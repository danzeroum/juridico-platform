"""Testes da normalização TPU (services/shared/tpu.py)."""
from services.shared import tpu


def test_normalize_classe_conhecida():
    code, label = tpu.normalize_classe("1125")
    assert code == "1125"
    assert label and "Recupera" in label


def test_normalize_classe_com_formatacao():
    # aceita código com ruído não-numérico
    code, label = tpu.normalize_classe(" 1125 ")
    assert code == "1125"
    assert label is not None


def test_normalize_classe_desconhecida_preserva_codigo():
    code, label = tpu.normalize_classe("999999")
    assert code == "999999"
    assert label is None


def test_normalize_classe_none():
    assert tpu.normalize_classe(None) == (None, None)


def test_normalize_assunto_e_ramo_trabalhista():
    code, label = tpu.normalize_assunto("1937")
    assert code == "1937"
    assert label is not None
    assert tpu.assunto_ramo("1937") == "TRABALHISTA"


def test_ramo_sobe_hierarquia_ate_raiz():
    # 5952 (ICMS) → pai 899 (DIREITO TRIBUTÁRIO) tem ramo TRIBUTARIO
    assert tpu.assunto_ramo("5952") == "TRIBUTARIO"


def test_ramo_desconhecido_e_outro():
    assert tpu.assunto_ramo("0000") == "OUTRO"
    assert tpu.assunto_ramo(None) == "OUTRO"


def test_classe_hierarchy_root_only():
    # classes-semente não têm parent → caminho é só o próprio código
    assert tpu.classe_hierarchy("7") == ["7"]
