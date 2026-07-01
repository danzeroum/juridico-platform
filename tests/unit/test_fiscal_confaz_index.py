"""Teste real do parser do índice do CONFAZ (extração de links de PDF)."""
from __future__ import annotations

from services.fiscal.ingestion.confaz_index import parse_convenio_links

BASE = "https://www.confaz.fazenda.gov.br/legislacao/convenios"
HTML = """
<html><body>
  <ul>
    <li><a href="/legislacao/convenios/2026/cv045_26.pdf">Convênio ICMS 45/2026</a></li>
    <li><a href="https://www.confaz.fazenda.gov.br/legislacao/protocolos/pt010_26.pdf">Protocolo ICMS 10/2026</a></li>
    <li><a href="/legislacao/convenios/2026/cv045_26.pdf">Convênio ICMS 45/2026 (duplicado)</a></li>
    <li><a href="/sobre/index.html">Página institucional</a></li>
    <li><a href="/downloads/manual.pdf">Manual do usuário</a></li>
  </ul>
</body></html>
"""


class TestParseConvenioLinks:
    def test_extrai_pdfs_de_convenio_absolutos(self):
        links = parse_convenio_links(HTML, BASE)
        assert "https://www.confaz.fazenda.gov.br/legislacao/convenios/2026/cv045_26.pdf" in links
        assert "https://www.confaz.fazenda.gov.br/legislacao/protocolos/pt010_26.pdf" in links

    def test_deduplica(self):
        links = parse_convenio_links(HTML, BASE)
        assert len(links) == len(set(links))
        assert len(links) == 2  # 2 únicos (o duplicado é colapsado)

    def test_ignora_nao_pdf_e_pdf_nao_convenio(self):
        links = parse_convenio_links(HTML, BASE)
        assert all(link.endswith(".pdf") for link in links)
        assert not any("manual.pdf" in link for link in links)  # PDF sem indício de convênio
        assert not any("index.html" in link for link in links)

    def test_html_sem_links(self):
        assert parse_convenio_links("<html><body>vazio</body></html>", BASE) == []
