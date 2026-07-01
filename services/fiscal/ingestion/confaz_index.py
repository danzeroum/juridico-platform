"""
Descoberta de links de convênios/protocolos do CONFAZ (parse do índice → PDFs).

Puro: recebe o HTML da página de índice e devolve as URLs absolutas dos PDFs de
convênios/protocolos. A task de descoberta busca o índice e enfileira o confaz_ocr
por link (dedup por hash já é feito no confaz_ocr).
"""
from __future__ import annotations

from urllib.parse import urljoin

_CONVENIO_HINTS = ("convenio", "convênio", "protocolo", "/cv", "/pt", "icms")


def parse_convenio_links(html: str, base_url: str) -> list[str]:
    """
    Extrai as URLs absolutas dos PDFs de convênios/protocolos do índice do CONFAZ.
    Filtra por extensão .pdf e por indícios de convênio/protocolo no href/texto.
    Deduplica preservando a ordem.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()
        if not low.endswith(".pdf"):
            continue
        texto = a.get_text(" ", strip=True).lower()
        if not any(h in low or h in texto for h in _CONVENIO_HINTS):
            continue
        url = href if low.startswith("http") else urljoin(base_url, href)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out
