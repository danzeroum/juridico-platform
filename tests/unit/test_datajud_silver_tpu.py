"""Testes da normalização TPU no transform silver do DATAJUD (quality.py)."""
from services.ingest.pipeline.quality import datajud_bronze_to_silver


def test_silver_enriquece_classe_assunto_ramo():
    bronze = {
        "id_processo": "P1",
        "classe": "1125",
        "assunto": "1937",
        "data_julgamento": "2024-05-01",
        "ingested_at": "2024-05-02T00:00:00Z",
        "transform_version": "1.0.0",
    }
    pseudo = {
        "id_processo": "P1",
        "tribunal": "TJSP",
        "cnpj_parte": "11222333000181",
        "data_julgamento": "2024-05-01",
        "valor_causa": 1000.0,
    }
    silver = datajud_bronze_to_silver(bronze, pseudo)
    assert silver["classe_tpu"] == "1125"
    assert silver["classe_label"] is not None
    assert silver["assunto_tpu"] == "1937"
    assert silver["ramo"] == "TRABALHISTA"
    # preserva campos existentes do silver
    assert silver["cnpj_parte"] == "11222333000181"
    assert silver["valor_log"] > 0


def test_silver_ramo_outro_para_assunto_desconhecido():
    bronze = {"id_processo": "P2", "classe": "7", "assunto": "0000",
              "data_julgamento": "2024-01-01"}
    pseudo = {"id_processo": "P2", "tribunal": "TJRJ", "data_julgamento": "2024-01-01"}
    silver = datajud_bronze_to_silver(bronze, pseudo)
    assert silver["ramo"] == "OUTRO"
    assert silver["assunto_tpu"] == "0000"
    assert silver["assunto_label"] is None
