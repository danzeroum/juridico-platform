"""
Cliente OpenSearch para a camada silver (dado limpo e consultável).

Convenção (plano A.1):
- índice mensal `datajud-silver-YYYY-MM` (e `abj-silver` para a fonte ABJ)
- `_id` = campo estável do registro (ex.: `id_processo`) → reindex idempotente
- escrita via API `_bulk` (batelada), nunca por-documento — DATAJUD é alto volume

I/O externo — omitido de cobertura; validado em E2E. Cliente lazy: importar este
módulo não exige `opensearch-py` nem conexão viva.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _client():
    from opensearchpy import OpenSearch

    from services.shared.config import settings

    return OpenSearch(hosts=[settings.OPENSEARCH_URL], http_compress=True, timeout=30)


def ensure_index(index: str, mapping: dict[str, Any] | None = None, client: Any | None = None) -> None:
    """Cria o índice com mapping explícito, se ausente (idempotente)."""
    client = client or _client()
    if client.indices.exists(index=index):
        return
    body = {"mappings": mapping} if mapping else None
    client.indices.create(index=index, body=body)
    logger.info("OpenSearch: índice %s criado", index)


def bulk_index(
    index: str,
    docs: list[dict[str, Any]],
    id_field: str = "id_processo",
    mapping: dict[str, Any] | None = None,
    client: Any | None = None,
) -> int:
    """
    Indexa `docs` no `index` em batelada (API `_bulk`).

    `_id` de cada documento vem de `doc[id_field]` (reindex idempotente); docs
    sem esse campo recebem id gerado pelo OpenSearch. Retorna o número de
    documentos enviados. Degradação graciosa: erros parciais do bulk são logados,
    não levantam exceção.
    """
    if not docs:
        return 0
    client = client or _client()
    ensure_index(index, mapping, client)

    actions: list[dict[str, Any]] = []
    for doc in docs:
        meta: dict[str, Any] = {"index": {"_index": index}}
        doc_id = doc.get(id_field)
        if doc_id is not None:
            meta["index"]["_id"] = str(doc_id)
        actions.append(meta)
        actions.append(doc)

    resp = client.bulk(body=actions)
    if resp.get("errors"):
        n_err = sum(1 for item in resp.get("items", []) if item.get("index", {}).get("error"))
        logger.warning("OpenSearch bulk em %s: %d de %d com erro", index, n_err, len(docs))
    logger.info("OpenSearch: %d docs → %s", len(docs), index)
    return len(docs)
