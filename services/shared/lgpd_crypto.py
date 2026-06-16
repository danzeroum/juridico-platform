"""
Crypto-shredding para o Decision Ledger (P0-3 da DoD).

Cada titular recebe uma chave AES-256-GCM ÚNICA, gerada aleatoriamente e
armazenada no KMS/Docker Secret indexada por `titular_id`. Para apagar os dados
de um titular, basta destruir a chave — o `subject_token` cifrado no Ledger
torna-se irrecuperável, mas `verify_integrity()` continua True (a prova de
integridade verifica o hash dos inputs/outputs, não a decriptabilidade do token).

Por que AES-256-GCM por titular (e não HMAC por titular):
  - HMAC é pseudonimização determinística, não cifragem: o HMAC de um CNPJ
    com chave conhecida é computável para sempre enquanto a chave existir.
  - AES-256-GCM é cifragem autenticada: sem a chave, o ciphertext é
    computacionalmente indistinguível de ruído aleatório.
  - Destruir a chave por titular é o mecanismo de erasure definido no ROADMAP.

Armazenamento de chaves:
  - Dev: dicionário em memória (volátil — para testes).
  - Produção: substituir _KEY_STORE por chamadas ao KMS (AWS KMS / HashiCorp
    Vault / GCP KMS). Em K8s, External Secrets Operator.

Formato do subject_token:
  base64url( iv_12_bytes || ciphertext || tag_16_bytes )
  — compacto, sem separadores, auto-contido para decriptação.

Uso:
    from services.shared.lgpd_crypto import encrypt_for_ledger, erase_titular

    token = encrypt_for_ledger("uid:12345678000195", tenant_id="t1")
    # ... persiste token no ledger ...
    erase_titular("uid:12345678000195", tenant_id="t1")
    # → token agora é irrecuperável; verify_integrity() ainda True
"""
from __future__ import annotations

import base64
import os
import threading

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from services.shared.audit_log import log_pii_decrypt, log_pii_erase

_KEY_STORE: dict[str, bytes] = {}
_STORE_LOCK = threading.Lock()

_KEY_SIZE = 32  # AES-256


def _key_id(pseudonym: str, tenant_id: str) -> str:
    """Chave interna do store: escopa por tenant para isolamento."""
    return f"{tenant_id}:{pseudonym}"


def _load_or_create_key(key_id: str) -> bytes:
    """
    Retorna (ou cria) a chave AES-256 para este titular.

    Em produção substituir por: KMS.CreateKey(alias=key_id) se ausente,
    KMS.GetKey(alias=key_id) se presente.
    """
    with _STORE_LOCK:
        if key_id not in _KEY_STORE:
            _KEY_STORE[key_id] = os.urandom(_KEY_SIZE)
        return _KEY_STORE[key_id]


def encrypt_for_ledger(pseudonym: str, tenant_id: str) -> str:
    """
    Cifra o pseudônimo do titular com AES-256-GCM.

    Retorna base64url( IV‖ciphertext‖tag ) — o `subject_token` a persistir
    no Ledger. Nunca persiste PII em claro.

    Args:
        pseudonym: identificador já pseudonimizado (ex.: HMAC do CNPJ/CPF).
        tenant_id: isola a chave por tenant.
    """
    kid = _key_id(pseudonym, tenant_id)
    key = _load_or_create_key(kid)

    iv = os.urandom(12)  # 96-bit IV recomendado pelo NIST para AES-GCM
    aesgcm = AESGCM(key)
    ciphertext_and_tag = aesgcm.encrypt(iv, pseudonym.encode(), None)

    return base64.urlsafe_b64encode(iv + ciphertext_and_tag).decode()


def decrypt_from_ledger(token: str, pseudonym: str, tenant_id: str) -> str:
    """
    Decifra um subject_token — apenas para auditoria autorizada.

    Levanta InvalidTag se a chave foi apagada ou o token foi adulterado.
    """
    kid = _key_id(pseudonym, tenant_id)
    with _STORE_LOCK:
        key = _KEY_STORE.get(kid)
    if key is None:
        raise KeyError(f"Chave apagada para {kid!r} — titular erased.")

    raw = base64.urlsafe_b64decode(token.encode())
    iv, ciphertext_and_tag = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    result = aesgcm.decrypt(iv, ciphertext_and_tag, None).decode()
    log_pii_decrypt(pseudonym=pseudonym, tenant_id=tenant_id)
    return result


def erase_titular(pseudonym: str, tenant_id: str) -> bool:
    """
    Apaga a chave AES do titular → crypto-shredding.

    Após esta chamada:
    - `decrypt_from_ledger()` levanta KeyError.
    - `verify_integrity()` do Ledger continua True (hash dos inputs/outputs
      não muda; só o `subject_token` torna-se irrecuperável).

    Retorna True se a chave existia, False se já havia sido apagada.
    Em produção: KMS.DeleteKey(alias=_key_id(pseudonym, tenant_id)).
    """
    kid = _key_id(pseudonym, tenant_id)
    with _STORE_LOCK:
        existed = kid in _KEY_STORE
        _KEY_STORE.pop(kid, None)
    log_pii_erase(pseudonym=pseudonym, tenant_id=tenant_id, existed=existed)
    return existed


def is_erased(pseudonym: str, tenant_id: str) -> bool:
    """Verifica se a chave do titular foi apagada."""
    kid = _key_id(pseudonym, tenant_id)
    with _STORE_LOCK:
        return kid not in _KEY_STORE
