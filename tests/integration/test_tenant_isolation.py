"""
Teste de isolamento de tenant (RLS + PgBouncer transaction pooling).

Critério de aceite da Fase 0:
    "teste de isolamento que exercita REUSO DE CONEXÃO SOB CONCORRÊNCIA — dois
     tenants em threads paralelas; confirmar que A nunca lê dados de B mesmo quando
     as conexões são reutilizadas. Teste sequencial simples não é suficiente."

Este arquivo cobre quatro coisas:
  1. Isolamento sob concorrência através do helper `tenant_transaction` (exercita
     reuso de conexão do pool).
  2. Fail-closed: query sem o GUC de tenant levanta erro (não vaza).
  3. Mecanismo: prova determinística de que `set_config(...,true)` (= SET LOCAL)
     NÃO persiste entre transações, enquanto `SET` de sessão persiste (vazaria).
  4. Metadado: as tabelas reais (ledger.entries, tenant.idempotency_keys) têm RLS
     e FORCE RLS habilitados.

Requer Postgres + PgBouncer no ar e DATABASE_URL apontando para o PgBouncer (6432).
Marcado como integração; pula se o banco não estiver disponível.

    pytest -m integration tests/integration/test_tenant_isolation.py
"""
from __future__ import annotations

import os
import threading
import uuid

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import text  # noqa: E402

pytestmark = pytest.mark.integration

TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"

PROBE_DDL = """
CREATE TABLE IF NOT EXISTS public.tenant_isolation_probe (
    id        uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    payload   text NOT NULL
);
ALTER TABLE public.tenant_isolation_probe ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_isolation_probe FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS probe_isolation ON public.tenant_isolation_probe;
CREATE POLICY probe_isolation ON public.tenant_isolation_probe
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


def _engine():
    if not os.getenv("DATABASE_URL"):
        pytest.skip(
        "DATABASE_URL não definido — em dev: pgbouncer:6432; em CI: postgres:5432 como app_user."
    )
    from services.shared.tenant_db import _get_engine

    eng = _get_engine()
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - ambiente sem DB
        pytest.skip(f"Postgres/PgBouncer indisponível: {exc}")
    return eng


@pytest.fixture(scope="module")
def engine():
    eng = _engine()
    from services.shared.tenant_db import tenant_transaction

    # Em CI, bootstrap-db.sql cria a tabela antes dos testes — pular DDL se já existe.
    # Em dev com POSTGRES_USER, tenta criar; com app_user (sem DDL), pula e falha
    # com mensagem clara.
    with eng.connect() as conn:
        table_exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'tenant_isolation_probe'"
            )
        ).scalar()

    if not table_exists:
        try:
            with eng.begin() as conn:
                for stmt in filter(None, (s.strip() for s in PROBE_DDL.split(";"))):
                    conn.execute(text(stmt))
        except Exception as exc:
            pytest.skip(
                f"Tabela-sonda ausente e sem privilégio DDL: {exc}. "
                "Em CI: verifique que bootstrap-db.sql foi executado antes dos testes. "
                "Em dev: conecte como POSTGRES_USER para criar a tabela uma vez."
            )

    # Seed: limpa dados anteriores e insere 5 linhas por tenant.
    # DELETE antes do INSERT: idempotente entre re-runs sem DROP TABLE.
    for tenant in (TENANT_A, TENANT_B):
        with tenant_transaction(tenant) as conn:
            conn.execute(
                text("DELETE FROM public.tenant_isolation_probe WHERE tenant_id = :tid"),
                {"tid": tenant},
            )
            for i in range(5):
                conn.execute(
                    text(
                        "INSERT INTO public.tenant_isolation_probe (id, tenant_id, payload) "
                        "VALUES (:id, :tid, :p)"
                    ),
                    {"id": str(uuid.uuid4()), "tid": tenant, "p": f"{tenant[-1]}-{i}"},
                )
    yield eng

    # Teardown: DELETE em vez de DROP — funciona com app_user (sem DDL privileges).
    # A tabela persiste em dev (idempotência acima garante dados frescos por run).
    try:
        for tenant in (TENANT_A, TENANT_B):
            with tenant_transaction(tenant) as conn:
                conn.execute(
                    text("DELETE FROM public.tenant_isolation_probe WHERE tenant_id = :tid"),
                    {"tid": tenant},
                )
    except Exception:
        pass


def _read_tenant_ids(tenant: str) -> set[str]:
    from services.shared.tenant_db import tenant_transaction

    with tenant_transaction(tenant) as conn:
        rows = conn.execute(
            text("SELECT tenant_id FROM public.tenant_isolation_probe")
        ).all()
    return {str(r[0]) for r in rows}


def test_isolamento_basico(engine):
    """Cada tenant só enxerga as próprias linhas."""
    assert _read_tenant_ids(TENANT_A) == {TENANT_A}
    assert _read_tenant_ids(TENANT_B) == {TENANT_B}


def test_isolamento_sob_concorrencia_e_reuso_de_pool(engine):
    """
    O teste que importa: dois tenants em muitas threads paralelas, forçando reuso
    das conexões do pool entre tenants diferentes. Se alguém usasse `SET` (sem
    LOCAL), o GUC vazaria entre conexões reutilizadas e uma thread veria o tenant
    errado. Com `set_config(...,true)`, nunca vaza.
    """
    leaks: list[str] = []
    barrier = threading.Barrier(20)

    def worker(tenant: str) -> None:
        barrier.wait()  # maximiza contenção/reuso simultâneo do pool
        for _ in range(50):
            seen = _read_tenant_ids(tenant)
            if seen - {tenant}:
                leaks.append(f"tenant {tenant} viu {seen - {tenant}}")

    threads = [
        threading.Thread(target=worker, args=(TENANT_A if i % 2 == 0 else TENANT_B,))
        for i in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not leaks, f"VAZAMENTO de tenant detectado: {leaks[:5]}"


def test_fail_closed_sem_tenant(engine):
    """
    Sem o GUC definido, a policy usa current_setting SEM missing_ok → erro.
    Confirma que a ausência de tenant FALHA FECHADA (não retorna linhas).
    """
    from sqlalchemy.exc import DBAPIError

    with pytest.raises((DBAPIError, Exception)):
        with engine.begin() as conn:  # transação sem set_config('app.tenant_id', ...)
            conn.execute(
                text("SELECT count(*) FROM public.tenant_isolation_probe")
            ).all()


def test_set_local_nao_vaza_mas_set_de_sessao_vaza(engine):
    """
    Prova determinística (numa única conexão física) de POR QUE SET LOCAL é
    obrigatório com PgBouncer transaction pooling:
      - set_config(...,true) (= SET LOCAL) é revertido após o COMMIT.
      - SET de sessão persiste entre transações → vazaria para o próximo tenant.
    """
    with engine.connect() as conn:
        # (1) SET LOCAL via set_config(...,true): não sobrevive ao COMMIT.
        with conn.begin():
            conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": TENANT_A})
            val = conn.execute(text("SELECT current_setting('app.tenant_id', true)")).scalar()
            assert val == TENANT_A
        # nova transação na MESMA conexão: GUC já não está mais definido
        with conn.begin():
            val_after = conn.execute(
                text("SELECT current_setting('app.tenant_id', true)")
            ).scalar()
        assert val_after in (None, ""), (
            "set_config(...,true) deveria ter sido revertido no COMMIT"
        )

        # (2) SET de sessão (is_local=false): PERSISTE → demonstra o vazamento.
        with conn.begin():
            conn.execute(text("SELECT set_config('app.tenant_id', :t, false)"), {"t": TENANT_B})
        with conn.begin():
            leaked = conn.execute(
                text("SELECT current_setting('app.tenant_id', true)")
            ).scalar()
        assert leaked == TENANT_B, (
            "SET de sessão persistiu entre transações — é exatamente o vazamento "
            "que o uso de SET LOCAL/set_config(...,true) evita."
        )
        # limpar para não contaminar a conexão
        conn.exec_driver_sql("RESET app.tenant_id")


@pytest.mark.parametrize(
    "schema,table",
    [("ledger", "entries"), ("tenant", "idempotency_keys")],
)
def test_tabelas_reais_tem_rls_e_force(engine, schema, table):
    """As tabelas reais com dados de cliente têm RLS e FORCE RLS habilitados."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT c.relrowsecurity, c.relforcerowsecurity "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = :s AND c.relname = :t"
            ),
            {"s": schema, "t": table},
        ).first()
    if row is None:
        pytest.skip(f"{schema}.{table} ausente neste banco.")
    assert row[0] is True, f"RLS não habilitado em {schema}.{table}"
    assert row[1] is True, f"FORCE RLS não habilitado em {schema}.{table}"
