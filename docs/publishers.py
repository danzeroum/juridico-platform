"""
Implementacoes do AlertPublisher.

OutboxAlertPublisher (HOJE): grava o alerta numa tabela Postgres `alerts_outbox`
DENTRO da transacao do chamador (transactional outbox). A entrega e um processo
separado que faz polling da tabela: hoje, um worker Celery; amanha, o Oban
(Elixir). O ponto-chave da fronteira: o Oban le A MESMA TABELA. Migrar para
Elixir = subir o Oban apontando para `alerts_outbox` e desligar o worker Celery
de entrega. O metodo publish() da aplicacao nao muda em nada.

HttpAlertPublisher (DEPOIS, alternativa): faz POST do envelope para um endpoint
do servico Elixir, com header X-Contract-Version. Mesma interface. Use o outbox
para a transicao Python->Elixir (mais simples e transacional); use o HTTP
quando o produtor e o consumidor ja forem servicos separados.

DDL da tabela (migration Alembic):

    CREATE TABLE alerts_outbox (
        alert_id     TEXT PRIMARY KEY,
        dedup_key    TEXT NOT NULL,
        envelope     JSONB NOT NULL,
        status       TEXT NOT NULL DEFAULT 'pending',  -- pending|claimed|done|failed
        attempts     INT  NOT NULL DEFAULT 0,
        available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_outbox_dispatch ON alerts_outbox (status, available_at);
    CREATE INDEX ix_outbox_dedup_key ON alerts_outbox (dedup_key);
    -- Dedup por alert_id determinístico (uuid5 do dedup_key) nos produtores.
    -- ON CONFLICT (alert_id) DO NOTHING é suficiente — sem partial index.
    -- ATENÇÃO: o dedup é durável apenas enquanto a linha existir na outbox.
    -- Não podar linhas dentro da janela do período de referência, ou manter
    -- tabela-tombstone de alert_ids entregues para evitar re-inserção.
"""
from __future__ import annotations

from typing import Any

import httpx

from services.shared.contracts.alerts import (
    ALERT_CONTRACT_VERSION,
    AlertEnvelope,
    PublishReceipt,
)


class OutboxAlertPublisher:
    """Insere na `alerts_outbox` de forma idempotente. A entrega e externa."""

    name = "outbox"

    def __init__(self, db_conn) -> None:
        # db_conn: conexao/psycopg compativel com .execute() e .fetchone().
        # Reutilize a conexao da transacao de negocio para garantir atomicidade
        # (o alerta so existe se a transacao que o gerou commitou).
        self._db = db_conn

    def healthy(self) -> bool:
        try:
            self._db.execute("SELECT 1")
            return True
        except Exception:
            return False

    def publish(self, envelope: AlertEnvelope) -> PublishReceipt:
        # ON CONFLICT (alert_id) DO NOTHING => idempotencia por alert_id.
        # alert_id e uuid5(dedup_key) nos produtores — mesmo evento → mesmo id.
        cur = self._db.execute(
            """
            INSERT INTO alerts_outbox (alert_id, dedup_key, envelope)
            VALUES (%(alert_id)s, %(dedup_key)s, %(envelope)s::jsonb)
            ON CONFLICT (alert_id) DO NOTHING
            RETURNING alert_id
            """,
            {
                "alert_id": envelope.alert_id,
                "dedup_key": envelope.dedup_key,
                "envelope": envelope.model_dump_json(),
            },
        )
        inserted = cur.fetchone() is not None
        return PublishReceipt(
            alert_id=envelope.alert_id,
            accepted=True,
            transport=self.name,
            dedup_hit=not inserted,
        )


class HttpAlertPublisher:
    """POST do envelope para o servico Elixir. Mesma interface."""

    name = "http"

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._url = base_url.rstrip("/") + "/api/v1/alertas/publicar"
        self._client = client or httpx.Client(timeout=5.0)

    def healthy(self) -> bool:
        try:
            return self._client.get(self._url.rsplit("/", 1)[0] + "/health").status_code == 200
        except Exception:
            return False

    def publish(self, envelope: AlertEnvelope) -> PublishReceipt:
        resp = self._client.post(
            self._url,
            content=envelope.model_dump_json(),
            headers={
                "Content-Type": "application/json",
                "X-Contract-Version": ALERT_CONTRACT_VERSION,
            },
        )
        # 202 Accepted = enfileirado; 409 = duplicado (idempotente).
        if resp.status_code not in (202, 409):
            resp.raise_for_status()
        return PublishReceipt(
            alert_id=envelope.alert_id,
            accepted=resp.status_code in (202, 409),
            transport=self.name,
            dedup_hit=resp.status_code == 409,
        )


def get_alert_publisher(backend: str, *, db_conn: Any = None, elixir_url: str = "") -> Any:
    """
    ALERT_BACKEND=outbox   # default hoje (Celery le a outbox)
    ALERT_BACKEND=http     # depois, quando o Elixir for um servico separado
    """
    backend = (backend or "outbox").lower()
    if backend == "http":
        if not elixir_url:
            raise ValueError("ALERT_BACKEND=http exige elixir_url")
        return HttpAlertPublisher(elixir_url)
    if db_conn is None:
        raise ValueError("ALERT_BACKEND=outbox exige db_conn")
    return OutboxAlertPublisher(db_conn)
