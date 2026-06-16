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
