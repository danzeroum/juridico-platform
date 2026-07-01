"""
Parse de tabelas de alíquotas internas de ICMS de portais SEFAZ (HTML).

Puro: recebe o HTML (renderizado pelo browser ou de uma API interna) e extrai as
linhas (produto, alíquota, fundamento). O produto é texto livre → o mapeamento
produto→NCM é feito depois por fuzzy contra fiscal.ncm.
"""
from __future__ import annotations

import re
from typing import Any

_PCT_RE = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%?")
_HEADER_HINTS = ("aliquot", "icms", "produto", "mercadoria", "descri")


def clean_percentage(text: str | None) -> float | None:
    """Extrai o valor numérico de um percentual ('18%', '18,00 %', '12.5')."""
    if not text:
        return None
    m = _PCT_RE.search(text.replace("%", " ").strip())
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _looks_like_aliquota_table(table: Any) -> bool:
    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    blob = " ".join(headers)
    return any(h in blob for h in _HEADER_HINTS)


def parse_aliquota_table(html: str, uf: str) -> list[dict[str, Any]]:
    """
    Extrai linhas de alíquota interna de ICMS do HTML. Retorna
    [{uf, produto, aliquota_pct, fundamento_legal}] apenas para linhas com alíquota.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    target = next((t for t in soup.find_all("table") if _looks_like_aliquota_table(t)), None)
    if target is None:
        return []

    rows: list[dict[str, Any]] = []
    for tr in target.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue  # linha de cabeçalho ou vazia
        cells = [td.get_text(strip=True) for td in tds]
        # A alíquota é a primeira célula que parece um percentual.
        aliquota = next((clean_percentage(c) for c in cells[1:] if clean_percentage(c) is not None), None)
        if aliquota is None:
            continue
        rows.append({
            "uf": uf.upper(),
            "produto": cells[0],
            "aliquota_pct": aliquota,
            "fundamento_legal": cells[-1] if len(cells) > 2 else None,
        })
    return rows
