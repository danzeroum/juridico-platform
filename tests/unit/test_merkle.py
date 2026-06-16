"""
Testes do Decision Ledger com Merkle tree completa.

Critérios de aceite da Fase 0:
- get_proof(entry_id) e verify_integrity(entry_id, proof) implementados.
- Integridade da entrada nº 1 verificável com ≥ 10k entradas.
- Cobertura de add_entry, prova de inclusão e falha de prova adulterada.
"""
import pytest


@pytest.fixture
def ledger():
    from services.shared.ledger.merkle import DecisionLedger
    return DecisionLedger()


def test_add_entry_retorna_campos_esperados(ledger):
    entry = ledger.add_entry(
        request_id="req-001",
        product="legalscore",
        inputs={"cnpj": "12345678000195"},
        outputs={"score": 720},
    )
    assert entry["request_id"] == "req-001"
    assert entry["product"] == "legalscore"
    assert "leaf_hash" in entry
    assert "merkle_root" in entry
    assert entry["entry_index"] == 0


def test_raiz_muda_a_cada_insercao(ledger):
    ledger.add_entry("r1", "legalscore", {}, {"score": 700})
    root1 = ledger.merkle_root
    ledger.add_entry("r2", "legalscore", {}, {"score": 800})
    root2 = ledger.merkle_root
    assert root1 != root2


def test_get_proof_entrada_inexistente(ledger):
    ledger.add_entry("r1", "legalscore", {}, {})
    with pytest.raises(KeyError):
        ledger.get_proof("nao-existe")


def test_verify_integrity_1_entrada(ledger):
    ledger.add_entry("r1", "legalscore", {"cnpj": "12345678000195"}, {"score": 700})
    proof = ledger.get_proof("r1")
    assert ledger.verify_integrity("r1", proof) is True


def test_verify_integrity_2_entradas(ledger):
    ledger.add_entry("r1", "prod", {}, {"v": 1})
    ledger.add_entry("r2", "prod", {}, {"v": 2})
    for req_id in ("r1", "r2"):
        proof = ledger.get_proof(req_id)
        assert ledger.verify_integrity(req_id, proof) is True


def test_verify_integrity_4_entradas(ledger):
    for i in range(4):
        ledger.add_entry(f"r{i}", "prod", {}, {"i": i})
    for i in range(4):
        proof = ledger.get_proof(f"r{i}")
        assert ledger.verify_integrity(f"r{i}", proof) is True


def test_verify_integrity_prova_adulterada(ledger):
    """Prova com leaf_hash adulterado deve falhar."""
    ledger.add_entry("r1", "prod", {}, {})
    ledger.add_entry("r2", "prod", {}, {})
    proof = ledger.get_proof("r1")
    proof["leaf_hash"] = "0" * 64  # adulterado
    assert ledger.verify_integrity("r1", proof) is False


def test_verify_integrity_10k_entradas():
    """
    Critério explícito da Fase 0: entrada nº 1 verificável com ≥ 10k entradas.
    A prova de inclusão deve ser válida independente do tamanho da árvore.
    """
    from services.shared.ledger.merkle import DecisionLedger
    ledger = DecisionLedger()
    for i in range(10_001):
        ledger.add_entry(f"r{i}", "perf-test", {}, {"i": i})

    # Verificar a primeira entrada (posição 0 na árvore)
    proof = ledger.get_proof("r0")
    assert ledger.verify_integrity("r0", proof) is True, (
        "Entrada nº 1 deve ser verificável com 10k+ entradas"
    )

    # E a última também
    proof_last = ledger.get_proof("r10000")
    assert ledger.verify_integrity("r10000", proof_last) is True


def test_subject_token_nao_e_pii(ledger):
    """subject_token deve ser armazenado como campo opaco (não PII em claro)."""
    entry = ledger.add_entry(
        "r1", "legalscore", {}, {},
        subject_token="ENCRYPTED_TOKEN_NOT_PII",
    )
    assert entry["subject_token"] == "ENCRYPTED_TOKEN_NOT_PII"


def test_len(ledger):
    assert len(ledger) == 0
    ledger.add_entry("r1", "p", {}, {})
    assert len(ledger) == 1
    ledger.add_entry("r2", "p", {}, {})
    assert len(ledger) == 2


def test_merkle_root_ledger_vazio(ledger):
    """Ledger vazio não deve explodir; retorna hash determinístico da string vazia."""
    root = ledger.merkle_root
    assert isinstance(root, str) and len(root) == 64
