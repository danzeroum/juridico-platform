"""
Testes de data contracts DATAJUD, PGFN, Receita Federal.

Cobrem: validação de schema OK, rejeição de inválidos, normalização de campos.
Não requerem serviços externos.
"""

import pytest
from pydantic import ValidationError

# ── DATAJUD ───────────────────────────────────────────────────────────────────

class TestDatajudProcessoBronze:
    def _import(self):
        from services.ingest.contracts.datajud import DatajudProcessoBronze
        return DatajudProcessoBronze

    def test_valid_record(self):
        DatajudProcessoBronze = self._import()
        rec = DatajudProcessoBronze(
            id_processo="proc-001",
            numero_processo="0001234-12.2024.8.26.0001",
            data_julgamento="2024-03-15",
            tribunal="TJSP",
            materia="TRIBUTARIO",
            resultado="provimento",
            cnpj_parte="11222333000181",
        )
        assert rec.tribunal == "TJSP"
        assert rec.source == "DATAJUD"
        assert rec.transform_version == "1.0.0"
        assert rec.ingested_at is not None

    def test_invalid_date_rejected(self):
        DatajudProcessoBronze = self._import()
        with pytest.raises(ValidationError):
            DatajudProcessoBronze(
                id_processo="p1",
                numero_processo="num",
                data_julgamento="not-a-date",
                tribunal="TJSP",
            )

    def test_invalid_cnpj_rejected(self):
        DatajudProcessoBronze = self._import()
        with pytest.raises(ValidationError):
            DatajudProcessoBronze(
                id_processo="p1",
                numero_processo="num",
                data_julgamento="2024-01-01",
                tribunal="TJSP",
                cnpj_parte="123",  # muito curto
            )

    def test_tribunal_uppercased(self):
        DatajudProcessoBronze = self._import()
        rec = DatajudProcessoBronze(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-06-01",
            tribunal="tjrs",
        )
        assert rec.tribunal == "TJRS"

    def test_cnpj_normalized_to_digits(self):
        DatajudProcessoBronze = self._import()
        rec = DatajudProcessoBronze(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-01-01",
            tribunal="TJSP",
            cnpj_parte="11.222.333/0001-81",
        )
        assert rec.cnpj_parte == "11222333000181"

    def test_cnpj_parte_none_passthrough(self):
        DatajudProcessoBronze = self._import()
        rec = DatajudProcessoBronze(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-01-01",
            tribunal="TJSP",
        )
        assert rec.cnpj_parte is None


class TestDatajudProcessoSilver:
    def _import(self):
        from datetime import datetime

        from services.ingest.contracts.datajud import DatajudProcessoSilver
        return DatajudProcessoSilver, datetime

    def test_resultado_normalized_provimento(self):
        DatajudProcessoSilver, datetime = self._import()
        rec = DatajudProcessoSilver(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-01-01",
            tribunal="TJSP",
            resultado_normalizado="dado provimento ao recurso",
            ingested_at=datetime.utcnow(),
        )
        assert rec.resultado_normalizado == "PROVIMENTO"

    def test_resultado_normalized_negado(self):
        DatajudProcessoSilver, datetime = self._import()
        rec = DatajudProcessoSilver(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-01-01",
            tribunal="TJSP",
            resultado_normalizado="recurso negado por unanimidade",
            ingested_at=datetime.utcnow(),
        )
        assert rec.resultado_normalizado == "NEGADO"

    def test_resultado_normalized_parcial(self):
        DatajudProcessoSilver, datetime = self._import()
        rec = DatajudProcessoSilver(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-01-01",
            tribunal="TJSP",
            resultado_normalizado="resultado parcial favorável",
            ingested_at=datetime.utcnow(),
        )
        assert rec.resultado_normalizado == "PARCIAL"

    def test_resultado_normalized_outro(self):
        DatajudProcessoSilver, datetime = self._import()
        rec = DatajudProcessoSilver(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-01-01",
            tribunal="TJSP",
            resultado_normalizado="extinto sem resolução do mérito",
            ingested_at=datetime.utcnow(),
        )
        assert rec.resultado_normalizado == "OUTRO"

    def test_resultado_normalized_none(self):
        DatajudProcessoSilver, datetime = self._import()
        rec = DatajudProcessoSilver(
            id_processo="p1",
            numero_processo="n",
            data_julgamento="2024-01-01",
            tribunal="TJSP",
            resultado_normalizado=None,
            ingested_at=datetime.utcnow(),
        )
        assert rec.resultado_normalizado is None


# ── PGFN ──────────────────────────────────────────────────────────────────────

class TestPgfnDevedorBronze:
    def _import(self):
        from services.ingest.contracts.pgfn import PgfnDevedorBronze
        return PgfnDevedorBronze

    def test_valid_regular(self):
        PgfnDevedorBronze = self._import()
        rec = PgfnDevedorBronze(
            cnpj="11222333000181",
            situacao="regular",
        )
        assert rec.situacao == "REGULAR"
        assert rec.source == "PGFN"
        # tem_divida_ativa é campo do Silver, não do Bronze

    def test_invalid_cnpj_rejected(self):
        PgfnDevedorBronze = self._import()
        with pytest.raises(ValidationError):
            PgfnDevedorBronze(cnpj="123", situacao="REGULAR")

    def test_valor_negativo_rejected(self):
        PgfnDevedorBronze = self._import()
        with pytest.raises(ValidationError):
            PgfnDevedorBronze(cnpj="11222333000181", situacao="IRREGULAR", valor_total_divida=-100)

    def test_cnpj_formatted_normalized(self):
        PgfnDevedorBronze = self._import()
        rec = PgfnDevedorBronze(cnpj="11.222.333/0001-81", situacao="REGULAR")
        assert rec.cnpj == "11222333000181"

    def test_invalid_date_rejected(self):
        PgfnDevedorBronze = self._import()
        with pytest.raises(ValidationError):
            PgfnDevedorBronze(cnpj="11222333000181", situacao="REGULAR", data_inscricao="nao-e-data")


# ── RECEITA ───────────────────────────────────────────────────────────────────

class TestReceitaCnpjBronze:
    def _import(self):
        from services.ingest.contracts.receita import ReceitaCnpjBronze
        return ReceitaCnpjBronze

    def test_valid_ativa(self):
        ReceitaCnpjBronze = self._import()
        rec = ReceitaCnpjBronze(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            situacao_cadastral="ATIVA",
            capital_social=100000.0,
            uf="SP",
        )
        assert rec.uf == "SP"
        assert rec.source == "RECEITA"

    def test_invalid_situacao_rejected(self):
        ReceitaCnpjBronze = self._import()
        with pytest.raises(ValidationError):
            ReceitaCnpjBronze(
                cnpj="11222333000181",
                razao_social="EMPRESA",
                situacao_cadastral="INEXISTENTE",
            )

    def test_situacao_normalized_uppercase(self):
        ReceitaCnpjBronze = self._import()
        rec = ReceitaCnpjBronze(
            cnpj="11222333000181",
            razao_social="EMPRESA",
            situacao_cadastral="ativa",
        )
        assert rec.situacao_cadastral == "ATIVA"

    def test_uf_normalized_uppercase(self):
        ReceitaCnpjBronze = self._import()
        rec = ReceitaCnpjBronze(
            cnpj="11222333000181",
            razao_social="EMPRESA",
            situacao_cadastral="ATIVA",
            uf="rj",
        )
        assert rec.uf == "RJ"

    def test_empty_razao_social_rejected(self):
        ReceitaCnpjBronze = self._import()
        with pytest.raises(ValidationError):
            ReceitaCnpjBronze(
                cnpj="11222333000181",
                razao_social="",
                situacao_cadastral="ATIVA",
            )

    def test_invalid_cnpj_rejected(self):
        ReceitaCnpjBronze = self._import()
        with pytest.raises(ValidationError):
            ReceitaCnpjBronze(
                cnpj="12345",  # menos de 14 dígitos
                razao_social="EMPRESA",
                situacao_cadastral="ATIVA",
            )

    def test_data_abertura_valid(self):
        ReceitaCnpjBronze = self._import()
        rec = ReceitaCnpjBronze(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            situacao_cadastral="ATIVA",
            data_abertura="2010-03-15",
            data_situacao_cadastral="2024-01-01",
        )
        assert rec.data_abertura == "2010-03-15"
        assert rec.data_situacao_cadastral == "2024-01-01"
