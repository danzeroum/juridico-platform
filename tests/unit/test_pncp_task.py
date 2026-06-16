"""Testes do ingest task PNCP."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _make_passthrough_app():
    """Cria mock de Celery que preserva a função original e adiciona .run()."""

    def _task_deco(**kwargs):
        bind = kwargs.get("bind", False)

        def decorator(fn):
            if bind:
                fn.run = lambda *a, **kw: fn(MagicMock(), *a, **kw)
            else:
                fn.run = fn
            return fn

        return decorator

    app = MagicMock()
    app.task = _task_deco
    return app


# celery e ingest.celery_app não estão instalados no env de test — mock antes de importar
for _mod in ["celery", "celery.utils", "celery.utils.log"]:
    sys.modules.setdefault(_mod, MagicMock())
sys.modules.setdefault("ingest", MagicMock())
_ingest_celery_mod = MagicMock()
_ingest_celery_mod.app = _make_passthrough_app()
sys.modules["ingest.celery_app"] = _ingest_celery_mod

# Força reimport do módulo de task com os mocks corretos
sys.modules.pop("services.ingest.tasks.pncp", None)

import pytest
from unittest.mock import patch


def _make_raw_contrato(
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


def _make_api_resp(items: list[dict], total_paginas: int = 1) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "data": items,
        "totalRegistros": len(items),
        "totalPaginas": total_paginas,
        "numeroPagina": 1,
    }
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture(autouse=True)
def _mock_settings():
    with patch("services.ingest.tasks.pncp.settings") as s:
        s.REDIS_URL = "redis://localhost:6379/0"
        yield s


class TestPncpMapModalidade:
    def test_pregao_eletronico(self):
        from services.ingest.tasks.pncp import _map_modalidade
        assert _map_modalidade("Pregão Eletrônico") == "PREGAO_ELETRONICO"

    def test_dispensa(self):
        from services.ingest.tasks.pncp import _map_modalidade
        assert _map_modalidade("Dispensa") == "DISPENSA"

    def test_dispensa_de_licitacao(self):
        from services.ingest.tasks.pncp import _map_modalidade
        assert _map_modalidade("Dispensa de Licitação") == "DISPENSA"

    def test_inexigibilidade(self):
        from services.ingest.tasks.pncp import _map_modalidade
        assert _map_modalidade("Inexigibilidade") == "INEXIGIBILIDADE"

    def test_desconhecida_vira_outra(self):
        from services.ingest.tasks.pncp import _map_modalidade
        assert _map_modalidade("Modalidade XYZ") == "OUTRA"

    def test_none_vira_outra(self):
        from services.ingest.tasks.pncp import _map_modalidade
        assert _map_modalidade(None) == "OUTRA"


class TestRawToBronzeDict:
    def test_happy_path(self):
        from services.ingest.tasks.pncp import _raw_to_bronze_dict
        d = _raw_to_bronze_dict(_make_raw_contrato(), "12345678000195", "2024")
        assert d is not None
        assert d["numero_controle"] == "PNCP-2024-001"
        assert d["cnpj_orgao"] == "12345678000195"
        assert d["modalidade"] == "PREGAO_ELETRONICO"
        assert d["valor_contrato"] == 100_000.0

    def test_sem_numero_controle_retorna_none(self):
        from services.ingest.tasks.pncp import _raw_to_bronze_dict
        raw = {"objetoContrato": "x", "valorGlobal": 1000}
        assert _raw_to_bronze_dict(raw, "12345678000195", "2024") is None

    def test_objeto_vazio_usa_fallback(self):
        from services.ingest.tasks.pncp import _raw_to_bronze_dict
        raw = {**_make_raw_contrato(), "objetoContrato": ""}
        d = _raw_to_bronze_dict(raw, "12345678000195", "2024")
        assert d is not None
        assert d["objeto"] == "Objeto não informado"

    def test_data_publicacao_fallback(self):
        from services.ingest.tasks.pncp import _raw_to_bronze_dict
        raw = {k: v for k, v in _make_raw_contrato().items() if k != "dataPublicacaoPncp"}
        d = _raw_to_bronze_dict(raw, "12345678000195", "2024")
        assert d is not None
        assert d["data_publicacao"] == "2024-01-01"

    def test_modalidade_sem_nome_vira_outra(self):
        from services.ingest.tasks.pncp import _raw_to_bronze_dict
        raw = {**_make_raw_contrato(), "modalidadeContratacao": {}}
        d = _raw_to_bronze_dict(raw, "12345678000195", "2024")
        assert d is not None
        assert d["modalidade"] == "OUTRA"


class TestFetchPncpPage:
    def test_api_ok_retorna_items_e_total_paginas(self):
        from services.ingest.tasks.pncp import _fetch_pncp_page
        raw = _make_raw_contrato()
        api_resp = _make_api_resp([raw], total_paginas=3)

        with (
            patch("services.ingest.tasks.pncp.requests.get", return_value=api_resp),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            items, total = _fetch_pncp_page("12345678000195", "2024-01-01", "2024-12-31", 1)

        assert len(items) == 1
        assert total == 3

    def test_api_error_retorna_listas_vazias(self):
        from services.ingest.tasks.pncp import _fetch_pncp_page

        with (
            patch("services.ingest.tasks.pncp.requests.get", side_effect=Exception("timeout")),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = False
            items, total = _fetch_pncp_page("12345678000195", "2024-01-01", "2024-12-31", 1)

        assert items == []
        assert total == 0

    def test_circuit_breaker_aberto_nao_faz_request(self):
        from services.ingest.tasks.pncp import _fetch_pncp_page

        with (
            patch("services.ingest.tasks.pncp.requests.get") as get_mock,
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
        ):
            gcb.return_value.is_open.return_value = True
            items, total = _fetch_pncp_page("12345678000195", "2024-01-01", "2024-12-31", 1)

        get_mock.assert_not_called()
        assert items == []
        assert total == 0


class TestRunDailyIngest:
    def _run(self, cnpj="12345678000195", ano=2024, api_resp=None, redis_mock=None):
        from services.ingest.tasks.pncp import run_daily_ingest

        redis_mock = redis_mock or MagicMock()
        api_resp = api_resp or _make_api_resp([])

        redis_lib_mock = MagicMock()
        redis_lib_mock.from_url.return_value = redis_mock

        with (
            patch("services.ingest.tasks.pncp.requests.get", return_value=api_resp),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
            patch.dict(sys.modules, {"redis": redis_lib_mock}),
        ):
            gcb.return_value.is_open.return_value = False
            return run_daily_ingest.run(cnpj, ano), redis_mock

    def test_happy_path_armazena_silver_no_redis(self):
        redis_mock = MagicMock()
        recon, _ = self._run(api_resp=_make_api_resp([_make_raw_contrato()]), redis_mock=redis_mock)

        assert recon["source"] == "PNCP"
        assert recon["records_in"] == 1
        assert recon["records_out"] == 1
        assert recon["rejected"] == 0
        redis_mock.setex.assert_called_once()
        key = redis_mock.setex.call_args[0][0]
        assert key.startswith("pncp:12345678000195:2024:")

    def test_api_error_retorna_zeros(self):
        from services.ingest.tasks.pncp import run_daily_ingest
        redis_mock = MagicMock()
        redis_lib_mock = MagicMock()
        redis_lib_mock.from_url.return_value = redis_mock

        with (
            patch("services.ingest.tasks.pncp.requests.get", side_effect=Exception("timeout")),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
            patch.dict(sys.modules, {"redis": redis_lib_mock}),
        ):
            gcb.return_value.is_open.return_value = False
            recon = run_daily_ingest.run("12345678000195", 2024)

        assert recon["records_in"] == 0
        assert recon["records_out"] == 0

    def test_registro_sem_numero_rejeitado(self):
        raw_sem_numero = {
            "objetoContrato": "Sem número",
            "valorGlobal": 1000,
            "dataPublicacaoPncp": "2024-01-01",
            "modalidadeContratacao": {"nome": "Pregão Eletrônico"},
        }
        redis_mock = MagicMock()
        recon, _ = self._run(api_resp=_make_api_resp([raw_sem_numero]), redis_mock=redis_mock)

        assert recon["rejected"] == 1
        assert recon["records_out"] == 0
        redis_mock.setex.assert_not_called()

    def test_paginacao_busca_multiplas_paginas(self):
        from services.ingest.tasks.pncp import run_daily_ingest
        redis_mock = MagicMock()
        redis_lib_mock = MagicMock()
        redis_lib_mock.from_url.return_value = redis_mock
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_api_resp(
                    [_make_raw_contrato(f"PNCP-2024-{i:03d}") for i in range(3)],
                    total_paginas=2,
                )
            return _make_api_resp([_make_raw_contrato("PNCP-2024-099")], total_paginas=2)

        with (
            patch("services.ingest.tasks.pncp.requests.get", side_effect=side_effect),
            patch("services.ingest.tasks.pncp.get_circuit_breaker") as gcb,
            patch.dict(sys.modules, {"redis": redis_lib_mock}),
        ):
            gcb.return_value.is_open.return_value = False
            recon = run_daily_ingest.run("12345678000195", 2024)

        assert recon["records_in"] == 4
        assert recon["records_out"] == 4
        assert redis_mock.setex.call_count == 4

    def test_ano_default_usa_ano_corrente(self):
        from datetime import datetime
        recon, _ = self._run(ano=None)
        assert recon["date"] == str(datetime.now().year)
