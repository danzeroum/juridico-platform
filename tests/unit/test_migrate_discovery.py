"""Testes da descoberta de migrações do runner (sem DB)."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "migrate", Path(__file__).resolve().parents[2] / "scripts" / "migrate.py"
)
migrate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(migrate)


def test_discover_ordena_por_nome(tmp_path):
    (tmp_path / "002_b.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "010_c.sql").write_text("SELECT 10;", encoding="utf-8")
    versions = [v for v, _sql, _c in migrate.discover(tmp_path)]
    assert versions == ["001_a", "002_b", "010_c"]


def test_discover_calcula_checksum_sha256(tmp_path):
    (tmp_path / "001_x.sql").write_text("SELECT 42;", encoding="utf-8")
    [(version, sql, checksum)] = migrate.discover(tmp_path)
    assert version == "001_x"
    assert sql == "SELECT 42;"
    assert checksum == hashlib.sha256(b"SELECT 42;").hexdigest()


def test_discover_ignora_nao_sql(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "README.md").write_text("nada", encoding="utf-8")
    assert [v for v, *_ in migrate.discover(tmp_path)] == ["001_a"]


def test_migracoes_reais_sao_descobertas():
    # As migrações versionadas do repo devem ser visíveis e em ordem.
    versions = [v for v, *_ in migrate.discover()]
    assert "001_ledger_entry_index_unique_and_anchors_rls" in versions
    assert "002_users_password_and_auth" in versions
    assert versions == sorted(versions)
