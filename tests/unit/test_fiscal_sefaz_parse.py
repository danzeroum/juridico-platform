"""Testes reais do parse bs4 de tabela de alíquotas SEFAZ."""
from __future__ import annotations

from services.fiscal.ingestion.sefaz_parse import clean_percentage, parse_aliquota_table

HTML = """
<html><body>
  <table><tr><th>Contato</th></tr><tr><td>telefone</td></tr></table>
  <table>
    <tr><th>Produto</th><th>Alíquota ICMS</th><th>Fundamento</th></tr>
    <tr><td>Energia elétrica</td><td>25%</td><td>RICMS Art. 52, II</td></tr>
    <tr><td>Mercadoria geral</td><td>18,00 %</td><td>RICMS Art. 52, I</td></tr>
    <tr><td>Cesta básica</td><td>7%</td><td>Anexo II</td></tr>
  </table>
</body></html>
"""


class TestParseAliquotaTable:
    def test_extrai_linhas_da_tabela_certa(self):
        rows = parse_aliquota_table(HTML, "SP")
        assert len(rows) == 3
        energia = next(r for r in rows if "Energia" in r["produto"])
        assert energia["aliquota_pct"] == 25.0
        assert energia["uf"] == "SP"
        assert "Art. 52" in energia["fundamento_legal"]

    def test_aliquota_com_virgula_e_espaco(self):
        rows = parse_aliquota_table(HTML, "SP")
        geral = next(r for r in rows if "geral" in r["produto"])
        assert geral["aliquota_pct"] == 18.0

    def test_tabela_sem_aliquota_ignorada(self):
        # A tabela "Contato" não deve gerar linhas.
        rows = parse_aliquota_table(HTML, "SP")
        assert all("telefone" not in r["produto"].lower() for r in rows)

    def test_html_sem_tabela_alvo(self):
        assert parse_aliquota_table("<html><body><p>nada</p></body></html>", "RJ") == []


class TestCleanPercentage:
    def test_variacoes(self):
        assert clean_percentage("18%") == 18.0
        assert clean_percentage("12,5 %") == 12.5
        assert clean_percentage("7") == 7.0
        assert clean_percentage(None) is None
        assert clean_percentage("sem numero") is None
