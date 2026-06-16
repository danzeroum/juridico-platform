# ----------------------------------------------------------------------------
# ContabilIA - Cross-check engine
# Cruza demonstracoes financeiras com 14 fontes de dados publicos
# ----------------------------------------------------------------------------

from typing import Dict, List


CROSS_CHECK_RULES = {
    "CC01": {
        "name": "Empregados vs CAGED",
        "severity": "ALTO",
        "logic": "Delta > 20% entre folha e vinculos",
    },
    "CC02": {
        "name": "Receita vs SICONFI",
        "severity": "CRITICO",
        "logic": "Delta > 30% (prefeituras)",
    },
    "CC03": {
        "name": "Contratos vs PNCP",
        "severity": "MEDIO",
        "logic": "Receita sem contratos correspondentes",
    },
    "CC04": {
        "name": "Importacoes vs Estoque",
        "severity": "MEDIO",
        "logic": "Crescimento desproporcional",
    },
}


class CrossCheckEngine:
    def run_checks(self, financials: Dict, public_data: Dict) -> List[Dict]:
        findings = []
        # TODO: implementar regras na Fase 2
        return findings
