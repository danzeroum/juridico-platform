"""
Ancoragem Merkle de um LOTE de triagem.

Motivação (plano §3, Pendencia.md QT-08): o Decision Ledger relê todas as folhas do
tenant por gravação (O(N)). Gravar uma entrada por item num lote de 40k daria O(N²)
+ 40k full-scans. Em vez disso:

  1. Classifica-se todos os itens (puro, engine.classify).
  2. Constrói-se UMA raiz Merkle local do lote em memória (O(N) uma vez).
  3. Grava-se UMA única entrada no Decision Ledger por JOB (hash do manifesto de
     entrada + raiz do lote).
  4. O decision_proof de cada item é a PROVA DE INCLUSÃO na árvore do lote
     (leaf_index + passos), verificável em O(log N) contra a raiz ancorada.

Reutiliza o mesmo esquema de hash/prova do Ledger (services/shared/ledger/merkle.py),
garantindo que as provas verifiquem com o mesmo algoritmo.
"""
from __future__ import annotations

import json
from typing import Any

from services.shared.contracts.fiscal import NcmTriageResult
from services.shared.ledger.merkle import (
    _compute_merkle_root,
    _generate_proof,
    _sha256,
)


def _leaf_for_item(index: int, result: NcmTriageResult) -> str:
    """Folha determinística de um item do lote (ordem canônica das chaves)."""
    payload = {
        "leaf_index": index,
        "sku_descricao": result.sku_descricao,
        "ncm": result.suggested_ncm.ncm_codigo if result.suggested_ncm else None,
        "confidence": result.suggested_ncm.confidence if result.suggested_ncm else None,
        "icms": result.icms.model_dump(),
        "categoria": result.categoria,
        "conflito": result.conflito_detectado,
    }
    return _sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def build_batch_anchor(results: list[NcmTriageResult]) -> dict[str, Any]:
    """
    Constrói a raiz Merkle do lote e as folhas. Retorna:
      {"root": <hex>, "leaf_hashes": [...], "count": N}
    """
    leaf_hashes = [_leaf_for_item(i, r) for i, r in enumerate(results)]
    return {
        "root": _compute_merkle_root(leaf_hashes),
        "leaf_hashes": leaf_hashes,
        "count": len(leaf_hashes),
    }


def inclusion_proof(leaf_hashes: list[str], leaf_index: int, root: str) -> dict[str, Any]:
    """
    Prova de inclusão de um item na árvore do lote. Formato compatível com
    DecisionLedger.verify_integrity (position 'left'/'right').
    """
    return {
        "leaf_index": leaf_index,
        "leaf_hash": leaf_hashes[leaf_index],
        "proof": _generate_proof(leaf_hashes, leaf_index),
        "root": root,
    }


def verify_inclusion(proof: dict[str, Any]) -> bool:
    """Verifica uma prova de inclusão do lote contra a raiz embutida."""
    current = proof["leaf_hash"]
    for step in proof["proof"]:
        sibling = step["sibling"]
        if step["position"] == "right":
            current = _sha256(current + sibling)
        else:
            current = _sha256(sibling + current)
    return current == proof["root"]


def batch_manifest_hash(job_id: str, tenant_id: str, count: int) -> str:
    """Hash do manifesto de entrada do lote — gravado no Ledger junto da raiz."""
    return _sha256(json.dumps({"job_id": job_id, "tenant_id": tenant_id, "count": count}, sort_keys=True))


def serialize_result(index: int, result: NcmTriageResult) -> dict[str, Any]:
    """Converte um NcmTriageResult numa linha de fiscal.triage_item (bulk insert)."""
    ncm = result.suggested_ncm
    return {
        "leaf_index": index,
        "sku_descricao": result.sku_descricao,
        "ncm_sugerido": ncm.ncm_codigo if ncm else None,
        "confidence": ncm.confidence if ncm else None,
        "fonte_regra": ncm.fonte_regra.value if ncm else None,
        "icms_interno_efetivo_pct": result.icms.interna_efetiva_pct,
        "icms_inter_pct": result.icms.interestadual_pct,
        "difal_pct": result.icms.difal_pct,
        "categoria": result.categoria,
        "conflito": result.conflito_detectado,
        "observacoes": result.observacoes,
    }
