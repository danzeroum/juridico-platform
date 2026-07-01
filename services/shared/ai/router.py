"""
LLM Router: decide automaticamente entre modelo local (Ollama) e API paga.

Custo zero para: classificacao, NER, embeddings (Llama3:8b + BGE-M3 via Ollama)
API paga para: geracao de texto juridico, raciocinio complexo, sumarizacao
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    CLASSIFICATION = "classification"      # Ollama local - GRATIS
    NER = "ner"                            # Ollama local - GRATIS
    EMBEDDING = "embedding"                # Ollama local - GRATIS
    GENERATION = "generation"              # API paga - ~$0.01/req
    REASONING = "reasoning"                # API paga - ~$0.03/req
    SUMMARIZATION = "summarization"        # API paga (mini) - ~$0.002/req


ROUTING_TABLE = {
    TaskType.CLASSIFICATION: {"provider": "ollama", "model": "llama3:8b",  "cost": 0.0},
    TaskType.NER:            {"provider": "ollama", "model": "llama3:8b",  "cost": 0.0},
    TaskType.EMBEDDING:      {"provider": "ollama", "model": "bge-m3",      "cost": 0.0},
    TaskType.GENERATION:     {"provider": "openai", "model": "gpt-4o",      "cost": 0.01},
    TaskType.REASONING:      {"provider": "openai", "model": "gpt-4o",      "cost": 0.03},
    TaskType.SUMMARIZATION:  {"provider": "openai", "model": "gpt-4o-mini", "cost": 0.002},
}


class LLMRouter:
    def route(self, task_type: TaskType) -> dict:
        config = ROUTING_TABLE[task_type]
        logger.debug(f"LLM route: {task_type.value} -> {config['provider']}/{config['model']}")
        return config

    def get_client(self, task_type: TaskType):
        """Retorna cliente configurado para o tipo de task."""
        config = self.route(task_type)
        if config["provider"] == "ollama":
            return self._ollama_client(config["model"])
        return self._openai_client(config["model"])

    def _ollama_client(self, model: str):
        # TODO: implementar cliente Ollama na Fase 1
        from services.shared.config import settings
        return {"url": settings.OLLAMA_URL, "model": model}

    def _openai_client(self, model: str):
        # TODO: implementar cliente OpenAI na Fase 1
        from services.shared.config import settings
        return {"api_key": settings.LLM_API_KEY, "model": model}


llm_router = LLMRouter()
