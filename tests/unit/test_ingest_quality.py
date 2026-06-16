"""
Testes de qualidade do pipeline bronze→silver (services/ingest/pipeline/quality.py).

Cobre tratamento de faltantes, outliers de higiene, normalização e transforms
de cada fonte (DATAJUD, PGFN, Receita).
"""
from __future__ import annotations

from services.ingest.pipeline.quality import (
    add_recencia,
    add_valor_log,
    datajud_bronze_to_silver,
    normalize_cnpj_part,
    pgfn_bronze_to_silver,
    receita_bronze_to_silver,
    remove_outliers_valor,
    treat_missing_valor_causa,
)


class TestTreatMissingValorCausa:
    def test_valor_presente_nao_imputa(self):
        r = treat_missing_valor_causa({"valor_causa": 5000.0})
        assert r["valor_causa"] == 5000.0
        assert r["valor_causa_imputado"] is False

    def test_valor_ausente_imputa_zero(self):
        r = treat_missing_valor_causa({})
        assert r["valor_causa"] == 0.0
        assert r["valor_causa_imputado"] is True


class TestRemoveOutliersValor:
    def test_valor_normal_nao_removido(self):
        r = remove_outliers_valor({"valor_causa": 50_000.0})
        assert r["valor_causa"] == 50_000.0
        assert r["valor_causa_outlier"] is False

    def test_valor_acima_do_limite_removido(self):
        r = remove_outliers_valor({"valor_causa": 2e12})
        assert r["valor_causa"] is None
        assert r["valor_causa_outlier"] is True

    def test_valor_nulo_nao_removido(self):
        r = remove_outliers_valor({"valor_causa": None})
        assert r["valor_causa_outlier"] is False


class TestAddValorLog:
    def test_log_de_valor_positivo(self):
        r = add_valor_log({"valor_causa": 1000.0})
        assert r["valor_log"] > 0

    def test_log_de_valor_nulo_retorna_zero(self):
        r = add_valor_log({"valor_causa": None})
        assert r["valor_log"] == 0.0


class TestAddRecencia:
    def test_data_valida_calcula_recencia(self):
        r = add_recencia({"data_julgamento": "2020-01-01"})
        assert r["recencia_dias"] > 0
        assert r["recencia"] < 0  # negativo: mais antigo = valor menor

    def test_data_ausente_retorna_zero(self):
        r = add_recencia({})
        assert r["recencia_dias"] is None
        assert r["recencia"] == 0.0

    def test_data_invalida_retorna_zero(self):
        r = add_recencia({"data_julgamento": "nao-e-data"})
        assert r["recencia_dias"] is None
        assert r["recencia"] == 0.0

    def test_campo_customizado(self):
        r = add_recencia({"data_decisao": "2022-06-01"}, date_field="data_decisao")
        assert r["recencia_dias"] > 0


class TestNormalizeCnpjPart:
    def test_cnpj_valido_normalizado(self):
        r = normalize_cnpj_part({"cnpj": "12.345.678/0001-95"})
        assert r["cnpj"] == "12345678000195"

    def test_cnpj_com_menos_de_14_digitos_vira_none(self):
        r = normalize_cnpj_part({"cnpj": "123"})
        assert r["cnpj"] is None

    def test_cnpj_parte_normalizado(self):
        r = normalize_cnpj_part({"cnpj_parte": "98.765.432/0001-10"})
        assert r["cnpj_parte"] == "98765432000110"

    def test_sem_cnpj_nao_altera(self):
        r = normalize_cnpj_part({"outro": "campo"})
        assert "cnpj" not in r


class TestDatajudBronzeToSilver:
    def test_pipeline_completo(self):
        bronze = {
            "numero_processo": "0001234-56.2024.8.26.0100",
            "subject_token": "tok-encrypted",
            "valor_causa": 25_000.0,
            "data_julgamento": "2023-03-15",
            "ingested_at": "2024-01-01T00:00:00Z",
            "transform_version": "1.0.0",
        }
        pseudonymized = dict(bronze)
        silver = datajud_bronze_to_silver(bronze, pseudonymized)
        assert silver["valor_causa"] == 25_000.0
        assert silver["valor_causa_imputado"] is False
        assert silver["valor_causa_outlier"] is False
        assert silver["valor_log"] > 0
        assert silver["recencia_dias"] > 0
        assert silver["ingested_at"] == "2024-01-01T00:00:00Z"

    def test_valor_ausente_imputado(self):
        bronze = {"numero_processo": "0001"}
        pseudonymized = {"numero_processo": "0001"}
        silver = datajud_bronze_to_silver(bronze, pseudonymized)
        assert silver["valor_causa"] == 0.0
        assert silver["valor_causa_imputado"] is True

    def test_outlier_removido(self):
        bronze = {"numero_processo": "X", "valor_causa": 5e12}
        pseudonymized = dict(bronze)
        silver = datajud_bronze_to_silver(bronze, pseudonymized)
        # outlier é zerado por remove_outliers_valor, depois imputado a 0.0
        assert silver["valor_causa"] == 0.0
        assert silver["valor_causa_outlier"] is True
        assert silver["valor_causa_imputado"] is True


class TestPgfnBronzeToSilver:
    def test_happy_path(self):
        bronze = {
            "cnpj": "12345678000195",
            "valor_total_divida": 50_000.0,
            "quantidade_debitos": 3,
            "tipo_devedor": "pj",
        }
        silver = pgfn_bronze_to_silver(bronze)
        assert silver["valor_total_divida"] == 50_000.0
        assert silver["tem_divida_ativa"] is True
        assert silver["valor_divida_log"] > 0
        assert silver["tipo_devedor"] == "PJ"

    def test_sem_divida(self):
        silver = pgfn_bronze_to_silver({"cnpj": "12345678000195"})
        assert silver["valor_total_divida"] == 0.0
        assert silver["tem_divida_ativa"] is False


class TestReceitaBronzeToSilver:
    def test_happy_path(self):
        bronze = {
            "cnpj": "12345678000195",
            "capital_social": 100_000.0,
            "situacao_cadastral": "ATIVA",
            "porte": "medio",
            "data_abertura": "2010-05-20",
        }
        silver = receita_bronze_to_silver(bronze)
        assert silver["capital_social"] == 100_000.0
        assert silver["capital_social_log"] > 0
        assert silver["esta_ativa"] is True
        assert silver["porte"] == "MEDIO"
        assert silver["idade_empresa_anos"] > 0

    def test_data_abertura_ausente(self):
        silver = receita_bronze_to_silver({"cnpj": "12345678000195"})
        assert silver["idade_empresa_anos"] is None

    def test_data_abertura_invalida(self):
        silver = receita_bronze_to_silver({
            "cnpj": "12345678000195",
            "data_abertura": "nao-e-data",
        })
        assert silver["idade_empresa_anos"] is None

    def test_inativa(self):
        silver = receita_bronze_to_silver({"situacao_cadastral": "BAIXADA"})
        assert silver["esta_ativa"] is False
