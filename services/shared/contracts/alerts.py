"""
Contrato da camada de alertas (FRONTEIRA Python <-> Elixir).

A aplicacao publica alertas atraves da interface AlertPublisher e NUNCA sabe
quem entrega: hoje um worker Celery, amanha um servico Elixir/Oban. A mensagem
trafega como um AlertEnvelope versionado, validado contra o JSON Schema
compartilhado em schemas/alert.v1.json — a fonte de verdade que os dois lados
(Python e Elixir) honram.

Decisao de privacidade: `subject_ref` carrega apenas referencias NAO pessoais
(municipio IBGE, CNPJ — dado publico). Nenhum dado pessoal (CPF, nome) entra no
envelope, que pode trafegar por filas, webhooks e logs.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

ALERT_CONTRACT_VERSION = "alerts/v1"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Channel(StrEnum):
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    WHATSAPP = "whatsapp"


class AlertEnvelope(BaseModel):
    """Mensagem versionada e imutavel. Este e o contrato com o Elixir."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = ALERT_CONTRACT_VERSION
    alert_id: str  # UUID — chave de idempotencia (insert ON CONFLICT DO NOTHING)
    dedup_key: str  # chave de deduplicacao temporal (cooldown de 24h)
    rule_id: str
    severity: Severity
    subject_ref: dict[str, str] = Field(default_factory=dict)  # sem PII
    payload: dict[str, Any] = Field(default_factory=dict)
    channels: list[Channel]
    occurred_at: datetime
    enrichment: bool = False


class PublishReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    alert_id: str
    accepted: bool
    transport: str  # "outbox" | "http"
    dedup_hit: bool = False  # True se ja existia (idempotencia/cooldown)


@runtime_checkable
class AlertPublisher(Protocol):
    name: str

    def healthy(self) -> bool:
        ...

    def publish(self, envelope: AlertEnvelope) -> PublishReceipt:
        ...
