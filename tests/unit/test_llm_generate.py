"""Testes do helper de geração LLM (sem rede — requests mockado)."""
from __future__ import annotations

from unittest.mock import patch

from services.shared.ai import generate


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class TestOllama:
    def test_retorna_texto(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        with patch.object(generate.requests, "post", return_value=_Resp({"response": "  texto gerado  "})):
            assert generate.generate_text("oi") == "texto gerado"

    def test_resposta_vazia_vira_none(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        with patch.object(generate.requests, "post", return_value=_Resp({"response": ""})):
            assert generate.generate_text("oi") is None

    def test_falha_de_rede_degrada(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        with patch.object(generate.requests, "post", side_effect=ConnectionError("offline")):
            assert generate.generate_text("oi") is None


class TestOpenAI:
    def test_sem_chave_retorna_none(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        with patch.object(generate.requests, "post") as mock_post:
            assert generate.generate_text("oi") is None
            mock_post.assert_not_called()

    def test_com_chave_retorna_texto(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        payload = {"choices": [{"message": {"content": "defesa gerada"}}]}
        with patch.object(generate.requests, "post", return_value=_Resp(payload)):
            assert generate.generate_text("oi", system="adv") == "defesa gerada"
