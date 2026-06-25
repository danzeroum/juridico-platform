"""
Ingest task para IBGE (servicodados.ibge.gov.br — dados públicos, sem auth).

Coleta direto da fonte:
  - Lista de municípios por UF   → /api/v1/localidades/estados/{UF}/municipios
  - População residente estimada → /api/v3/agregados/6579/periodos/-1/variaveis/9324

As funções `fetch_municipios` e `fetch_populacao` são puras (apenas HTTP, sem
Celery/Redis) e são reutilizadas pelo gateway para coleta ao vivo. O
`run_ingest` adicional persiste no Redis (cache ibge:{cod_ibge}) seguindo o
mesmo padrão dos demais coletores (PNCP, Receita).
"""
from __future__ import annotations

import logging

import requests
from pydantic import ValidationError

from services.ingest.contracts.ibge import IbgeMunicipioBronze, ibge_bronze_to_silver
from services.ingest.pipeline.base import get_circuit_breaker, reconcile
from services.shared.config import settings

# Celery disponível apenas em runtime (não em test env sem infraestrutura)
try:
    from celery.utils.log import get_task_logger
    from ingest.celery_app import app as _celery_app

    logger = get_task_logger(__name__)
    _CELERY = True
except (ImportError, ModuleNotFoundError):
    logger = logging.getLogger(__name__)
    _celery_app = None  # type: ignore[assignment]
    _CELERY = False

IBGE_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1"
IBGE_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3"
# Agregado 6579 = População residente estimada; variável 9324; nível N6 = Município.
_POP_AGREGADO = "6579"
_POP_VARIAVEL = "9324"
# Agregado 1737 = IPCA; variável 63 = variação mensal; variável 2265 = acumulada 12m.
_IPCA_AGREGADO = "1737"
_IPCA_VAR_MENSAL = "63"
_IPCA_VAR_12M = "2265"
CACHE_TTL = 60 * 60 * 24 * 30  # 30 dias (dados anuais)


def _extract_uf(item: dict, fallback: str) -> str:
    """Extrai a sigla da UF do município (estrutura aninhada do IBGE)."""
    try:
        return item["microrregiao"]["mesorregiao"]["UF"]["sigla"]
    except (KeyError, TypeError):
        return fallback.upper()


def fetch_municipios(uf: str) -> list[dict]:
    """
    Lista municípios de uma UF direto do IBGE.

    Retorna [{cod_ibge, municipio, uf}], ordenado por nome. Lista vazia em falha
    (degradação graciosa). `uf` deve ser sigla de 2 letras (ex.: "SP").
    """
    uf_norm = uf.strip().upper()
    if len(uf_norm) != 2 or not uf_norm.isalpha():
        return []

    cb = get_circuit_breaker("ibge")
    if cb.is_open():
        logger.warning("CircuitBreaker IBGE aberto — skip municipios uf=%s", uf_norm)
        return []

    try:
        resp = requests.get(
            f"{IBGE_LOCALIDADES}/localidades/estados/{uf_norm}/municipios",
            timeout=30,
        )
        resp.raise_for_status()
        cb.record_success()
        data = resp.json()
        if not isinstance(data, list):
            return []
        municipios = [
            {
                "cod_ibge": str(item["id"]),
                "municipio": item["nome"],
                "uf": _extract_uf(item, uf_norm),
            }
            for item in data
            if item.get("id") and item.get("nome")
        ]
        municipios.sort(key=lambda m: m["municipio"])
        return municipios
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao buscar municípios IBGE uf=%s: %s", uf_norm, exc)
        return []


def fetch_populacao(cod_ibge: str) -> tuple[int | None, str | None]:
    """
    População residente estimada de um município (SIDRA agregado 6579).

    Retorna (populacao, ano) ou (None, None) em falha/ausência.
    """
    if not cod_ibge.isdigit() or len(cod_ibge) != 7:
        return None, None

    cb = get_circuit_breaker("ibge")
    if cb.is_open():
        return None, None

    try:
        resp = requests.get(
            f"{IBGE_AGREGADOS}/agregados/{_POP_AGREGADO}/periodos/-1/variaveis/{_POP_VARIAVEL}",
            params={"localidades": f"N6[{cod_ibge}]"},
            timeout=30,
        )
        resp.raise_for_status()
        cb.record_success()
        data = resp.json()
        serie = data[0]["resultados"][0]["series"][0]["serie"]
        ano = max(serie.keys())
        valor = serie[ano]
        return (int(valor) if valor not in (None, "-", "...") else None), ano
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao buscar população IBGE cod=%s: %s", cod_ibge, exc)
        return None, None


def _fmt_periodo(p: str) -> str:
    """Converte período SIDRA 'YYYYMM' em 'YYYY-MM'."""
    return f"{p[:4]}-{p[4:6]}" if len(p) == 6 and p.isdigit() else p


def _fetch_ipca_serie(variavel: str, periodos: str) -> dict[str, str]:
    """Busca uma série do IPCA (agregado 1737) no nível Brasil. {} em falha."""
    resp = requests.get(
        f"{IBGE_AGREGADOS}/agregados/{_IPCA_AGREGADO}/periodos/{periodos}/variaveis/{variavel}",
        params={"localidades": "N1[all]"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()[0]["resultados"][0]["series"][0]["serie"]


def fetch_ipca() -> dict:
    """
    IPCA (IBGE/SIDRA agregado 1737): acumulado em 12 meses + variação mensal recente.

    Retorna {acumulado_12m, referencia, mensal:[{periodo, valor}]} ou {} em falha
    (degradação graciosa). Indicador macro real para enriquecer o TaxPredict.
    """
    cb = get_circuit_breaker("ibge")
    if cb.is_open():
        return {}

    try:
        serie_12m = _fetch_ipca_serie(_IPCA_VAR_12M, "-1")
        ref = max(serie_12m.keys())
        acumulado = float(serie_12m[ref])

        serie_mensal = _fetch_ipca_serie(_IPCA_VAR_MENSAL, "-6")
        mensal = [
            {"periodo": _fmt_periodo(k), "valor": float(v)}
            for k, v in sorted(serie_mensal.items())
            if v not in (None, "-", "...")
        ]
        cb.record_success()
        return {"acumulado_12m": acumulado, "referencia": _fmt_periodo(ref), "mensal": mensal}
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao buscar IPCA IBGE: %s", exc)
        return {}


def _ingest_ibge(uf: str, redis_client) -> dict:
    """
    Coleta municípios + população de uma UF e persiste no Redis (cache ibge:{cod}).

    Testável sem Celery. Retorna reconciliação (records_in/out, rejected).
    """
    municipios = fetch_municipios(uf)
    records_in = len(municipios)
    records_out = 0
    rejected = 0

    for m in municipios:
        populacao, ano = fetch_populacao(m["cod_ibge"])
        try:
            bronze = IbgeMunicipioBronze(
                cod_ibge=m["cod_ibge"],
                municipio=m["municipio"],
                uf=m["uf"],
                ano=int(ano) if ano else 0,
                populacao=populacao or 0,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            logger.warning("IBGE bronze inválido cod=%s: %s", m["cod_ibge"], exc)
            rejected += 1
            continue

        silver = ibge_bronze_to_silver(bronze)
        redis_client.setex(f"ibge:{m['cod_ibge']}", CACHE_TTL, silver.model_dump_json())
        records_out += 1

    recon = reconcile("IBGE", records_in, records_out, uf.upper())
    recon["rejected"] = rejected
    recon["uf"] = uf.upper()
    logger.info("IBGE ingest uf=%s: %s", uf.upper(), recon)
    return recon


if _CELERY:
    @_celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
    def run_ingest(self, uf: str) -> dict:
        """Ingest IBGE de uma UF (Celery task)."""
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        return _ingest_ibge(uf, r)
else:
    def run_ingest(uf: str) -> dict:  # type: ignore[misc]
        """Ingest IBGE de uma UF (fallback sem Celery — dev/test)."""
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        return _ingest_ibge(uf, r)
