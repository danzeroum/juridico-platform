"""
Decision Ledger com Merkle tree completa.

Propriedades de segurança:
- Cobre TODAS as entradas (não apenas as últimas N).
- get_proof(entry_id)  → prova de inclusão: lista de (sibling_hash, posição).
- verify_integrity(entry_id, proof) → verifica a prova contra a raiz atual.
- A raiz é recalculada a cada add_entry (adequado para <10k entradas em memória).
  Para volumes maiores (Fase 1b), migrar para âncoras periódicas em Postgres.

subject_token: pseudônimo cifrado por chave AES-256-GCM por titular (não HMAC em
claro). O campo é distinto de AlertEnvelope.subject_ref (referências não-pessoais).
Apagar a chave AES no KMS = crypto-shredding (dados do titular tornam-se
irrelegíveis sem quebrar a prova de integridade da árvore).
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _compute_merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return _sha256("")
    layer = list(hashes)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [_sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0]


def _generate_proof(hashes: list[str], idx: int) -> list[dict[str, str]]:
    """Gera lista de passos da prova de inclusão Merkle para o índice idx."""
    steps: list[dict[str, str]] = []
    layer = list(hashes)
    position = idx

    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])

        is_right_child = (position % 2 == 1)
        sibling_idx = position - 1 if is_right_child else position + 1
        steps.append({
            "sibling": layer[sibling_idx],
            # "left" = irmão está à esquerda (current é filho direito)
            # "right" = irmão está à direita (current é filho esquerdo)
            "position": "left" if is_right_child else "right",
        })

        layer = [_sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
        position = position // 2

    return steps


class DecisionLedger:
    """
    Ledger append-only com Merkle tree cobrindo 100% das entradas.

    Em memória para Fase 0. Fase 1b migra para Postgres particionado com
    âncoras periódicas (raiz salva a cada N entradas na tabela ledger.anchors).
    """

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._leaf_hashes: list[str] = []
        self.merkle_root: str = _sha256("")

    def add_entry(
        self,
        request_id: str,
        product: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        sources: list[str] | None = None,
        weights: dict[str, Any] | None = None,
        subject_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Adiciona entrada ao ledger e recalcula a raiz Merkle.

        inputs/outputs: dados técnicos do request (sem PII — PII fica em subject_token).
        subject_token: pseudônimo cifrado do titular (AES-256-GCM). Nunca PII em claro.
        """
        entry: dict[str, Any] = {
            "request_id": request_id,
            "entry_index": len(self._entries),
            "timestamp": datetime.now(UTC).isoformat(),
            "product": product,
            "inputs_hash": _sha256(json.dumps(inputs, sort_keys=True)),
            "outputs_hash": _sha256(json.dumps(outputs, sort_keys=True)),
            "sources": sources or [],
            "weights_applied": weights or {},
            "subject_token": subject_token,
        }
        leaf_hash = _sha256(json.dumps(entry, sort_keys=True))
        self._entries.append(entry)
        self._leaf_hashes.append(leaf_hash)
        self.merkle_root = _compute_merkle_root(self._leaf_hashes)
        return {**entry, "leaf_hash": leaf_hash, "merkle_root": self.merkle_root}

    def get_proof(self, entry_id: str) -> dict[str, Any]:
        """
        Retorna a prova de inclusão Merkle para a entrada identificada por request_id.

        Complexidade: O(N) na busca + O(log N) para gerar os passos.
        Para N < 10M entradas em produção, usar índice de request_id → índice.
        """
        idx = next(
            (i for i, e in enumerate(self._entries) if e["request_id"] == entry_id),
            None,
        )
        if idx is None:
            raise KeyError(f"Entrada não encontrada no ledger: {entry_id!r}")

        return {
            "entry_id": entry_id,
            "entry_index": idx,
            "leaf_hash": self._leaf_hashes[idx],
            "proof": _generate_proof(self._leaf_hashes, idx),
            "root": self.merkle_root,
        }

    def verify_integrity(self, entry_id: str, proof: dict[str, Any]) -> bool:
        """
        Verifica uma prova de inclusão Merkle contra a raiz atual.

        Retorna True se e somente se a entrada está na árvore com a raiz atual.
        False indica adulteração ou prova para estado anterior do ledger.
        """
        current = proof["leaf_hash"]
        for step in proof["proof"]:
            sibling = step["sibling"]
            if step["position"] == "right":
                current = _sha256(current + sibling)
            else:
                current = _sha256(sibling + current)
        return current == self.merkle_root

    def __len__(self) -> int:
        return len(self._entries)


# Frequência de checkpoints Merkle em ledger.anchors.
# Não reduz O(N) do recálculo atual (requer migração para MMR — ver Pendencia.md QT-08);
# fornece marcos de auditoria histórica verificáveis sem replay total.
_ANCHOR_INTERVAL = 1024


class PostgresDecisionLedger:
    """
    Decision Ledger com backend Postgres (Fase 1c).

    Usa tenant_transaction() para todas as operações; a RLS do Postgres enforça
    isolamento de tenant. O Merkle tree é por tenant: entradas ordenadas por
    entry_index, raiz recalculada a cada INSERT.

    Custo atual: O(N) por inserção (lê todos os leaf_hashes do tenant).
    Mitigation: advisory lock serializa escritas por tenant (evita bifurcação
    da cadeia Merkle); checkpoint a cada _ANCHOR_INTERVAL entradas (auditoria
    histórica). Migração para O(log N) requer MMR — ver Pendencia.md QT-08.

    A aplicação DEVE conectar como role não-superusuário (app_user definido em
    bootstrap-db.sql). No PostgreSQL, superusuários bypassam FORCE ROW LEVEL
    SECURITY — esse vetor não pode ser eliminado por política SQL.
    """

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id

    def add_entry(
        self,
        request_id: str,
        product: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        sources: list[str] | None = None,
        weights: dict[str, Any] | None = None,
        subject_token: str | None = None,
    ) -> dict[str, Any]:
        from sqlalchemy import text as sa_text

        from services.shared.tenant_db import tenant_transaction

        with tenant_transaction(self._tenant_id) as conn:
            # Serializa escritas por tenant dentro da transação.
            # pg_advisory_xact_lock libera automaticamente no COMMIT/ROLLBACK.
            # Previne que dois requests concorrentes do mesmo tenant leiam o
            # mesmo COUNT(*) e insiram entry_index duplicado (bifurcação Merkle).
            conn.execute(
                sa_text("SELECT pg_advisory_xact_lock(hashtext(:tid)::bigint)"),
                {"tid": self._tenant_id},
            )

            entry_index = int(
                conn.execute(sa_text("SELECT COUNT(*) FROM ledger.entries")).scalar() or 0
            )
            existing_hashes: list[str] = [
                r[0]
                for r in conn.execute(
                    sa_text("SELECT leaf_hash FROM ledger.entries ORDER BY entry_index")
                ).fetchall()
            ]

            entry: dict[str, Any] = {
                "request_id": request_id,
                "entry_index": entry_index,
                "timestamp": datetime.now(UTC).isoformat(),
                "product": product,
                "inputs_hash": _sha256(json.dumps(inputs, sort_keys=True)),
                "outputs_hash": _sha256(json.dumps(outputs, sort_keys=True)),
                "sources": sources or [],
                "weights_applied": weights or {},
                "subject_token": subject_token,
            }
            leaf_hash = _sha256(json.dumps(entry, sort_keys=True))
            new_root = _compute_merkle_root(existing_hashes + [leaf_hash])

            conn.execute(
                sa_text(
                    """
                    INSERT INTO ledger.entries
                        (request_id, entry_index, product, tenant_id, inputs_hash,
                         outputs_hash, sources, weights_applied, subject_token,
                         leaf_hash, merkle_root)
                    VALUES
                        (:request_id, :entry_index, :product, :tenant_id::uuid,
                         :inputs_hash, :outputs_hash, :sources::jsonb,
                         :weights_applied::jsonb, :subject_token, :leaf_hash, :merkle_root)
                    """
                ),
                {
                    "request_id": request_id,
                    "entry_index": entry_index,
                    "product": product,
                    "tenant_id": self._tenant_id,
                    "inputs_hash": entry["inputs_hash"],
                    "outputs_hash": entry["outputs_hash"],
                    "sources": json.dumps(sources or []),
                    "weights_applied": json.dumps(weights or {}),
                    "subject_token": subject_token,
                    "leaf_hash": leaf_hash,
                    "merkle_root": new_root,
                },
            )

            # Checkpoint periódico: salva raiz Merkle verificável em ledger.anchors.
            # Permite auditoria histórica sem replay total. Não reduz O(N) deste método.
            new_count = entry_index + 1
            if new_count % _ANCHOR_INTERVAL == 0:
                conn.execute(
                    sa_text(
                        "INSERT INTO ledger.anchors (anchor_at_index, merkle_root, tenant_id)"
                        " VALUES (:idx, :root, :tenant_id::uuid)"
                    ),
                    {"idx": entry_index, "root": new_root, "tenant_id": self._tenant_id},
                )

        return {**entry, "leaf_hash": leaf_hash, "merkle_root": new_root}

    def get_proof(self, entry_id: str) -> dict[str, Any]:
        from sqlalchemy import text as sa_text

        from services.shared.tenant_db import tenant_transaction

        with tenant_transaction(self._tenant_id) as conn:
            row = conn.execute(
                sa_text(
                    "SELECT entry_index, leaf_hash FROM ledger.entries "
                    "WHERE request_id = :rid"
                ),
                {"rid": entry_id},
            ).fetchone()
            if row is None:
                raise KeyError(f"Entrada não encontrada no ledger: {entry_id!r}")
            idx, leaf_hash = int(row[0]), row[1]

            all_hashes: list[str] = [
                r[0]
                for r in conn.execute(
                    sa_text("SELECT leaf_hash FROM ledger.entries ORDER BY entry_index")
                ).fetchall()
            ]

        return {
            "entry_id": entry_id,
            "entry_index": idx,
            "leaf_hash": leaf_hash,
            "proof": _generate_proof(all_hashes, idx),
            "root": _compute_merkle_root(all_hashes),
        }

    def verify_integrity(self, entry_id: str, proof: dict[str, Any]) -> bool:
        from sqlalchemy import text as sa_text

        from services.shared.tenant_db import tenant_transaction

        current = proof["leaf_hash"]
        for step in proof["proof"]:
            sibling = step["sibling"]
            if step["position"] == "right":
                current = _sha256(current + sibling)
            else:
                current = _sha256(sibling + current)

        with tenant_transaction(self._tenant_id) as conn:
            db_root = conn.execute(
                sa_text(
                    "SELECT merkle_root FROM ledger.entries "
                    "ORDER BY entry_index DESC LIMIT 1"
                )
            ).scalar()

        return db_root is not None and current == db_root

    def __len__(self) -> int:
        from sqlalchemy import text as sa_text

        from services.shared.tenant_db import tenant_transaction

        with tenant_transaction(self._tenant_id) as conn:
            return int(
                conn.execute(sa_text("SELECT COUNT(*) FROM ledger.entries")).scalar() or 0
            )
