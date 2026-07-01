"""
Histórico de migração de códigos NCM — código antigo → novo, temporal.

Os códigos NCM mudam por resoluções (MERCOSUL/RFB): são unificados, desmembrados
ou extintos. Para consultas retroativas e para mapear um NCM antigo (vindo de uma
planilha de anos atrás) ao código vigente, mantemos uma tabela de migração e um
resolvedor determinístico que segue a cadeia de sucessão até a data consultada.

Puro: recebe o texto/linhas, sem I/O. Alimenta fiscal.ncm_migracao (via task).
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from services.shared.contracts.fiscal import normalize_descricao

_ORIG_ALIASES = {"ncm origem", "codigo antigo", "ncm antigo", "origem", "de"}
_DEST_ALIASES = {"ncm destino", "codigo novo", "ncm novo", "destino", "para"}
_INI_ALIASES = {"vigencia inicio", "inicio", "data inicio", "vigente desde"}
_FIM_ALIASES = {"vigencia fim", "fim", "data fim"}
_ATO_ALIASES = {"ato legal", "ato", "resolucao", "fundamento"}


def _clean_ncm(value: Any) -> str | None:
    if value is None:
        return None
    digitos = "".join(ch for ch in str(value) if ch.isdigit())
    return digitos.zfill(8) if 0 < len(digitos) <= 8 else None


def _detect(headers: list[Any]) -> dict[str, int | None]:
    aliases = {
        "ncm_origem": _ORIG_ALIASES, "ncm_destino": _DEST_ALIASES,
        "vigencia_inicio": _INI_ALIASES, "vigencia_fim": _FIM_ALIASES, "ato_legal": _ATO_ALIASES,
    }
    colmap: dict[str, int | None] = dict.fromkeys(aliases, None)
    for idx, raw in enumerate(headers):
        if raw is None:
            continue
        norm = normalize_descricao(str(raw))
        for field, al in aliases.items():
            if colmap[field] is None and norm in al:
                colmap[field] = idx
                break
    return colmap


def parse_migracao(csv_text: str, *, delimiter: str = ";") -> list[dict[str, Any]]:
    """
    Parse do CSV de migração de NCM. Colunas: origem, destino (vazio = extinto),
    vigência início/fim (YYYY-MM-DD), ato legal. Descarta linhas sem origem válida.
    """
    rows = list(csv.reader(io.StringIO(csv_text), delimiter=delimiter))
    if not rows:
        return []
    cm = _detect(rows[0])
    if cm["ncm_origem"] is None:
        raise ValueError("CSV de migração sem coluna de NCM origem reconhecível.")

    def cell(row: list, field: str) -> Any:
        col = cm[field]
        return row[col] if col is not None and col < len(row) else None

    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        origem = _clean_ncm(cell(row, "ncm_origem"))
        if origem is None:
            continue
        out.append({
            "ncm_origem": origem,
            "ncm_destino": _clean_ncm(cell(row, "ncm_destino")),
            "vigencia_inicio": (str(cell(row, "vigencia_inicio")).strip() or None) if cell(row, "vigencia_inicio") else None,
            "vigencia_fim": (str(cell(row, "vigencia_fim")).strip() or None) if cell(row, "vigencia_fim") else None,
            "ato_legal": (str(cell(row, "ato_legal")).strip() or None) if cell(row, "ato_legal") else None,
        })
    return out


def resolve_current(ncm: str, migracoes: list[dict[str, Any]], data: date | None = None) -> str | None:
    """
    Segue a cadeia de sucessão de `ncm` até o código vigente na `data` (default: hoje).

    - Retorna o código vigente (pode ser o próprio, se não houve migração).
    - Retorna None se o código foi extinto sem sucessor (ncm_destino None) até a data.
    - Protegido contra ciclos.
    """
    alvo = data or date.today()
    # Índice: origem → lista de migrações, ordenadas por início.
    by_origem: dict[str, list[dict[str, Any]]] = {}
    for m in migracoes:
        by_origem.setdefault(m["ncm_origem"], []).append(m)

    atual = "".join(ch for ch in str(ncm) if ch.isdigit()).zfill(8)
    visitados: set[str] = set()
    while atual and atual not in visitados:
        visitados.add(atual)
        candidatas = [
            m for m in by_origem.get(atual, [])
            if not m["vigencia_inicio"] or date.fromisoformat(m["vigencia_inicio"]) <= alvo
        ]
        if not candidatas:
            return atual
        # Migração mais recente aplicável.
        m = max(candidatas, key=lambda x: x["vigencia_inicio"] or "0000-00-00")
        if m["ncm_destino"] is None:
            return None  # extinto sem sucessor
        atual = m["ncm_destino"]
    return atual
