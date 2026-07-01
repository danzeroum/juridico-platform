"""Testes do núcleo puro de agregação jurimétrica (build_indicador_rows)."""
from services.ingest.tasks.jurimetria_aggregate import build_indicador_rows


def test_datajud_puro_gera_linha_datajud():
    buckets = [{"tribunal": "TJSP", "classe_tpu": "7", "assunto_tpu": "899",
                "periodo": "TODOS", "n_processos": 10, "pct_provimento": 0.4}]
    rows = build_indicador_rows(buckets, [])
    assert len(rows) == 1
    r = rows[0]
    assert r["fonte"] == "DATAJUD"
    assert r["n_processos"] == 10
    assert r["pct_provimento"] == 0.4
    assert r["duracao_mediana_dias"] is None  # DATAJUD não tem duração


def test_blend_combina_volume_datajud_com_duracao_abj():
    buckets = [{"tribunal": "TJSP", "classe_tpu": "7", "assunto_tpu": "899",
                "periodo": "TODOS", "n_processos": 10, "pct_provimento": 0.4}]
    abj = [{"tribunal": "TJSP", "classe_cnj": "7", "assunto_cnj": "899",
            "periodo": "TODOS", "tempo_medio_dias": 540, "taxa_congestionamento": 0.6,
            "casos_novos": 100}]
    rows = build_indicador_rows(buckets, abj)
    fontes = {r["fonte"] for r in rows}
    assert fontes == {"DATAJUD", "BLEND"}
    blend = next(r for r in rows if r["fonte"] == "BLEND")
    assert blend["n_processos"] == 10          # volume do DATAJUD
    assert blend["duracao_mediana_dias"] == 540  # duração da ABJ
    assert blend["taxa_congestionamento"] == 0.6


def test_abj_sem_correspondente_entra_como_abj():
    abj = [{"tribunal": "TJMG", "classe_cnj": "1", "assunto_cnj": "2",
            "periodo": "2024", "tempo_medio_dias": 300, "casos_pendentes": 50}]
    rows = build_indicador_rows([], abj)
    assert len(rows) == 1
    assert rows[0]["fonte"] == "ABJ"
    assert rows[0]["n_processos"] == 50


def test_chaves_divergentes_nao_fazem_blend():
    buckets = [{"tribunal": "TJSP", "classe_tpu": "7", "assunto_tpu": "899",
                "periodo": "TODOS", "n_processos": 10, "pct_provimento": None}]
    abj = [{"tribunal": "TJRJ", "classe_cnj": "7", "assunto_cnj": "899",
            "periodo": "TODOS", "tempo_medio_dias": 400}]
    rows = build_indicador_rows(buckets, abj)
    assert {r["fonte"] for r in rows} == {"DATAJUD", "ABJ"}
