"""
Testes da camada de pseudonimização LGPD.

Critérios de aceite da Fase 0:
- Mesmo CPF + mesma chave → mesmo hash (determinístico, permite join interno).
- Chave rotacionada → hash diferente (separação de datasets).
- Hash não derivável do SHA-256 puro do CPF sem a chave.
"""
import hashlib
import os
import re

import pytest


@pytest.fixture(autouse=True)
def set_hmac_key(monkeypatch):
    """Injetar chave HMAC de teste via variável de ambiente."""
    monkeypatch.setenv("HMAC_KEY", "a" * 64)
    # Resetar cache da chave entre testes
    import services.shared.lgpd as lgpd_mod
    lgpd_mod._HMAC_KEY = None
    yield
    lgpd_mod._HMAC_KEY = None


def test_hash_cpf_deterministico():
    from services.shared.lgpd import hash_cpf
    h1 = hash_cpf("123.456.789-09")
    h2 = hash_cpf("12345678909")
    assert h1 == h2, "Mesmo CPF (com/sem formatação) deve gerar o mesmo hash"


def test_hash_cpf_mesma_chave_mesmo_resultado():
    from services.shared.lgpd import hash_cpf
    h1 = hash_cpf("12345678909")
    h2 = hash_cpf("12345678909")
    assert h1 == h2


def test_hash_cpf_diferente_cpf_diferente_hash():
    from services.shared.lgpd import hash_cpf
    assert hash_cpf("12345678909") != hash_cpf("98765432100")


def test_hash_cpf_64_chars():
    from services.shared.lgpd import hash_cpf
    h = hash_cpf("12345678909")
    assert len(h) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", h), "Deve ser hex lowercase sem truncamento"


def test_hash_cpf_chave_diferente_hash_diferente(monkeypatch):
    """Chave rotacionada produz hash diferente — requisito de separação de dados."""
    import services.shared.lgpd as lgpd_mod

    monkeypatch.setenv("HMAC_KEY", "a" * 64)
    lgpd_mod._HMAC_KEY = None
    from services.shared.lgpd import hash_cpf
    h1 = hash_cpf("12345678909")

    monkeypatch.setenv("HMAC_KEY", "b" * 64)
    lgpd_mod._HMAC_KEY = None
    h2 = hash_cpf("12345678909")

    assert h1 != h2, "Chave diferente deve produzir hash diferente"


def test_hash_nao_e_sha256_puro():
    """Hash não deve ser derivável de SHA-256 puro do CPF (sem a chave)."""
    from services.shared.lgpd import hash_cpf
    cpf = "12345678909"
    sha256_puro = hashlib.sha256(cpf.encode()).hexdigest()
    assert hash_cpf(cpf) != sha256_puro, "HMAC deve diferir de SHA-256 sem chave"


def test_pseudonymize_process_record_remove_pii():
    from services.shared.lgpd import pseudonymize_process_record
    record = {
        "numero_processo": "0000001-00.2020.8.26.0001",
        "cnpj": "12345678000195",
        "parte_cpf": "12345678909",
        "parte_nome": "João Silva",
        "endereco": "Rua Exemplo, 123",
        "cep": "01001-000",
    }
    safe = pseudonymize_process_record(record)
    assert "parte_cpf" not in safe, "CPF em claro não deve persistir"
    assert "parte_nome" not in safe, "Nome em claro não deve persistir"
    assert "endereco" not in safe, "Endereço deve ser removido"
    assert "cep" not in safe, "CEP deve ser removido"
    assert "parte_cpf_hash" in safe, "Hash do CPF deve estar presente"
    assert "parte_nome_hash" in safe, "Hash do nome deve estar presente"
    assert safe["cnpj"] == "12345678000195", "CNPJ (dado público) deve ser mantido"
    assert safe["numero_processo"] == "0000001-00.2020.8.26.0001"


def test_k_anonymize():
    from services.shared.lgpd import k_anonymize
    records = [
        {"uf": "SP", "faixa_etaria": "30-40"},
        {"uf": "SP", "faixa_etaria": "30-40"},
        {"uf": "SP", "faixa_etaria": "30-40"},
        {"uf": "SP", "faixa_etaria": "30-40"},
        {"uf": "SP", "faixa_etaria": "30-40"},
        {"uf": "RJ", "faixa_etaria": "20-30"},  # grupo de 1 → suprimido
    ]
    result = k_anonymize(records, ["uf", "faixa_etaria"], k=5)
    assert len(result) == 5
    assert all(r["uf"] == "SP" for r in result)


def test_hmac_key_obrigatoria(monkeypatch):
    import services.shared.lgpd as lgpd_mod
    monkeypatch.setenv("HMAC_KEY", "")
    lgpd_mod._HMAC_KEY = None
    with pytest.raises(RuntimeError, match="HMAC_KEY"):
        from services.shared.lgpd import hash_cpf
        hash_cpf("12345678909")
