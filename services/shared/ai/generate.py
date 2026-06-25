"""
Geração de texto via LLM — Ollama local ou API OpenAI-compatível.

Degradação graciosa: `generate_text` retorna None quando o provedor está
indisponível (sem chave, serviço offline, host bloqueado), permitindo que o
chamador caia para um template determinístico. É assim que o Defensor passa a
redigir a defesa "de verdade" quando há LLM, sem quebrar quando não há.

Provedor escolhido por settings.LLM_PROVIDER (ollama|openai).
"""
from __future__ import annotations

import logging

import requests

from services.shared.config import settings

logger = logging.getLogger(__name__)

# (connect, read) — falha rápido em DNS/conn para não travar o request quando offline.
_TIMEOUT = (3, 30)


def generate_text(prompt: str, *, system: str | None = None, max_tokens: int = 600) -> str | None:
    """
    Gera texto a partir de `prompt`. Retorna o texto ou None em qualquer falha.

    Nunca levanta exceção — degradação graciosa é parte do contrato.
    """
    provider = settings.LLM_PROVIDER.lower()
    try:
        if provider == "openai":
            return _openai(prompt, system, max_tokens)
        return _ollama(prompt, system, max_tokens)
    except Exception as exc:
        logger.warning("Geração LLM indisponível (provider=%s): %s", provider, exc)
        return None


def _ollama(prompt: str, system: str | None, max_tokens: int) -> str | None:
    payload: dict = {
        "model": settings.LLM_MODEL_LOCAL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.3},
    }
    if system:
        payload["system"] = system
    resp = requests.post(f"{settings.OLLAMA_URL}/api/generate", json=payload, timeout=_TIMEOUT)
    resp.raise_for_status()
    text = (resp.json().get("response") or "").strip()
    return text or None


def _openai(prompt: str, system: str | None, max_tokens: int) -> str | None:
    if not settings.LLM_API_KEY:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        f"{settings.LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        json={
            "model": settings.LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
    return text or None
