#!/usr/bin/env python3
"""
Runner de migrações de schema (idempotente).

Aplica, em ordem, os arquivos `scripts/migrations/NNN_*.sql` que ainda não foram
registrados em `public.schema_migrations`. Cada migração roda na sua própria
transação; uma falha aborta a migração sem registrá-la (as demais não rodam).

Conexão: usa `MIGRATIONS_DATABASE_URL` (ou `DATABASE_URL`). DDL exige conectar
como **owner do banco** (`POSTGRES_USER`), NÃO como `app_user`.

Uso:
    python scripts/migrate.py            # aplica as pendentes
    python scripts/migrate.py --status   # lista aplicadas/pendentes (não altera)

Idempotente: rodar duas vezes em sequência é seguro — a segunda é no-op.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

# sqlalchemy é importado de forma lazy dentro das funções que tocam o banco,
# para que discover()/checksum sejam usáveis (e testáveis) sem o driver.

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Tabela de controle + leitura para o app_user (versão de schema / health).
_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version     TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
DO $$ BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        GRANT SELECT ON public.schema_migrations TO app_user;
    END IF;
END $$;
"""


def _db_url() -> str:
    url = os.getenv("MIGRATIONS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        sys.exit("Defina MIGRATIONS_DATABASE_URL (admin) ou DATABASE_URL.")
    return url


def discover(migrations_dir: Path = MIGRATIONS_DIR) -> list[tuple[str, str, str]]:
    """Devolve (version, sql, checksum) ordenado por nome do arquivo."""
    out: list[tuple[str, str, str]] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        out.append((path.stem, sql, checksum))
    return out


def _ensure_control_table(engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(_BOOTSTRAP_SQL)


def _applied(engine) -> dict[str, str]:
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT version, checksum FROM public.schema_migrations")
        ).all()
    return {version: checksum for version, checksum in rows}


def run(status_only: bool = False, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    from sqlalchemy import create_engine, text

    engine = create_engine(_db_url(), future=True)
    _ensure_control_table(engine)
    applied = _applied(engine)
    migrations = discover(migrations_dir)
    pending = [(v, sql, c) for (v, sql, c) in migrations if v not in applied]

    # Aviso (não bloqueia): migração já aplicada cujo arquivo mudou depois.
    for version, _sql, checksum in migrations:
        if version in applied and applied[version] != checksum:
            print(f"AVISO: {version} aplicada com checksum diferente (arquivo alterado após aplicar).")

    if status_only:
        for version, _sql, _c in migrations:
            print(f"  {'✓' if version in applied else '·'} {version}")
        print(f"{len(applied)} aplicada(s), {len(pending)} pendente(s).")
        return 0

    if not pending:
        print("Nenhuma migração pendente.")
        return 0

    for version, sql, checksum in pending:
        print(f"Aplicando {version} …")
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
            conn.execute(
                text("INSERT INTO public.schema_migrations (version, checksum) VALUES (:v, :c)"),
                {"v": version, "c": checksum},
            )
        print(f"  ✓ {version}")

    print(f"{len(pending)} migração(ões) aplicada(s).")
    return 0


if __name__ == "__main__":
    sys.exit(run(status_only="--status" in sys.argv))
