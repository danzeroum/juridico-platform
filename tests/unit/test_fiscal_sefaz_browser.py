"""
Teste REAL de navegador: renderiza uma página com tabela injetada via JS num
Chromium headless (Playwright) e confirma que o scraper extrai as alíquotas do DOM
pós-JavaScript — exatamente o que os portais SEFAZ modernos exigem.

Pula automaticamente se o Playwright ou um binário do Chromium não estiverem
disponíveis (ex.: runner de CI sem browser). Localmente/no CI com Chromium, roda de verdade.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright")

from services.fiscal.ingestion.browser import (  # noqa: E402
    fetch_html,
    resolve_chromium_executable,
)
from services.fiscal.ingestion.sefaz_parse import parse_aliquota_table  # noqa: E402

# Tabela criada SÓ via JS (só existe no DOM após o script rodar → prova a renderização).
PAGE = """<!doctype html><html><body><div id="app"></div>
<script>
  const t = document.createElement('table');
  t.innerHTML =
    '<tr><th>Produto</th><th>Aliquota ICMS</th><th>Fundamento</th></tr>' +
    '<tr><td>Energia eletrica</td><td>25%</td><td>Art. 52 II</td></tr>' +
    '<tr><td>Notebook</td><td>18%</td><td>Art. 52 I</td></tr>';
  document.getElementById('app').appendChild(t);
</script></body></html>"""


def _browser_available() -> bool:
    if resolve_chromium_executable() is not None:
        return True
    # Deixa o Playwright tentar seu próprio browser empacotado.
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=["--no-sandbox"])
            b.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _browser_available(), reason="Chromium indisponível — teste de navegador pulado."
)


def test_scraper_le_tabela_renderizada_por_js(tmp_path):
    page = tmp_path / "sefaz.html"
    page.write_text(PAGE, encoding="utf-8")

    html = fetch_html(page.as_uri(), wait_selector="table")

    # O HTML retornado é o DOM renderizado — a <table> só existe pós-JS.
    assert "<table" in html.lower()
    rows = parse_aliquota_table(html, "SP")
    assert len(rows) == 2
    energia = next(r for r in rows if "Energia" in r["produto"])
    assert energia["aliquota_pct"] == 25.0
    assert energia["uf"] == "SP"
