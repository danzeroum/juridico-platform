"""
Auth router — emissão de JWT RS256 + sessão.

POST /api/v1/auth/token  → token de acesso (Bearer JWT RS256)
GET  /api/v1/auth/me     → claims do usuário autenticado (para hidratar o frontend)
GET  /.well-known/jwks.json → servido em main.py diretamente
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

router = APIRouter(tags=["auth"])

_DEV_ENVS = {"dev", "development", "test"}


class LoginRequest(BaseModel):
    # `username` carrega o e-mail do usuário (o form do frontend envia o e-mail).
    username: str
    password: str
    tenant_slug: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

    model_config = {"json_schema_extra": {
        "example": {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 3600,
        }
    }}


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Emite token JWT RS256",
    responses={
        200: {"description": "Token emitido com sucesso"},
        401: {
            "description": "Credenciais inválidas",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://juridico-platform/errors/401",
                        "title": "Não autenticado",
                        "status": 401,
                        "detail": "Credenciais inválidas.",
                        "instance": "/api/v1/auth/token",
                        "contract_version": "1.0",
                    }
                }
            },
        },
    },
)
async def login(request: LoginRequest) -> TokenResponse:
    """
    Valida credenciais contra `tenant.users` e emite JWT RS256.

    - 401 se e-mail/senha/tenant inválidos.
    - 503 se o backend de autenticação estiver indisponível (em produção).
    - Em dev/test sem DB, cai para um atalho de desenvolvimento (sem validação de
      senha) — NUNCA ativado em produção.
    """
    try:
        from services.gateway.auth.jwt import TOKEN_EXPIRY_SECONDS, issue_token
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de autenticação indisponível.",
        ) from None

    from services.gateway.auth.users import AuthBackendError, authenticate

    env = os.getenv("ENV", "production").strip().lower()

    try:
        user = authenticate(request.username, request.password, request.tenant_slug)
    except AuthBackendError:
        # DB indisponível: só em dev/test caímos para o atalho de desenvolvimento.
        if env not in _DEV_ENVS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend de autenticação indisponível.",
            ) from None
        user = _dev_fallback_user(request)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    token = issue_token(user_id=user.user_id, tenant_id=user.tenant_id, role=user.role)
    return TokenResponse(access_token=token, expires_in=TOKEN_EXPIRY_SECONDS)


def _dev_fallback_user(request: LoginRequest):
    """Usuário de desenvolvimento quando não há DB (apenas dev/test)."""
    from services.gateway.auth.users import AuthenticatedUser

    return AuthenticatedUser(
        user_id=request.username or "dev-user",
        tenant_id="00000000-0000-0000-0000-000000000001",  # dev-tenant
        tenant_slug=request.tenant_slug or "dev-tenant",
        tenant_name="Tenant de Desenvolvimento",
        email=request.username or "dev@dev",
        role="admin",
    )


@router.get(
    "/me",
    summary="Claims do usuário autenticado",
    description="Lê o JWT validado pelo middleware e devolve tenant_id/role para o frontend hidratar a sessão.",
    responses={401: {"description": "Não autenticado"}},
)
async def me(request: Request) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
        )
    return {
        "user_id": user_id,
        "tenant_id": getattr(request.state, "tenant_id", None),
        "role": getattr(request.state, "role", "viewer"),
    }
