"""
Integração do schema `fiscal`: seed, integridade temporal (EXCLUDE), RLS.

Requer Postgres com a migração 003 aplicada e o seed rodado (CI faz ambos).
Marcado como integração; pula se o banco não estiver disponível.

    pytest -m integration tests/integration/test_fiscal_schema.py
"""
from __future__ import annotations

import os

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import text  # noqa: E402

pytestmark = pytest.mark.integration


def _engine():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL não definido.")
    from services.shared.tenant_db import _get_engine

    eng = _get_engine()
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Postgres indisponível: {exc}")
    return eng


@pytest.fixture(scope="module")
def engine():
    eng = _engine()
    with eng.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'fiscal' AND table_name = 'icms_interno'"
            )
        ).scalar()
    if not exists:
        pytest.skip("Schema fiscal ausente — rode scripts/migrate.py.")
    return eng


class TestSeed:
    def test_interestadual_sp_ba_7pct(self, engine):
        with engine.connect() as conn:
            pct = conn.execute(
                text(
                    "SELECT aliquota_pct FROM fiscal.icms_interestadual "
                    "WHERE uf_origem='SP' AND uf_destino='BA' AND importado=FALSE "
                    "AND vigencia @> CURRENT_DATE"
                )
            ).scalar()
        if pct is None:
            pytest.skip("Seed não aplicado (scripts/seed_fiscal.py).")
        assert float(pct) == 7.0

    def test_interestadual_sp_rj_12pct(self, engine):
        with engine.connect() as conn:
            pct = conn.execute(
                text(
                    "SELECT aliquota_pct FROM fiscal.icms_interestadual "
                    "WHERE uf_origem='SP' AND uf_destino='RJ' AND vigencia @> CURRENT_DATE"
                )
            ).scalar()
        if pct is None:
            pytest.skip("Seed não aplicado.")
        assert float(pct) == 12.0

    def test_rj_interno_tem_fcp(self, engine):
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT aliquota_pct, fcp_pct FROM fiscal.icms_interno "
                    "WHERE uf='RJ' AND ncm_prefix IS NULL AND vigencia @> CURRENT_DATE"
                )
            ).fetchone()
        if row is None:
            pytest.skip("Seed não aplicado.")
        assert float(row[0]) == 18.0
        assert float(row[1]) == 2.0  # FECP → efetiva 20%


class TestIntegridadeTemporal:
    def test_exclude_impede_vigencia_sobreposta(self, engine):
        """Duas vigências abertas para o mesmo (uf, prefix) devem violar o EXCLUDE.

        Os inserts ficam em transações separadas: um IntegrityError aborta a
        transação corrente, então tentar as duas na mesma transação quebraria o
        COMMIT em vez de exercitar o constraint.
        """
        from sqlalchemy.exc import IntegrityError

        ins = (
            "INSERT INTO fiscal.icms_interno (uf, ncm_prefix, aliquota_pct, source) "
            "VALUES ('ZZ', NULL, :a, 'TEST')"
        )
        try:
            with engine.begin() as conn:
                conn.execute(text(ins), {"a": 10.0})  # primeira vigência aberta: OK
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:
                    conn.execute(text(ins), {"a": 12.0})  # sobreposição → viola EXCLUDE
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM fiscal.icms_interno WHERE source='TEST'"))


class TestRls:
    def test_triage_tables_tem_force_rls(self, engine):
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname IN ('triage_job','triage_item')"
                )
            ).fetchall()
        by_name = {r[0]: (r[1], r[2]) for r in rows}
        assert by_name.get("triage_job") == (True, True)
        assert by_name.get("triage_item") == (True, True)

    def test_select_sem_tenant_falha_closed(self, engine):
        """Sem app.tenant_id setado, a policy não resolve o GUC → query falha (não vaza)."""
        from sqlalchemy.exc import DBAPIError

        with engine.connect() as conn:
            with pytest.raises(DBAPIError):
                conn.execute(text("SELECT * FROM fiscal.triage_item")).fetchall()
