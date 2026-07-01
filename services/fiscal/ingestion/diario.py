"""
Monitor de Diário Oficial — detecção de alteração fiscal (lógica pura).

A alíquota interna muda com frequência (guerra fiscal); o monitor roda diariamente,
detecta mudança real via hash do documento e sinaliza para revisão humana quando o
texto contém termos fiscais relevantes. Aqui vive só a lógica determinística; o
download e a persistência do hash (fiscal.doc_hash) ficam no wrapper Celery.
"""
from __future__ import annotations

import hashlib
import re

# Termos que indicam alteração fiscal potencialmente relevante.
FISCAL_TERMS = [
    r"\bICMS\b",
    r"\bal[íi]quota\b",
    r"\bCONFAZ\b",
    r"\bisen[çc][ãa]o\b",
    r"\bRICMS\b",
    r"\bsubstitui[çc][ãa]o\s+tribut[áa]ria\b",
    r"\bFECP\b",
    r"\bFCP\b",
    r"\bdecreto\b",
    r"\bconv[êe]nio\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in FISCAL_TERMS]


def file_sha256(data: bytes) -> str:
    """Hash SHA-256 do documento — chave de deduplicação/detecção de mudança."""
    return hashlib.sha256(data).hexdigest()


def matched_fiscal_terms(text: str) -> list[str]:
    """Termos fiscais encontrados no texto (nomes canônicos, sem duplicar)."""
    found: list[str] = []
    for pat in _COMPILED:
        m = pat.search(text)
        if m:
            token = m.group(0).upper()
            if token not in found:
                found.append(token)
    return found


def is_fiscally_relevant(text: str, *, min_terms: int = 1) -> bool:
    """True se o texto tem pelo menos `min_terms` termos fiscais distintos."""
    return len(matched_fiscal_terms(text)) >= min_terms
