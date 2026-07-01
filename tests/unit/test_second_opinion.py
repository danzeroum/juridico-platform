"""Testes do núcleo puro do Second Opinion Engine (services/second_opinion/consensus.py)."""
from services.second_opinion import consensus


def test_sem_sinais():
    assert consensus.synthesize_opinion()["status"] == "sem_sinais"


def test_consenso_favoravel_alta_concordancia():
    r = consensus.synthesize_opinion(legalscore=800, taxpredict_prob=0.8, pct_provimento=0.75)
    assert r["veredito"] == "FAVORAVEL"
    assert r["nivel_concordancia"] == "ALTA"
    assert r["n_sinais"] == 3


def test_baixa_concordancia_quando_sinais_divergem():
    r = consensus.synthesize_opinion(legalscore=900, taxpredict_prob=0.1, pct_provimento=0.5)
    assert r["nivel_concordancia"] == "BAIXA"


def test_um_sinal_sem_concordancia():
    r = consensus.synthesize_opinion(taxpredict_prob=0.3)
    assert r["nivel_concordancia"] == "UNICO_SINAL"
    assert r["concordancia"] is None
    assert r["veredito"] == "DESFAVORAVEL"


def test_favorabilidade_normaliza_legalscore():
    # legalscore 500/1000 = 0.5 favorabilidade
    r = consensus.synthesize_opinion(legalscore=500)
    assert r["sinais"]["legalscore"] == 0.5
