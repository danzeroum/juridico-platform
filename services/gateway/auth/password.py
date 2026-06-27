"""
Hashing de senha com PBKDF2-HMAC-SHA256 (stdlib — sem dependências externas).

Formato armazenado (compatível com o estilo Django):
    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>

- `hash_password(plain)` gera salt aleatório por senha e devolve a string acima.
- `verify_password(plain, encoded)` recomputa e compara em tempo constante.

Trocar o nº de iterações é seguro: o valor fica embutido em cada hash, então
hashes antigos continuam validáveis. Para migrar, re-hashear no próximo login.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 600_000  # OWASP 2023 (PBKDF2-HMAC-SHA256)
_SALT_BYTES = 16


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def hash_password(plain: str, *, iterations: int = _DEFAULT_ITERATIONS) -> str:
    """Gera o hash PBKDF2 de uma senha em texto puro."""
    if not plain:
        raise ValueError("senha vazia")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${_b64(salt)}${_b64(dk)}"


def verify_password(plain: str, encoded: str | None) -> bool:
    """Valida uma senha contra o hash armazenado. Falha fechado (False) em erro."""
    if not plain or not encoded:
        return False
    try:
        algo, iters_s, salt_b64, hash_b64 = encoded.split("$")
        if algo != _ALGO:
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, int(iters_s))
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False
