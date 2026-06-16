"""
Testes do ingest task PNCP.

Testam as funções de lógica pura (_map_modalidade, _raw_to_bronze_dict,
_fetch_pncp_page, _ingest_pncp) sem nenhuma dependência de Celery ou Redis real.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.ingest.tasks.pncp import (
    _cache_key,
    _fetch_pncp_page,
    _ingest_pncp,
    _map_modalidade,
    _raw_to_bronze_dict,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw(
    numero="PNCP-2024-001",
    modalidade_nome="Pregão Eletrônico",
    valor=100_000.0,
    num_propostas=3,
) -> dict:
    return {
        "numeroControlePNCP": numero,
        "niFornecedor": "98765432000110",
        "objetoContrato": "Aquisição de materiais",
        "modalidadeContratacao": {"nome": modalidade_nome},
        "valorGlobal": valor,
        "dataPublicacaoPncp": "2024-03-01",
        "dataAberturaPropostas": "2024-03-15",
        "quantidadePropostasRecebidas": num_propostas,
    }


def _api_resp(items: list[dict], total_paginas: int = 1) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "data": items,
        "totalRegistros": len(items),
        "totalPaginas": total_paginas,
        "numeroPagina": 1,
    }
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# _map_modalidade
# ---------------------------------------------------------------------------

class TestMapModalidade:
    def test_pregao_eletronico(self):
        assert _map_modalidade("Pregão Eletrônico") == "PREGAO_ELETRONICO"

    def test_dispensa(self):
        assert _map_modalidade("Dispensa") == "DISPENSA"

    def test_dispensa_de_licitacao(self):
        assert _map_modalidade("Dispensa de Licitação") == "DISPENSA"

    def test_inexigibilidade(self):
        assert _map_modalidade("Inexigibilidade") == "INEXIGIBILIDADE"

    def test_concorrencia(self):
        assert _map_modalidade("Concorrência") == "CONCORRENCIA"

    def test_desconhecida_vira_outra(self):
        assert _map_modalidade("Modalidade XYZ") == "OUTRA"

    def test_none_vira_outra(self):
        assert _map_modalidade(None) == "OUTRA"


# ---------------------------------------------------------------------------
# _raw_to_bronze_dict
# ---------------------------------------------------------------------------

class TestRawToBronzeDict:
    def test_happy_path(self):
        d = _raw_to_bronze_dict(_make_raw(), "12345678000195", "2024")
        assert d is not None
        assert d["numero_controle"] == "PNCP-2024-001"
        assert d["cnpj_orgao"] == "12345678000195"
        assert d["modalidade"] == "PREGAO_ELETRONICO"
        assert d["valor_contrato"] == 100_000.0

    def test_sem_numero_retorna_none(self):
        raw = {"objetoContrato": "x", "valorGlobal": 1000}
        assert _raw_to_bronze_dict(raw, "12345678000195", "2024") is None

    def test_objeto_vazio_usa_fallback(self):
        raw = {**_make_raw(), "objetoContrato": ""}
        d = _raw_to_bronze_dict(raw, "12345678000195", "2024")
        assert d is not None
        assert d["objeto"] == "Objeto não informado"

    def test_data_publicacao_fallback(self):
        raw = {k: v for k, v in _make_raw().items() if k != "dataPublicacaoPncp"}
        d = _raw_to_bronze_dict(raw, "12345678000195", "2024")
        assert d is not None
        assert d["data_publicacao"] == "2024-01-01"

    def test_modalidade_sem_nome_vira_outra(self):
        raw = {**_make_raw(), "modalidadeContratacao": {}}
        d = _raw_to_bronze_dict(raw, "12345678000195", "2024")
        assert d is not None
        assert d["modalidade"] == "OUTRA"

    def test_numeropce_como_fallback(self):
        raw = {**_make_raw()}
        del raw["numeroControlePNCP"]
        raw["numeroPCE"] = "PCE-2024-999"
        d = _raw_to_bronze_dict(raw, "12345678000195", "2024")
        assert d is not None
        assert d["numero_controle"] == "PCE-2024-999"


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_formato_correto(self):
        key = _cache_key("12345678000195", "2024", "PNCP-001")
        assert key == "pncp:12345678000195:2024:PNCP-001"


# ---------------------------------------------------------------------------
# _fetch_pncp_page
# ---------------------------------------------------------------------------

class TestFetchPncpPage:
    def test_ok_retorna_items_e_total_paginas(self):
        raw = _make_raw()
        api_resp = _api_resp([raw], total_paginas=3)

        with (
            patch("services.ingest.tasks.pncp.requests.get", return_value=api_resp),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            items, total = _fetch_pncp_page("12345678000195", "2024-01-01", "2024-12-31", 1)

        assert len(items) == 1
        assert total == 3

    def test_api_error_retorna_listas_vazias(self):
        with (
            patch("services.ingest.tasks.pncp.requests.get", side_effect=Exception("timeout")),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            items, total = _fetch_pncp_page("12345678000195", "2024-01-01", "2024-12-31", 1)

        assert items == []
        assert total == 0

    def test_circuit_breaker_aberto_nao_faz_request(self):
        with (
            patch("services.ingest.tasks.pncp.requests.get") as get_mock,
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = True
            items, total = _fetch_pncp_page("12345678000195", "2024-01-01", "2024-12-31", 1)

        get_mock.assert_not_called()
        assert items == []


# ---------------------------------------------------------------------------
# _ingest_pncp  (lógica central, sem Celery)
# ---------------------------------------------------------------------------

class TestIngestPncp:
    def test_happy_path_armazena_silver(self):
        redis_mock = MagicMock()
        api_resp = _api_resp([_make_raw()])

        with (
            patch("services.ingest.tasks.pncp.requests.get", return_value=api_resp),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            recon = _ingest_pncp("12345678000195", "2024", redis_mock)

        assert recon["source"] == "PNCP"
        assert recon["records_in"] == 1
        assert recon["records_out"] == 1
        assert recon["rejected"] == 0
        redis_mock.setex.assert_called_once()
        key = redis_mock.setex.call_args[0][0]
        assert key.startswith("pncp:12345678000195:2024:")

    def test_api_error_retorna_zeros(self):
        redis_mock = MagicMock()

        with (
            patch("services.ingest.tasks.pncp.requests.get", side_effect=Exception("timeout")),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            recon = _ingest_pncp("12345678000195", "2024", redis_mock)

        assert recon["records_in"] == 0
        assert recon["records_out"] == 0
        redis_mock.setex.assert_not_called()

    def test_registro_sem_numero_rejeitado(self):
        redis_mock = MagicMock()
        raw_sem_numero = {
            "objetoContrato": "Sem número",
            "valorGlobal": 1000,
            "dataPublicacaoPncp": "2024-01-01",
            "modalidadeContratacao": {"nome": "Pregão Eletrônico"},
        }
        api_resp = _api_resp([raw_sem_numero])

        with (
            patch("services.ingest.tasks.pncp.requests.get", return_value=api_resp),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            recon = _ingest_pncp("12345678000195", "2024", redis_mock)

        assert recon["rejected"] == 1
        assert recon["records_out"] == 0
        redis_mock.setex.assert_not_called()

    def test_paginacao_busca_multiplas_paginas(self):
        redis_mock = MagicMock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _api_resp(
                    [_make_raw(f"PNCP-2024-{i:03d}") for i in range(3)],
                    total_paginas=2,
                )
            return _api_resp([_make_raw("PNCP-2024-099")], total_paginas=2)

        with (
            patch("services.ingest.tasks.pncp.requests.get", side_effect=side_effect),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            recon = _ingest_pncp("12345678000195", "2024", redis_mock)

        assert recon["records_in"] == 4
        assert recon["records_out"] == 4
        assert redis_mock.setex.call_count == 4

    def test_dispensa_identificada_no_silver(self):
        redis_mock = MagicMock()
        raw = _make_raw(modalidade_nome="Dispensa")
        api_resp = _api_resp([raw])

        with (
            patch("services.ingest.tasks.pncp.requests.get", return_value=api_resp),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            recon = _ingest_pncp("12345678000195", "2024", redis_mock)

        assert recon["records_out"] == 1
        # Verify the silver stored has is_dispensa=True
        stored_json = redis_mock.setex.call_args[0][2]
        import json
        silver = json.loads(stored_json)
        assert silver["is_dispensa"] is True

    def test_unico_proponente_identificado_no_silver(self):
        redis_mock = MagicMock()
        raw = _make_raw(num_propostas=1)
        api_resp = _api_resp([raw])

        with (
            patch("services.ingest.tasks.pncp.requests.get", return_value=api_resp),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            _ingest_pncp("12345678000195", "2024", redis_mock)

        stored_json = redis_mock.setex.call_args[0][2]
        import json
        silver = json.loads(stored_json)
        assert silver["is_unico_proponente"] is True
