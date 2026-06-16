"""
Auth router — emissão de JWT RS256.

POST /api/v1/auth/token  → token de acesso (Bearer JWT RS256)
GET  /.well-known/jwks.json → servido em main.py diretamente
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
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
    Emite JWT RS256 para autenticação.

    Em desenvolvimento, aceita qualquer credencial com tenant_slug "dev-tenant".
    Em produção, validar contra a tabela tenant.users.
    """
    try:
        from services.gateway.auth.jwt import issue_token, TOKEN_EXPIRY_SECONDS
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de autenticação indisponível.",
        )

    # TODO (Fase 1): validar request.username + request.password contra tenant.users
    # Por ora: aceitar dev-tenant sem validação de senha (SOMENTE em dev)
    import os
    if os.getenv("ENV", "dev") != "dev" and request.tenant_slug == "dev-tenant":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    # Em produção: buscar tenant_id do DB pelo slug
    tenant_id = "00000000-0000-0000-0000-000000000001"  # dev tenant

    token = issue_token(
        user_id=request.username,
        tenant_id=tenant_id,
        role="analyst",
    )
    return TokenResponse(access_token=token, expires_in=TOKEN_EXPIRY_SECONDS)
