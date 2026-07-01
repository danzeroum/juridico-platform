"""
Normalização TPU — Tabelas Processuais Unificadas do CNJ (Resolução CNJ 46/2007).

O DATAJUD entrega `classe` e `assunto` como códigos numéricos crus. Sem
canonização, agregações jurimétricas por classe/assunto ficam ruidosas (o mesmo
tema aparece sob rótulos diferentes entre tribunais). Este módulo é a fonte única
de normalização, consumida por:

- `pipeline/quality.py` (transform silver do DATAJUD) — adiciona classe_tpu/label,
  assunto_tpu/label e `ramo`;
- a camada de serviço (`services/jurimetria/`) — joins e rótulos legíveis.

Fica em `services/shared/` (par de `lgpd.py`) por ser dado de referência puro,
sem PII e sem escopo de tenant, evitando import serviço→ingest.

Carregamento: lê os JSON-semente de `services/shared/data/`. Se ausentes,
degrada para dicionário embutido mínimo — nunca levanta na importação. A tabela
completa vive em `jurimetria.tpu_classe`/`tpu_assunto` (migração 004), populada
pela ingestão; este módulo é o bootstrap/fallback offline.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent / "data"

# Fallback embutido mínimo (caso os JSON não estejam presentes no deploy).
_FALLBACK_CLASSES: dict[str, dict] = {
    "7": {"label": "Procedimento Comum Cível", "parent": None},
    "985": {"label": "Ação Trabalhista - Rito Ordinário", "parent": None},
    "1125": {"label": "Recuperação Judicial", "parent": None},
}
_FALLBACK_ASSUNTOS: dict[str, dict] = {
    "864": {"label": "DIREITO DO TRABALHO", "parent": None, "ramo": "TRABALHISTA"},
    "899": {"label": "DIREITO TRIBUTÁRIO", "parent": None, "ramo": "TRIBUTARIO"},
    "10375": {"label": "Recuperação Judicial e Falência", "parent": None, "ramo": "EMPRESARIAL"},
}


def _load(filename: str, key: str, fallback: dict[str, dict]) -> dict[str, dict]:
    path = _DATA_DIR / filename
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        table = raw.get(key, {})
        return {str(k): v for k, v in table.items()} if table else dict(fallback)
    except (OSError, ValueError) as exc:
        logger.warning("TPU: falha ao carregar %s (%s) — usando fallback embutido", filename, exc)
        return dict(fallback)


@lru_cache(maxsize=1)
def _classes() -> dict[str, dict]:
    return _load("tpu_classes.json", "classes", _FALLBACK_CLASSES)


@lru_cache(maxsize=1)
def _assuntos() -> dict[str, dict]:
    return _load("tpu_assuntos.json", "assuntos", _FALLBACK_ASSUNTOS)


def _clean_code(codigo: str | int | None) -> str | None:
    if codigo is None:
        return None
    digits = "".join(c for c in str(codigo) if c.isdigit())
    return digits or None


def normalize_classe(codigo: str | int | None) -> tuple[str | None, str | None]:
    """(codigo_canonico, label). Código desconhecido devolve (codigo, None)."""
    code = _clean_code(codigo)
    if code is None:
        return None, None
    entry = _classes().get(code)
    return code, (entry.get("label") if entry else None)


def normalize_assunto(codigo: str | int | None) -> tuple[str | None, str | None]:
    """(codigo_canonico, label). Código desconhecido devolve (codigo, None)."""
    code = _clean_code(codigo)
    if code is None:
        return None, None
    entry = _assuntos().get(code)
    return code, (entry.get("label") if entry else None)


def assunto_ramo(codigo: str | int | None) -> str:
    """
    Ramo do direito do assunto (TRABALHISTA | TRIBUTARIO | CONSUMIDOR | CIVEL |
    EMPRESARIAL | OUTRO). Sobe a hierarquia até achar um `ramo` declarado.
    """
    code = _clean_code(codigo)
    seen: set[str] = set()
    table = _assuntos()
    while code and code in table and code not in seen:
        seen.add(code)
        entry = table[code]
        if entry.get("ramo"):
            return str(entry["ramo"])
        code = _clean_code(entry.get("parent"))
    return "OUTRO"


def classe_hierarchy(codigo: str | int | None) -> list[str]:
    """Caminho da classe na árvore TPU, da raiz até o código (inclusive)."""
    code = _clean_code(codigo)
    path: list[str] = []
    seen: set[str] = set()
    table = _classes()
    while code and code in table and code not in seen:
        seen.add(code)
        path.append(code)
        code = _clean_code(table[code].get("parent"))
    return list(reversed(path))
