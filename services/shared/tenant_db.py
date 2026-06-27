"""
Helper de conexão com isolamento de tenant (RLS + PgBouncer transaction pooling).

Este módulo fornece o `tenant_transaction(tenant_id)` que o middleware do gateway
referencia (como `get_db_connection`) mas que ainda não existia em
`services/shared/db.py`. Sem ele, as policies RLS do `bootstrap-db.sql` ficam sem
quem defina o GUC `app.tenant_id` por request — e, como a policy usa
`current_setting('app.tenant_id')` SEM `missing_ok`, qualquer query sem o GUC
**falha fechada** (erro), não vaza. Este helper é o que torna a aplicação
funcional E isolada.

Por que `SET LOCAL` (e não `SET`):
    Em PgBouncer `pool_mode=transaction`, a conexão de servidor é reutilizada entre
    tenants entre transações. Um `SET` de sessão persiste na conexão e vaza para o
    próximo tenant; `SET LOCAL` (revertido no COMMIT/ROLLBACK) não.

Por que `set_config(name, value, is_local=true)` e não `SET LOCAL ... = :tid`:
    `SET` não aceita parâmetro de bind — construir a string com o tenant_id abriria
    risco de injeção. `set_config('app.tenant_id', :tid, true)` é o equivalente
    PARAMETRIZÁVEL e injection-safe de `SET LOCAL`.

Uso:
    from services.shared.tenant_db import tenant_transaction
    from sqlalchemy import text

    with tenant_transaction(tenant_id) as conn:
        rows = conn.execute(
            text("SELECT request_id FROM ledger.entries")
        ).all()
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    """
    Reutiliza o engine do app se disponível; senão, cria a partir de DATABASE_URL.
    DATABASE_URL deve apontar para o PgBouncer (porta 6432), nunca direto ao Postgres.
    """
    try:
        from services.shared.db import engine as app_engine  # type: ignore

        return app_engine
    except Exception:
        dsn = os.environ["DATABASE_URL"]
        return create_engine(dsn, pool_pre_ping=True, future=True)


@contextmanager
def tenant_transaction(tenant_id: str) -> Iterator[Connection]:
    """
    Abre `BEGIN; set_config('app.tenant_id', :tid, true); <queries>; COMMIT`.

    Tudo o que rodar dentro do `with` enxerga apenas as linhas do tenant. No fim
    do bloco a transação faz COMMIT (ou ROLLBACK em exceção) e o GUC é revertido
    automaticamente — seguro para reuso da conexão pelo PgBouncer.
    """
    if not tenant_id:
        # Fail-closed também no nível da aplicação: sem tenant não há transação.
        raise ValueError("tenant_id é obrigatório (RLS é fail-closed).")

    engine = _get_engine()
    with engine.begin() as conn:  # BEGIN ... COMMIT/ROLLBACK automático
        conn.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        yield conn


# Nome alternativo referenciado pelo docstring do middleware do gateway.
get_db_connection = tenant_transaction


def get_engine() -> Engine:
    """
    Engine compartilhado (sem contexto de tenant). Para uso em queries que NÃO
    estão sob RLS — ex.: autenticação contra tenant.tenants/tenant.users, que o
    app_user pode ler diretamente. Queries sob RLS DEVEM usar tenant_transaction.
    """
    return _get_engine()
