"""
Testes do audit trail estruturado para operações com PII.

Verifica:
- Formato JSON dos eventos (campos obrigatórios)
- Pseudonimização do pseudônimo nos logs (SHA-256, não valor em claro)
- Integração com lgpd_crypto: decrypt e erase disparam eventos de auditoria
- Isolamento de tenant nos logs
"""
from __future__ import annotations

import json
import logging


def _capture_audit_logs(func):
    """Executa func e retorna lista de registros emitidos pelo logger 'audit'."""
    records: list[logging.LogRecord] = []

    handler = logging.handlers.MemoryHandler(capacity=100, target=None)
    handler.buffer = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    capture = _Capture()
    audit_logger = logging.getLogger("audit")
    audit_logger.addHandler(capture)
    audit_logger.setLevel(logging.DEBUG)
    try:
        func()
    finally:
        audit_logger.removeHandler(capture)
    return records


import logging.handlers  # noqa: E402 (after helper uses it)

# ---------------------------------------------------------------------------
# log_ledger_write
# ---------------------------------------------------------------------------

def test_ledger_write_emits_event():
    from services.shared.audit_log import log_ledger_write

    records = _capture_audit_logs(lambda: log_ledger_write(
        request_id="req-001",
        product="legalscore",
        tenant_id="t1",
        entry_index=0,
        has_subject_token=True,
    ))
    assert len(records) == 1
    body = json.loads(records[0].getMessage())
    assert body["event"] == "ledger.write"
    assert body["request_id"] == "req-001"
    assert body["product"] == "legalscore"
    assert body["tenant_id"] == "t1"
    assert body["entry_index"] == 0
    assert body["has_subject_token"] is True
    assert "timestamp" in body


def test_ledger_write_no_pii_in_log():
    from services.shared.audit_log import log_ledger_write

    records = _capture_audit_logs(lambda: log_ledger_write(
        request_id="req-002",
        product="legalscore",
        tenant_id="t1",
        entry_index=1,
        has_subject_token=False,
    ))
    body = json.loads(records[0].getMessage())
    # Nenhum campo deve ter PII — só booleano indicando presença do token
    assert "cnpj" not in body
    assert "cpf" not in body
    assert body["has_subject_token"] is False


# ---------------------------------------------------------------------------
# log_pii_decrypt
# ---------------------------------------------------------------------------

def test_pii_decrypt_emits_event():
    from services.shared.audit_log import log_pii_decrypt

    records = _capture_audit_logs(lambda: log_pii_decrypt(
        pseudonym="hmac-abc123",
        tenant_id="tenant-x",
    ))
    assert len(records) == 1
    body = json.loads(records[0].getMessage())
    assert body["event"] == "pii.decrypt"
    assert body["tenant_id"] == "tenant-x"
    assert "timestamp" in body


def test_pii_decrypt_logs_sha256_not_plaintext():
    import hashlib

    from services.shared.audit_log import log_pii_decrypt

    pseudonym = "hmac-secret-value"
    expected_sha = hashlib.sha256(pseudonym.encode()).hexdigest()

    records = _capture_audit_logs(lambda: log_pii_decrypt(
        pseudonym=pseudonym,
        tenant_id="t1",
    ))
    body = json.loads(records[0].getMessage())
    assert body["pseudonym_sha256"] == expected_sha
    assert pseudonym not in records[0].getMessage()


# ---------------------------------------------------------------------------
# log_pii_erase
# ---------------------------------------------------------------------------

def test_pii_erase_emits_event():
    from services.shared.audit_log import log_pii_erase

    records = _capture_audit_logs(lambda: log_pii_erase(
        pseudonym="hmac-xyz",
        tenant_id="tenant-y",
        existed=True,
    ))
    assert len(records) == 1
    body = json.loads(records[0].getMessage())
    assert body["event"] == "pii.erase"
    assert body["existed"] is True
    assert body["tenant_id"] == "tenant-y"


def test_pii_erase_existed_false():
    from services.shared.audit_log import log_pii_erase

    records = _capture_audit_logs(lambda: log_pii_erase(
        pseudonym="hmac-gone",
        tenant_id="t1",
        existed=False,
    ))
    body = json.loads(records[0].getMessage())
    assert body["existed"] is False


# ---------------------------------------------------------------------------
# Integração: lgpd_crypto chama audit_log automaticamente
# ---------------------------------------------------------------------------

def test_decrypt_triggers_audit_log():
    """decrypt_from_ledger() deve emitir pii.decrypt automaticamente."""
    from services.shared.lgpd_crypto import decrypt_from_ledger, encrypt_for_ledger

    pseudonym = "test-pseudo-audit"
    tenant_id = "audit-tenant"
    token = encrypt_for_ledger(pseudonym, tenant_id)

    records = _capture_audit_logs(lambda: decrypt_from_ledger(token, pseudonym, tenant_id))
    assert any(
        json.loads(r.getMessage()).get("event") == "pii.decrypt"
        for r in records
    )


def test_erase_triggers_audit_log():
    """erase_titular() deve emitir pii.erase automaticamente."""
    from services.shared.lgpd_crypto import encrypt_for_ledger, erase_titular

    pseudonym = "erase-audit-test"
    tenant_id = "erase-tenant"
    encrypt_for_ledger(pseudonym, tenant_id)  # cria a chave

    records = _capture_audit_logs(lambda: erase_titular(pseudonym, tenant_id))
    events = [json.loads(r.getMessage()).get("event") for r in records]
    assert "pii.erase" in events


def test_erase_nonexistent_logs_existed_false():
    """erase_titular() de chave inexistente loga existed=False (sem crash)."""
    from services.shared.lgpd_crypto import erase_titular

    records = _capture_audit_logs(lambda: erase_titular("never-existed", "t1"))
    body = json.loads(records[0].getMessage())
    assert body["event"] == "pii.erase"
    assert body["existed"] is False
