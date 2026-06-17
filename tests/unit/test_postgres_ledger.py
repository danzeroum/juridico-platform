"""
Testes da PostgresDecisionLedger (Fase 1c) — backend Postgres com mock.

A camada de conexão (tenant_transaction + SQLAlchemy) é substituída por mocks
via unittest.mock.patch; nenhum Postgres real é necessário.

Verifica:
1. add_entry executa COUNT + SELECT leaf_hashes + INSERT com parâmetros corretos
2. add_entry entry_index = COUNT(*) das entradas existentes
3. get_proof retorna estrutura completa (entry_id, leaf_hash, proof, root)
4. get_proof levanta KeyError para entry_id inexistente
5. verify_integrity retorna True para prova válida
6. verify_integrity retorna False para leaf_hash adulterado
7. verify_integrity retorna False quando ledger vazio (db_root = None)
8. __len__ delega para COUNT(*)
9. Múltiplos tenants isolados (cada instância usa seu próprio tenant_id)
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Infraestrutura de mock: simula tenant_transaction + SQLAlchemy Connection
# ---------------------------------------------------------------------------

def _make_mock_conn(count: int = 0, leaf_hashes: list = None,
                    last_root: str | None = None, entry_row=None) -> MagicMock:
    """
    Cria mock de SQLAlchemy Connection que despacha por padrão SQL.

    Ordem de prioridade nas verificações de SQL (mais específico primeiro):
    - "COUNT(*)"              → scalar = count
    - "merkle_root" + "DESC"  → scalar = last_root   (verify_integrity)
    - "entry_index, leaf_hash"→ fetchone = entry_row  (get_proof entry lookup)
    - "leaf_hash" + "ORDER"   → fetchall = leaf_hashes (add_entry / get_proof)
    - INSERT                  → noop
    """
    leaf_hashes = leaf_hashes or []
    conn = MagicMock()

    def execute(stmt, params=None):
        sql = str(stmt)
        result = MagicMock()
        if "COUNT(*)" in sql:
            result.scalar.return_value = count
        elif "merkle_root" in sql and "DESC LIMIT 1" in sql:
            result.scalar.return_value = last_root
        elif "entry_index, leaf_hash" in sql:
            result.fetchone.return_value = entry_row
        elif "leaf_hash" in sql and "ORDER BY entry_index" in sql:
            result.fetchall.return_value = [(h,) for h in leaf_hashes]
        # INSERT INTO → result não utilizado pelo chamador
        return result

    conn.execute.side_effect = execute
    return conn


def _tx_factory(conn):
    """Retorna um context manager de tenant_transaction que sempre yield conn."""
    @contextmanager
    def _mock_tx(tenant_id: str):
        yield conn
    return _mock_tx


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestPostgresDecisionLedger:
    def test_add_entry_retorna_campos_obrigatorios(self):
        conn = _make_mock_conn(count=0, leaf_hashes=[])
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            entry = PostgresDecisionLedger("tenant-1").add_entry(
                request_id="req-pg-001",
                product="legalscore",
                inputs={"cnpj": "12345678000195"},
                outputs={"score": 720},
            )

        assert entry["request_id"] == "req-pg-001"
        assert entry["product"] == "legalscore"
        assert entry["entry_index"] == 0
        assert len(entry["leaf_hash"]) == 64
        assert len(entry["merkle_root"]) == 64

    def test_add_entry_entry_index_igual_a_count(self):
        """entry_index deve ser o COUNT(*) das entradas já existentes."""
        conn = _make_mock_conn(count=3, leaf_hashes=["a" * 64, "b" * 64, "c" * 64])
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            entry = PostgresDecisionLedger("tenant-1").add_entry("req-4", "p", {}, {})

        assert entry["entry_index"] == 3

    def test_add_entry_executa_tres_queries(self):
        """add_entry deve executar COUNT, SELECT leaf_hashes e INSERT."""
        conn = _make_mock_conn(count=0, leaf_hashes=[])
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            PostgresDecisionLedger("tenant-1").add_entry("r1", "legalscore", {}, {})

        assert conn.execute.call_count == 3

    def test_add_entry_insert_com_tenant_id_correto(self):
        """O INSERT deve incluir o tenant_id passado ao construtor."""
        conn = _make_mock_conn(count=0, leaf_hashes=[])
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            PostgresDecisionLedger("TENANT-ABC").add_entry("r1", "legalscore", {}, {})

        insert_call = conn.execute.call_args_list[2]
        params = insert_call.args[1] if len(insert_call.args) > 1 else {}
        assert params.get("tenant_id") == "TENANT-ABC"

    def test_add_entry_subject_token_afeta_leaf_hash(self):
        """subject_token faz parte do dict hasheado → leaf_hash diferente."""
        conn_a = _make_mock_conn(count=0, leaf_hashes=[])
        conn_b = _make_mock_conn(count=0, leaf_hashes=[])

        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn_a)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            e1 = PostgresDecisionLedger("t").add_entry("r1", "p", {}, {}, subject_token=None)

        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn_b)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            e2 = PostgresDecisionLedger("t").add_entry("r1", "p", {}, {}, subject_token="ENCRYPTED")

        assert e1["leaf_hash"] != e2["leaf_hash"]

    def test_get_proof_retorna_estrutura_correta(self):
        from services.shared.ledger.merkle import _sha256

        leaf = _sha256("entry-data")
        conn = _make_mock_conn(leaf_hashes=[leaf], entry_row=(0, leaf))
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            proof = PostgresDecisionLedger("tenant-1").get_proof("req-001")

        assert proof["entry_id"] == "req-001"
        assert proof["entry_index"] == 0
        assert proof["leaf_hash"] == leaf
        assert isinstance(proof["proof"], list)
        assert len(proof["root"]) == 64

    def test_get_proof_entry_inexistente_levanta_key_error(self):
        import pytest
        conn = _make_mock_conn(entry_row=None, leaf_hashes=[])
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            with pytest.raises(KeyError, match="não encontrada"):
                PostgresDecisionLedger("tenant-1").get_proof("req-inexistente")

    def test_verify_integrity_prova_valida_retorna_true(self):
        from services.shared.ledger.merkle import (
            PostgresDecisionLedger,
            _compute_merkle_root,
            _generate_proof,
            _sha256,
        )

        leaf1 = _sha256("entry-1-data")
        leaf2 = _sha256("entry-2-data")
        root = _compute_merkle_root([leaf1, leaf2])
        proof = {
            "entry_id": "r1",
            "entry_index": 0,
            "leaf_hash": leaf1,
            "proof": _generate_proof([leaf1, leaf2], 0),
            "root": root,
        }
        conn = _make_mock_conn(leaf_hashes=[leaf1, leaf2], last_root=root)
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            result = PostgresDecisionLedger("tenant-1").verify_integrity("r1", proof)

        assert result is True

    def test_verify_integrity_leaf_hash_adulterado_retorna_false(self):
        from services.shared.ledger.merkle import (
            PostgresDecisionLedger,
            _compute_merkle_root,
            _generate_proof,
            _sha256,
        )

        leaf1 = _sha256("e1")
        leaf2 = _sha256("e2")
        root = _compute_merkle_root([leaf1, leaf2])
        adulterado = {
            "leaf_hash": "0" * 64,  # adulterado
            "proof": _generate_proof([leaf1, leaf2], 0),
            "root": root,
        }
        conn = _make_mock_conn(last_root=root)
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            result = PostgresDecisionLedger("tenant-1").verify_integrity("r1", adulterado)

        assert result is False

    def test_verify_integrity_ledger_vazio_retorna_false(self):
        """db_root = None (nenhuma entrada no banco) → verify_integrity é False."""
        from services.shared.ledger.merkle import PostgresDecisionLedger, _sha256

        proof = {"leaf_hash": _sha256("x"), "proof": [], "root": _sha256("x")}
        conn = _make_mock_conn(last_root=None)
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            assert PostgresDecisionLedger("tenant-1").verify_integrity("r1", proof) is False

    def test_len_delega_count_ao_banco(self):
        conn = _make_mock_conn(count=42)
        with patch("services.shared.tenant_db.tenant_transaction", new=_tx_factory(conn)):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            assert len(PostgresDecisionLedger("tenant-1")) == 42

    def test_tenants_distintos_usam_tenant_ids_distintos(self):
        """Dois tenants devem passar tenant_ids diferentes para tenant_transaction."""
        called_with: list[str] = []

        @contextmanager
        def recording_tx(tenant_id: str):
            called_with.append(tenant_id)
            conn = _make_mock_conn(count=0, leaf_hashes=[])
            yield conn

        with patch("services.shared.tenant_db.tenant_transaction", new=recording_tx):
            from services.shared.ledger.merkle import PostgresDecisionLedger
            PostgresDecisionLedger("tenant-A").add_entry("r1", "p", {}, {})
            PostgresDecisionLedger("tenant-B").add_entry("r2", "p", {}, {})

        assert "tenant-A" in called_with
        assert "tenant-B" in called_with
        assert called_with.count("tenant-A") == called_with.count("tenant-B")
