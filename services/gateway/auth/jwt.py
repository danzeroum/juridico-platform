"""
Utilitários JWT RS256 para autenticação.

Fluxo:
- Geração do par RSA: gerar_par_chaves() — executar uma vez em setup.
- Emissão de token: issue_token(user_id, tenant_id, role, expires_in).
- Validação de token: validate_token(token) → TokenPayload.
- Chave pública: get_public_key() → para /.well-known/jwks.json.

Em produção:
- PRIVATE_KEY_PEM: Docker Secret (load_secret("JWT_PRIVATE_KEY")).
- PUBLIC_KEY_PEM: pode ser público (/.well-known/jwks.json).
- Rotação de chave: publicar nova chave JWKS antes de invalidar a antiga.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

try:
    import jwt as pyjwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False

from services.shared.config import load_secret

logger = logging.getLogger(__name__)

_DEV_ENVS = {"dev", "development", "test"}

ALGORITHM = "RS256"
TOKEN_EXPIRY_SECONDS = int(os.getenv("JWT_EXPIRY_SECONDS", "3600"))
ISSUER = os.getenv("JWT_ISSUER", "juridico-platform")

_private_key_pem: bytes | None = None
_public_key_pem: bytes | None = None


def _load_keys() -> tuple[bytes, bytes]:
    global _private_key_pem, _public_key_pem
    if _private_key_pem and _public_key_pem:
        return _private_key_pem, _public_key_pem

    if not _JWT_AVAILABLE:
        raise ImportError("PyJWT[crypto] e cryptography são necessários. pip install PyJWT[crypto]")

    # Tentar carregar do Docker Secret / env
    priv_pem = load_secret("JWT_PRIVATE_KEY")
    pub_pem = load_secret("JWT_PUBLIC_KEY")

    if priv_pem and pub_pem:
        _private_key_pem = priv_pem.encode() if isinstance(priv_pem, str) else priv_pem
        _public_key_pem = pub_pem.encode() if isinstance(pub_pem, str) else pub_pem
    else:
        # Sem chaves configuradas. FALHAR FECHADO em produção — um par efêmero
        # invalida todos os tokens a cada restart e diverge entre réplicas.
        env = os.getenv("ENV", "production").strip().lower()
        if env not in _DEV_ENVS:
            raise RuntimeError(
                "JWT_PRIVATE_KEY/JWT_PUBLIC_KEY ausentes. São obrigatórios em "
                "produção (Docker Secret/Vault) — sem fallback efêmero."
            )
        logger.warning(
            "Chaves JWT ausentes — gerando par EFÊMERO (apenas %s). "
            "Tokens invalidam no restart e divergem entre réplicas.",
            env,
        )
        _private_key_pem, _public_key_pem = _generate_ephemeral_keypair()

    return _private_key_pem, _public_key_pem


def _generate_ephemeral_keypair() -> tuple[bytes, bytes]:
    """Gera par RSA efêmero para desenvolvimento. Em produção usar Docker Secret."""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def issue_token(
    user_id: str,
    tenant_id: str,
    role: str,
    expires_in: int = TOKEN_EXPIRY_SECONDS,
) -> str:
    """Emite JWT RS256 com claims de tenant e role."""
    private_pem, _ = _load_keys()
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
        "iss": ISSUER,
    }
    return pyjwt.encode(payload, private_pem, algorithm=ALGORITHM)


def validate_token(token: str) -> dict[str, Any]:
    """
    Valida JWT RS256 e retorna payload.
    Lança pyjwt.InvalidTokenError se inválido ou expirado.
    """
    _, public_pem = _load_keys()
    return pyjwt.decode(
        token,
        public_pem,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "tenant_id", "role", "exp", "iss"]},
        issuer=ISSUER,
    )


def get_public_key_pem() -> str:
    """Retorna a chave pública em PEM para /.well-known/jwks.json."""
    _, public_pem = _load_keys()
    return public_pem.decode() if isinstance(public_pem, bytes) else public_pem
