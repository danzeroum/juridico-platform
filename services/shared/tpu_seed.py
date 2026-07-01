"""
Semente TPU (Tabelas Processuais Unificadas do CNJ) — subconjunto de referência.

Embutido como módulo Python (não JSON em `data/`) porque `data/` é ignorado pelo
.gitignore e não seria versionado/empacotado — isso quebrava a normalização no CI.
A tabela COMPLETA é carregada em `jurimetria.tpu_classe`/`tpu_assunto` pela
ingestão (migração 004); este módulo é a semente/fallback offline determinístico.

Fonte: CNJ — Resolução CNJ 46/2007.
"""
from __future__ import annotations

CLASSES: dict[str, dict] = {
    "1116": {"label": "Cumprimento de Sentença", "parent": None},
    "156": {"label": "Execução de Título Extrajudicial", "parent": None},
    "7": {"label": "Procedimento Comum Cível", "parent": None},
    "985": {"label": "Ação Trabalhista - Rito Ordinário", "parent": None},
    "1125": {"label": "Recuperação Judicial", "parent": None},
    "132": {"label": "Falência de Empresários e Sociedades", "parent": None},
    "319": {"label": "Mandado de Segurança Cível", "parent": None},
    "1727": {"label": "Execução Fiscal", "parent": None},
    "436": {"label": "Procedimento do Juizado Especial Cível", "parent": None},
    "202": {"label": "Ação Civil Pública", "parent": None},
}

ASSUNTOS: dict[str, dict] = {
    "864": {"label": "DIREITO DO TRABALHO", "parent": None, "ramo": "TRABALHISTA"},
    "1937": {"label": "Rescisão do Contrato de Trabalho", "parent": "864", "ramo": "TRABALHISTA"},
    "2546": {"label": "Verbas Rescisórias", "parent": "864", "ramo": "TRABALHISTA"},
    "899": {"label": "DIREITO TRIBUTÁRIO", "parent": None, "ramo": "TRIBUTARIO"},
    "5952": {"label": "ICMS", "parent": "899", "ramo": "TRIBUTARIO"},
    "6017": {"label": "PIS/COFINS", "parent": "899", "ramo": "TRIBUTARIO"},
    "1156": {"label": "DIREITO DO CONSUMIDOR", "parent": None, "ramo": "CONSUMIDOR"},
    "7771": {"label": "Práticas Abusivas", "parent": "1156", "ramo": "CONSUMIDOR"},
    "10375": {"label": "Recuperação Judicial e Falência", "parent": None, "ramo": "EMPRESARIAL"},
    "10376": {"label": "Concurso de Credores", "parent": "10375", "ramo": "EMPRESARIAL"},
    "9985": {"label": "Direito Societário", "parent": None, "ramo": "EMPRESARIAL"},
}
