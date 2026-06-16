"""
Audit trail estruturado para operações envolvendo PII.

Emite eventos JSON via logger 'audit.*' (separado do logger de aplicação).
Não loga PII em claro — usa SHA-256 do pseudônimo para correlação.

Eventos rastreados:
  ledger.write    — entrada criada no Decision Ledger com subject_token
  pii.decrypt     — token AES-GCM decriptado (acesso à ligação titular ↔ registro)
  pii.erase       — chave do titular apagada (crypto-shredding / direito ao esquecimento)
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any

_logger = logging.getLogger("audit")

_audit_lock = threading.Lock()


def _pseudonym_sha256(pseudonym: str) -> str:
    """SHA-256 do pseudônimo para correlação sem revelar o valor."""
    return hashlib.sha256(pseudonym.encode()).hexdigest()


def _emit(event_type: str, fields: dict[str, Any]) -> None:
    record: dict[str, Any] = {
        "event": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }
    with _audit_lock:
        _logger.info(json.dumps(record, ensure_ascii=False))


def log_ledger_write(
    *,
    request_id: str,
    product: str,
    tenant_id: str | None,
    entry_index: int,
    has_subject_token: bool,
) -> None:
    """Loga criação de entrada no Decision Ledger."""
    _emit("ledger.write", {
        "request_id": request_id,
        "product": product,
        "tenant_id": tenant_id,
        "entry_index": entry_index,
        "has_subject_token": has_subject_token,
    })


def log_pii_decrypt(
    *,
    pseudonym: str,
    tenant_id: str,
    caller: str = "unknown",
) -> None:
    """Loga decriptação de token AES-GCM — acesso à ligação titular ↔ registro."""
    _emit("pii.decrypt", {
        "pseudonym_sha256": _pseudonym_sha256(pseudonym),
        "tenant_id": tenant_id,
        "caller": caller,
    })


def log_pii_erase(
    *,
    pseudonym: str,
    tenant_id: str,
    existed: bool,
) -> None:
    """Loga apagamento de chave AES-GCM (crypto-shredding / direito ao esquecimento)."""
    _emit("pii.erase", {
        "pseudonym_sha256": _pseudonym_sha256(pseudonym),
        "tenant_id": tenant_id,
        "existed": existed,
    })
