"""Testes do núcleo puro do Chamber Profiler (services/chamber_profiler/profile.py)."""
from services.chamber_profiler import profile


def test_profile_pondera_por_volume():
    rows = [
        {"classe_tpu": "7", "n_processos": 100, "pct_provimento": 0.6,
         "taxa_congestionamento": 0.8, "duracao_mediana_dias": 800},
        {"classe_tpu": "1125", "n_processos": 900, "pct_provimento": 0.1,
         "taxa_congestionamento": 0.4, "duracao_mediana_dias": 300},
    ]
    p = profile.build_profile("tjsp", rows)
    assert p["tribunal"] == "TJSP"
    assert p["n_processos"] == 1000
    # média ponderada de provimento puxa para o segmento de 900 processos (0.1)
    assert p["perfil"]["provimento"]["valor"] < 0.25
    assert p["perfil"]["provimento"]["faixa"] == "BAIXO_PROVIMENTO"


def test_tiers_congestionamento_e_duracao():
    rows = [{"classe_tpu": "7", "n_processos": 10, "pct_provimento": 0.5,
             "taxa_congestionamento": 0.75, "duracao_mediana_dias": 730}]
    p = profile.build_profile("TJMG", rows)
    assert p["perfil"]["congestionamento"]["faixa"] == "MUITO_CONGESTIONADO"
    assert p["perfil"]["duracao_mediana_dias"]["faixa"] == "LENTO"
    assert p["perfil"]["provimento"]["faixa"] == "ALTO_PROVIMENTO"


def test_profile_sem_dados():
    p = profile.build_profile("TJRJ", [])
    assert p["n_processos"] == 0
    assert p["perfil"]["provimento"]["faixa"] == "SEM_DADOS"


def test_grao_documenta_limite_camara_vara():
    p = profile.build_profile("TJSP", [])
    assert p["grao"] == "tribunal+classe"
