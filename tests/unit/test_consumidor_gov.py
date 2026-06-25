"""Testes do coletor Consumidor.gov (parsing/agregação puros, sem rede)."""
from __future__ import annotations

import json
from unittest.mock import patch

from services.ingest.tasks import consumidor_gov as cg


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def setex(self, key, ttl, value):
        self.store[key] = value


_CSV = (
    "Nome Fantasia;Situação;Respondida;Nota do Consumidor\n"
    "Operadora XYZ;Resolvida;S;4\n"
    "Operadora XYZ;Não Resolvida;S;2\n"
    "Operadora XYZ;Resolvida;N;\n"
    "Banco ABC;Resolvida;S;5\n"
    ";Resolvida;S;5\n"  # sem empresa — ignorado
)


class TestSlugify:
    def test_normaliza(self):
        assert cg.slugify("Operadora XYZ S.A.") == "operadora-xyz-s-a"
        assert cg.slugify("Café Ltda") == "cafe-ltda"


class TestAggregate:
    def test_agrega_por_empresa(self):
        agg = cg.aggregate_reclamacoes(cg.parse_csv(_CSV))
        xyz = agg["operadora-xyz"]
        assert xyz["total"] == 3
        assert xyz["respondidas"] == 2
        assert xyz["resolvidas"] == 2  # "Não Resolvida" não conta
        assert xyz["pct_resolucao"] == round(2 / 3, 4)
        assert xyz["nota_media"] == 3.0  # (4+2)/2; linha sem nota ignorada
        assert "banco-abc" in agg
        assert len(agg) == 2  # linha sem empresa descartada

    def test_csv_vazio(self):
        assert cg.aggregate_reclamacoes([]) == {}


class TestFetchEAgrega:
    def test_falha_degrada(self):
        with patch.object(cg.requests, "get", side_effect=ConnectionError("403")):
            assert cg.fetch_e_agrega("https://x/y.csv") == {}


class TestIngest:
    def test_persiste_por_empresa(self):
        with patch.object(cg, "fetch_e_agrega", return_value={
            "operadora-xyz": {"empresa": "Operadora XYZ", "total": 3, "pct_resolucao": 0.67}
        }):
            redis = _FakeRedis()
            recon = cg._ingest_consumidor("https://x/y.csv", redis)
        assert recon["empresas"] == 1
        assert "consumidor:operadora-xyz" in redis.store
        assert json.loads(redis.store["consumidor:operadora-xyz"])["empresa"] == "Operadora XYZ"
