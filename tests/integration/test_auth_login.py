"""
Integração: autenticação real contra tenant.users (P0-2).

Requer Postgres + DATABASE_URL e a migração 002 aplicada (cria password_hash e
semeia o usuário de desenvolvimento admin@dev.com / dev12345 no tenant
'dev-tenant'). Pula se o banco não estiver disponível.

    pytest -m integration tests/integration/test_auth_login.py
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlalchemy")

from services.gateway.auth.users import authenticate  # noqa: E402

pytestmark = pytest.mark.integration

DEV_EMAIL = "admin@dev.com"
DEV_PASSWORD = "dev12345"
DEV_TENANT = "dev-tenant"


@pytest.fixture(autouse=True)
def _require_db():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL não definido — integração pulada.")


def test_credenciais_validas_retornam_usuario():
    user = authenticate(DEV_EMAIL, DEV_PASSWORD, DEV_TENANT)
    assert user is not None
    assert user.email.lower() == DEV_EMAIL
    assert user.tenant_slug == DEV_TENANT
    assert user.role == "admin"
    assert user.tenant_id  # uuid resolvido


def test_senha_errada_retorna_none():
    assert authenticate(DEV_EMAIL, "senha-errada", DEV_TENANT) is None


def test_email_inexistente_retorna_none():
    assert authenticate("naoexiste@dev.com", DEV_PASSWORD, DEV_TENANT) is None


def test_tenant_inexistente_retorna_none():
    assert authenticate(DEV_EMAIL, DEV_PASSWORD, "tenant-fantasma") is None


def test_email_case_insensitive():
    assert authenticate(DEV_EMAIL.upper(), DEV_PASSWORD, DEV_TENANT) is not None


def test_campos_vazios_retornam_none():
    assert authenticate("", DEV_PASSWORD, DEV_TENANT) is None
    assert authenticate(DEV_EMAIL, "", DEV_TENANT) is None
    assert authenticate(DEV_EMAIL, DEV_PASSWORD, "") is None
