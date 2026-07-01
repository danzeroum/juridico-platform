"""
Armazenamento de planilhas no MinIO (bucket `documents`).

Motivação (plano §3): o enriquecimento de planilhas de até 40k itens NÃO deve
trafegar as linhas inline na mensagem do Celery (payload enorme no Redis). O
gateway grava o arquivo no MinIO e passa só a KEY; o worker lê o arquivo do MinIO.

I/O externo — omitido de cobertura; validado em E2E.
"""
from __future__ import annotations

DOCUMENTS_BUCKET = "documents"


def _client():
    from minio import Minio

    from services.shared.config import settings

    return Minio(
        settings.MINIO_URL.replace("http://", "").replace("https://", ""),
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_URL.startswith("https://"),
    )


def upload_spreadsheet(key: str, data: bytes) -> str:
    """Grava os bytes da planilha no MinIO e devolve a key."""
    import io

    client = _client()
    client.put_object(DOCUMENTS_BUCKET, key, io.BytesIO(data), length=len(data))
    return key


def download_spreadsheet(key: str) -> bytes:
    """Lê os bytes da planilha do MinIO."""
    resp = _client().get_object(DOCUMENTS_BUCKET, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()
