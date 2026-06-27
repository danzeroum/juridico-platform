"""Testes do hashing de senha PBKDF2 (stdlib, sem dependências)."""
from __future__ import annotations

from services.gateway.auth.password import hash_password, verify_password

# Hash semeado pela migração 002 (senha: dev12345). Mantém o teste como guarda
# contra mudanças acidentais no formato/iterações que invalidariam o seed.
SEEDED_HASH = (
    "pbkdf2_sha256$600000$g9gLadCiKMaLDkcSM5KIbg=="
    "$9d2VPknk/IesKc65jhIbV9KIvkm+9zyFd/YICkX9CXM="
)


def test_roundtrip():
    h = hash_password("s3nha-forte")
    assert verify_password("s3nha-forte", h)


def test_rejeita_senha_errada():
    h = hash_password("correta")
    assert not verify_password("errada", h)


def test_salt_aleatorio_por_senha():
    # Mesma senha → hashes diferentes (salt distinto), ambos válidos.
    a = hash_password("igual")
    b = hash_password("igual")
    assert a != b
    assert verify_password("igual", a)
    assert verify_password("igual", b)


def test_formato_armazenado():
    h = hash_password("x", iterations=120_000)
    algo, iters, salt_b64, hash_b64 = h.split("$")
    assert algo == "pbkdf2_sha256"
    assert iters == "120000"
    assert salt_b64 and hash_b64


def test_falha_fechado_em_entrada_invalida():
    assert not verify_password("x", None)
    assert not verify_password("x", "")
    assert not verify_password("x", "lixo")
    assert not verify_password("x", "pbkdf2_sha256$naoeinteiro$a$b")
    assert not verify_password("", hash_password("nao-vazia"))


def test_seed_da_migracao_confere():
    assert verify_password("dev12345", SEEDED_HASH)
    assert not verify_password("dev1234", SEEDED_HASH)
