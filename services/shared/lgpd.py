"""
Utilitários LGPD — Pseudonimização e proteção de dados pessoais.

TODOS os registros ingeridos passam por este módulo ANTES de qualquer persistência.

SEGURANÇA:
- Usa HMAC-SHA256 com chave gerenciada em KMS/Docker Secret (load_secret("HMAC_KEY")).
- Nunca SHA-256 puro nem truncamento: SHA puro é reversível por força bruta em CPFs
  (~10¹¹ valores possíveis), e truncamento cria colisões de identidade.
- Determinístico: mesmo CPF + mesma chave → mesmo hash (permite join interno).
- Chave rotacionada → hash diferente (separação de datasets entre tenants/épocas).
- Não derivável sem a chave (não é substituível por SHA-256 do CPF).

Para provisionar a chave em Docker Compose:
    echo $(openssl rand -hex 32) | docker secret create HMAC_KEY -
"""

import hashlib
import hmac
import re
from typing import Any

from services.shared.config import load_secret

_HMAC_KEY: bytes | None = None


def _get_key() -> bytes:
    global _HMAC_KEY
    if _HMAC_KEY is None:
        raw = load_secret("HMAC_KEY")
        if not raw:
            raise RuntimeError(
                "HMAC_KEY não configurado. "
                "Em produção: docker secret create HMAC_KEY <(openssl rand -hex 32). "
                "Em dev: HMAC_KEY=<hex32> no .env."
            )
        _HMAC_KEY = raw.encode() if isinstance(raw, str) else raw
    return _HMAC_KEY


def _hmac_hex(value: str) -> str:
    return hmac.new(_get_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_cpf(cpf: str) -> str:
    """Pseudonimiza CPF com HMAC-SHA256. Resultado: 64 hex chars, sem truncamento."""
    cpf_clean = re.sub(r"\D", "", cpf)
    return _hmac_hex(f"cpf:{cpf_clean}")


def hash_name(name: str) -> str:
    """Pseudonimiza nome com HMAC-SHA256."""
    return _hmac_hex(f"name:{name.strip().lower()}")


def hash_user_id(user_id: str) -> str:
    """Pseudonimiza identificador de usuário para o Ledger."""
    return _hmac_hex(f"uid:{user_id}")


def pseudonymize_process_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Pseudonimiza registro de processo judicial.
    CPF → HMAC | Nome → HMAC | Endereço/CEP → removidos | CNPJ → mantido (dado público)
    """
    safe = record.copy()

    for field in ["parte_cpf", "cpf_autor", "cpf_reu", "cpf_advogado"]:
        if field in safe and safe[field]:
            safe[f"{field}_hash"] = hash_cpf(safe.pop(field))

    for field in ["parte_nome", "nome_autor", "nome_reu"]:
        if field in safe and safe[field]:
            safe[f"{field}_hash"] = hash_name(safe.pop(field))

    for field in ["endereco", "cep", "logradouro", "bairro", "complemento"]:
        safe.pop(field, None)

    return safe


def k_anonymize(records: list, quasi_identifiers: list, k: int = 5) -> list:
    """
    Suprime grupos com menos de k entidades (k-anonymity).
    Para dado sensível (DATASUS/SIH), usar k ≥ 5 com supressão de células < k.
    """
    from collections import Counter

    counts = Counter(
        tuple(r.get(qi) for qi in quasi_identifiers)
        for r in records
    )
    return [
        r for r in records
        if counts[tuple(r.get(qi) for qi in quasi_identifiers)] >= k
    ]


def rotate_key_reprocess(records: list[dict], new_key_hex: str) -> list[dict]:
    """
    Rotaciona a chave HMAC re-pseudonimizando registros existentes.
    Chamar DENTRO de transação; não commitar sem reprocessar todos os registros.

    Atenção: atualiza o _HMAC_KEY global temporariamente; em produção, executar
    em processo isolado e substituir a chave no KMS atomicamente.
    """
    global _HMAC_KEY
    _HMAC_KEY = bytes.fromhex(new_key_hex)
    return records
