"""
Parse da tabela de municípios do IBGE (DTB) — fonte estruturada, estável.

Fornece código IBGE (7 dígitos) → município + UF, usado para cruzamentos
cadastrais/geográficos. Puro: recebe o texto do CSV, sem I/O de rede.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from services.shared.contracts.fiscal import UF, normalize_descricao

# Aliases de cabeçalho (normalizados) → campo lógico. A DTB do IBGE muda os rótulos
# ao longo dos anos; cobrimos as variações mais comuns.
_COD_ALIASES = {"codigo municipio completo", "codigo ibge", "cod municipio", "municipio codigo", "codigo"}
_MUN_ALIASES = {"nome municipio", "municipio", "nome do municipio"}
_UF_ALIASES = {"uf", "sigla uf", "nome uf", "sigla"}


def detect_columns(headers: list[Any]) -> dict[str, int | None]:
    colmap: dict[str, int | None] = {"codigo": None, "municipio": None, "uf": None}
    for idx, raw in enumerate(headers):
        if raw is None:
            continue
        norm = normalize_descricao(str(raw))
        if colmap["codigo"] is None and norm in _COD_ALIASES:
            colmap["codigo"] = idx
        elif colmap["municipio"] is None and norm in _MUN_ALIASES:
            colmap["municipio"] = idx
        elif colmap["uf"] is None and norm in _UF_ALIASES:
            colmap["uf"] = idx
    return colmap


def _clean_codigo(value: Any) -> str | None:
    if value is None:
        return None
    digitos = "".join(ch for ch in str(value) if ch.isdigit())
    return digitos if len(digitos) == 7 else None


def parse_municipios(csv_text: str, *, delimiter: str = ";") -> list[dict[str, Any]]:
    """
    Faz o parse do CSV de municípios do IBGE. Retorna linhas válidas
    {codigo_ibge, municipio, uf}. Descarta linhas sem código de 7 dígitos ou UF inválida.
    """
    reader = csv.reader(io.StringIO(csv_text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return []
    colmap = detect_columns(rows[0])
    if colmap["codigo"] is None or colmap["uf"] is None:
        raise ValueError("CSV do IBGE sem colunas de código/UF reconhecíveis.")

    def cell(row: list, field: str) -> Any:
        col = colmap[field]
        return row[col] if col is not None and col < len(row) else None

    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        codigo = _clean_codigo(cell(row, "codigo"))
        uf_raw = cell(row, "uf")
        uf = str(uf_raw).strip().upper() if uf_raw is not None else None
        if codigo is None or uf not in UF.__members__:
            continue
        municipio = cell(row, "municipio")
        out.append({
            "codigo_ibge": codigo,
            "municipio": str(municipio).strip() if municipio is not None else None,
            "uf": uf,
        })
    return out
