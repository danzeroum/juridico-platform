"""
Contrato da camada de alertas.

Garante que todo AlertEnvelope produzido em Python valida contra o MESMO
schema (schemas/alert.v1.json) que o consumidor Elixir vai usar. Se o Python
gerar algo que o schema rejeita, o CI quebra aqui — antes de o Elixir receber.

Rode com: pytest services/shared/alerts/tests/test_alert_contract.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from services.shared.contracts.alerts import (
    ALERT_CONTRACT_VERSION,
    AlertEnvelope,
    Channel,
    Severity,
)

SCHEMA_PATH = Path(__file__).resolve().parents[4] / "schemas" / "alert.v1.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _envelope(**overrides) -> AlertEnvelope:
    base = dict(
        alert_id="11111111-1111-1111-1111-111111111111",
        dedup_key="arrecadacao_critica:3550308:2026-06",
        rule_id="arrecadacao_critica",
        severity=Severity.CRITICAL,
        subject_ref={"municipio_ibge": "3550308"},
        payload={"delta_arrecadacao_yoy": -0.27, "z_score": 3.2},
        channels=[Channel.WEBHOOK, Channel.EMAIL],
        occurred_at=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return AlertEnvelope(**base)


def test_envelope_valida_contra_schema(schema):
    payload = json.loads(_envelope().model_dump_json())
    jsonschema.validate(instance=payload, schema=schema)  # nao lanca = ok


def test_versao_do_schema_bate(schema):
    assert _envelope().schema_version == ALERT_CONTRACT_VERSION
    assert schema["properties"]["schema_version"]["const"] == ALERT_CONTRACT_VERSION


def test_subject_ref_so_aceita_strings(schema):
    # Reforca a regra de "sem PII estruturada": valores sao referencias simples.
    payload = json.loads(_envelope().model_dump_json())
    payload["subject_ref"]["numero"] = 123  # int -> invalido pelo schema
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_channels_nao_vazio(schema):
    payload = json.loads(_envelope().model_dump_json())
    payload["channels"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_campo_desconhecido_rejeitado():
    # extra="forbid" no Pydantic + additionalProperties:false no schema:
    # ambos os lados recusam campos nao previstos (evita drift silencioso).
    with pytest.raises(Exception):
        AlertEnvelope(
            alert_id="x", dedup_key="y", rule_id="z", severity=Severity.LOW,
            channels=[Channel.WEBHOOK], occurred_at=datetime.now(timezone.utc),
            campo_fantasma="oops",
        )
