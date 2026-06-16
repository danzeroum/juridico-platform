ALERT_RULES = [
    {
        "id": "arrecadacao_critica",
        "name": "Queda critica de arrecadacao",
        "condition": "delta_arrecadacao_yoy < -0.20 AND delta_emprego_yoy < -0.10",
        "severity": "CRITICAL",
        "cooldown_hours": 24,
        "enrichment": True,
        "channels": ["webhook", "email", "slack"],
    },
    {
        "id": "saneamento_baixo",
        "name": "Cobertura de saneamento critica",
        "condition": "cobertura_agua < 50 AND cobertura_esgoto < 30",
        "severity": "HIGH",
        "cooldown_hours": 720,
        "enrichment": False,
        "channels": ["webhook"],
    },
]
