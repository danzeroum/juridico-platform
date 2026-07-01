"""Testes reais do HeuristicRuleParser contra texto de convênio CONFAZ."""
from __future__ import annotations

from services.fiscal.ingestion.confaz_parse import (
    HeuristicRuleParser,
    parse_rules,
)

CONVENIO = (
    "CONVÊNIO ICMS 45/2026 - Autoriza isenção nas operações interestaduais com o "
    "produto classificado no NCM 8471.30.12, com alíquota de 7%, nas remessas do "
    "Estado de São Paulo (SP) para o Estado da Bahia (BA). "
    "Vigência a partir de 01/01/2026."
)


class TestHeuristicRuleParser:
    def test_extrai_regra_completa(self):
        regras = HeuristicRuleParser().parse(CONVENIO)
        assert len(regras) == 1
        r = regras[0]
        assert r["ncm"] == "84713012"
        assert r["aliquota_pct"] == 7.0
        assert r["uf_origem"] == "SP"
        assert r["uf_destino"] == "BA"
        assert r["vigencia_inicio"] == "01/01/2026"
        assert "45/2026" in r["ato_ref"]
        assert r["needs_review"] is True

    def test_texto_vazio(self):
        assert HeuristicRuleParser().parse("") == []

    def test_texto_sem_ncm(self):
        assert HeuristicRuleParser().parse("Convênio sem classificação fiscal.") == []

    def test_multiplos_ncm(self):
        texto = (
            "NCM 2202.10.00 alíquota de 12%. Outro item no NCM 9403.60.00 com "
            "alíquota de 18%."
        )
        regras = HeuristicRuleParser().parse(texto)
        assert {r["ncm"] for r in regras} == {"22021000", "94036000"}

    def test_parse_rules_default_heuristico(self):
        regras = parse_rules(CONVENIO)
        assert regras[0]["ncm"] == "84713012"
