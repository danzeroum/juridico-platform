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

Carregamento: usa a semente Python `services/shared/tpu_seed.py` (versionada e
sempre presente). A tabela COMPLETA vive em `jurimetria.tpu_classe`/`tpu_assunto`
(migração 004), populada pela ingestão; este módulo é o normalizador offline.
"""
from __future__ import annotations

from services.shared.tpu_seed import ASSUNTOS as _ASSUNTOS
from services.shared.tpu_seed import CLASSES as _CLASSES


def _classes() -> dict[str, dict]:
    return _CLASSES


def _assuntos() -> dict[str, dict]:
    return _ASSUNTOS


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
