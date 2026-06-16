"""Regras de alerta do LicitaWatch (LL01–LL04)."""

LICITAWATCH_RULES = [
    {
        "id": "LL01_concentracao_fornecedor",
        "name": "Concentração de fornecedor",
        "description": "Mais de 70% dos contratos adjudicados ao mesmo vencedor",
        "field": "pct_mesmo_vencedor",
        "threshold": 0.70,
        "severity": "ALTO",
        "cooldown_hours": 720,
    },
    {
        "id": "LL02_dispensa_excessiva",
        "name": "Uso excessivo de dispensa/inexigibilidade",
        "description": "Mais de 30% dos contratos dispensados da licitação",
        "field": "pct_dispensa",
        "threshold": 0.30,
        "severity": "ALTO",
        "cooldown_hours": 720,
    },
    {
        "id": "LL03_unico_proponente",
        "name": "Predominância de único proponente",
        "description": "Mais de 50% dos processos com apenas uma proposta",
        "field": "pct_unico_proponente",
        "threshold": 0.50,
        "severity": "CRITICO",
        "cooldown_hours": 720,
    },
    {
        "id": "LL04_prazo_curto",
        "name": "Prazo de abertura curto",
        "description": "Mais de 20% dos contratos com prazo de abertura inferior a 5 dias",
        "field": "pct_prazo_curto",
        "threshold": 0.20,
        "severity": "MEDIO",
        "cooldown_hours": 360,
    },
]
