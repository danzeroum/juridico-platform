"""
Transforms de qualidade de dados: faltantes, outliers de higiene, normalização.

Bronze → Silver:
1. Validação de schema (Pydantic — já feita no contrato)
2. Tratamento de faltantes
3. Remoção de outliers de higiene (valores fisicamente impossíveis)
4. Normalização de strings (strip/upper)
5. Derivação de features simples (log1p, idade)
"""

from datetime import date
from typing import Any

from .base import safe_log1p


def treat_missing_valor_causa(record: dict[str, Any]) -> dict[str, Any]:
    """Imputa valor_causa ausente com 0.0 e registra flag."""
    if record.get("valor_causa") is None:
        record["valor_causa"] = 0.0
        record["valor_causa_imputado"] = True
    else:
        record["valor_causa_imputado"] = False
    return record


def remove_outliers_valor(record: dict[str, Any], max_valor: float = 1e12) -> dict[str, Any]:
    """Remove outliers físicos de valor (>1 trilhão é erro de dado, não anomalia de negócio)."""
    v = record.get("valor_causa")
    if v is not None and v > max_valor:
        record["valor_causa"] = None
        record["valor_causa_outlier"] = True
    else:
        record["valor_causa_outlier"] = False
    return record


def add_valor_log(record: dict[str, Any]) -> dict[str, Any]:
    record["valor_log"] = safe_log1p(record.get("valor_causa"))
    return record


def add_recencia(record: dict[str, Any], date_field: str = "data_julgamento") -> dict[str, Any]:
    """Dias desde a data da fonte — feature de recência normalizada."""
    raw = record.get(date_field)
    if raw:
        try:
            source_date = date.fromisoformat(str(raw)[:10])
            lag = (date.today() - source_date).days
            record["recencia_dias"] = lag
            record["recencia"] = -lag / 365.0  # negativo: mais recente = valor maior
        except ValueError:
            record["recencia_dias"] = None
            record["recencia"] = 0.0
    else:
        record["recencia_dias"] = None
        record["recencia"] = 0.0
    return record


def normalize_cnpj_part(record: dict[str, Any]) -> dict[str, Any]:
    """Normaliza CNPJ: apenas dígitos, 14 chars."""
    for field in ("cnpj", "cnpj_parte"):
        v = record.get(field)
        if v:
            digits = "".join(c for c in str(v) if c.isdigit())
            record[field] = digits if len(digits) == 14 else None
    return record


def datajud_bronze_to_silver(
    bronze: dict[str, Any],
    pseudonymized: dict[str, Any],
) -> dict[str, Any]:
    """
    Transforma registro bronze DATAJUD para silver.

    `pseudonymized` é o resultado de `pseudonymize_process_record(bronze)`.
    """
    silver = dict(pseudonymized)

    # Qualidade: outliers de valor
    silver = remove_outliers_valor(silver)
    silver = treat_missing_valor_causa(silver)
    silver = add_valor_log(silver)
    silver = add_recencia(silver, date_field="data_julgamento")

    # Linage original preservada
    silver.setdefault("ingested_at", bronze.get("ingested_at"))
    silver.setdefault("transform_version", bronze.get("transform_version", "1.0.0"))

    return silver


def pgfn_bronze_to_silver(bronze: dict[str, Any]) -> dict[str, Any]:
    silver = dict(bronze)
    valor = silver.get("valor_total_divida") or 0.0
    silver["valor_total_divida"] = valor
    silver["valor_divida_log"] = safe_log1p(valor)
    silver["tem_divida_ativa"] = valor > 0
    silver["quantidade_debitos"] = silver.get("quantidade_debitos") or 0
    silver["tipo_devedor"] = (silver.get("tipo_devedor") or "PJ").upper()
    return silver


def receita_bronze_to_silver(bronze: dict[str, Any]) -> dict[str, Any]:
    silver = dict(bronze)
    capital = silver.get("capital_social") or 0.0
    silver["capital_social"] = capital
    silver["capital_social_log"] = safe_log1p(capital)
    silver["esta_ativa"] = silver.get("situacao_cadastral", "") == "ATIVA"
    silver["porte"] = (silver.get("porte") or "DESCONHECIDO").upper()

    # Idade da empresa em anos
    abertura = silver.get("data_abertura")
    if abertura:
        try:
            d = date.fromisoformat(str(abertura)[:10])
            silver["idade_empresa_anos"] = round((date.today() - d).days / 365.25, 1)
        except ValueError:
            silver["idade_empresa_anos"] = None
    else:
        silver["idade_empresa_anos"] = None

    return silver
