"""
Autenticação de usuário contra `tenant.users` (P0-2).

`authenticate(email, password, tenant_slug)`:
  - resolve o tenant pelo slug e o usuário pelo e-mail (ambos `active`);
  - valida a senha contra `password_hash` (PBKDF2, ver auth/password.py);
  - devolve `AuthenticatedUser` em sucesso, `None` em credencial inválida.

As tabelas `tenant.tenants`/`tenant.users` NÃO estão sob RLS e o `app_user` tem
SELECT nelas, então a consulta roda sem contexto de tenant (o login acontece
antes de haver tenant). Erros de backend (DB indisponível) viram `AuthBackendError`
para o router distinguir 401 (credencial) de 503 (infra).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from services.gateway.auth.password import verify_password


class AuthBackendError(RuntimeError):
    """Falha de infraestrutura ao autenticar (DB indisponível, etc.)."""


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    email: str
    role: str


_QUERY = text(
    """
    SELECT u.id::text          AS user_id,
           u.tenant_id::text   AS tenant_id,
           t.slug              AS tenant_slug,
           t.name              AS tenant_name,
           u.email             AS email,
           u.role              AS role,
           u.password_hash     AS password_hash
      FROM tenant.users u
      JOIN tenant.tenants t ON t.id = u.tenant_id
     WHERE t.slug = :slug
       AND lower(u.email) = lower(:email)
       AND u.active
       AND t.active
     LIMIT 1
    """
)


def authenticate(email: str, password: str, tenant_slug: str) -> AuthenticatedUser | None:
    """Valida credenciais. Retorna o usuário em sucesso ou None se inválido."""
    if not email or not password or not tenant_slug:
        return None

    try:
        from services.shared.tenant_db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                _QUERY, {"slug": tenant_slug, "email": email}
            ).mappings().first()
    except Exception as exc:  # conexão/engine/query — infra, não credencial
        raise AuthBackendError(str(exc)) from exc

    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None

    return AuthenticatedUser(
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        tenant_slug=row["tenant_slug"],
        tenant_name=row["tenant_name"],
        email=row["email"],
        role=row["role"],
    )
