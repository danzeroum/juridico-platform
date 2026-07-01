"""Testes do núcleo puro da rede de litigância (services/knowledge_graph/analysis.py)."""
from services.knowledge_graph import analysis


def test_classify_relationship_faixas():
    assert analysis.classify_relationship(0) == "ISOLADO"
    assert analysis.classify_relationship(1) == "ISOLADO"
    assert analysis.classify_relationship(2) == "OCASIONAL"
    assert analysis.classify_relationship(5) == "RECORRENTE"
    assert analysis.classify_relationship(20) == "PREDATORIO"
    assert analysis.classify_relationship(100) == "PREDATORIO"


def test_annotate_network_adiciona_relacao():
    rows = [{"cnpj": "1", "processos_em_comum": 25}, {"cnpj": "2", "processos_em_comum": 3}]
    out = analysis.annotate_network(rows)
    assert out[0]["relacao"] == "PREDATORIO"
    assert out[1]["relacao"] == "OCASIONAL"


def test_network_summary_distribuicao_e_flag_predatoria():
    rows = [
        {"cnpj": "1", "processos_em_comum": 30},
        {"cnpj": "2", "processos_em_comum": 6},
        {"cnpj": "3", "processos_em_comum": 1},
    ]
    s = analysis.network_summary(rows)
    assert s["n_vizinhos"] == 3
    assert s["distribuicao"]["PREDATORIO"] == 1
    assert s["distribuicao"]["RECORRENTE"] == 1
    assert s["distribuicao"]["ISOLADO"] == 1
    assert s["tem_litigancia_predatoria"] is True


def test_network_summary_vazio():
    s = analysis.network_summary([])
    assert s["n_vizinhos"] == 0
    assert s["tem_litigancia_predatoria"] is False
