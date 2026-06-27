"""
Integração: o runner de migrações registrou as migrações em schema_migrations.

O job de CI aplica as migrações com o runner (como owner) antes de rodar os
testes. Aqui validamos, como app_user, que a tabela de controle existe, que as
migrações versionadas estão registradas e legíveis pelo app_user.

    pytest -m integration tests/integration/test_migrations.py
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL não definido — integração pulada.")
    return create_engine(url, future=True)


def test_tabela_de_controle_existe_e_legivel(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT version FROM public.schema_migrations ORDER BY version")
        ).all()
    versions = {r[0] for r in rows}
    assert "001_ledger_entry_index_unique_and_anchors_rls" in versions
    assert "002_users_password_and_auth" in versions


def test_checksum_registrado(engine):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT checksum FROM public.schema_migrations "
                "WHERE version = '002_users_password_and_auth'"
            )
        ).first()
    assert row is not None
    assert len(row[0]) == 64  # sha256 hex
