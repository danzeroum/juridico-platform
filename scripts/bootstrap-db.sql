-- =============================================================================
-- Bootstrap do banco de dados PostgreSQL
-- Executado automaticamente na inicialização do container
-- =============================================================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- Schema de tenants (multi-tenancy)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS tenant;

CREATE TABLE IF NOT EXISTS tenant.tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug        VARCHAR(64) NOT NULL UNIQUE,     -- identificador único (ex: "empresa-abc")
    name        VARCHAR(255) NOT NULL,
    plan        VARCHAR(50) NOT NULL DEFAULT 'starter',
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant.users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenant.tenants(id),
    email       VARCHAR(255) NOT NULL,
    role        VARCHAR(50) NOT NULL DEFAULT 'viewer',  -- admin | analyst | viewer
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, email)
);

-- Idempotência de Idempotency-Key por tenant (TTL de 24h aplicado via cron ou particionamento)
CREATE TABLE IF NOT EXISTS tenant.idempotency_keys (
    key         TEXT NOT NULL,
    tenant_id   UUID NOT NULL,
    response    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_created ON tenant.idempotency_keys (created_at);

-- =============================================================================
-- Schema para o Decision Ledger (append-only, 7 anos de retenção)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS ledger;

CREATE TABLE IF NOT EXISTS ledger.entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id      VARCHAR(64) NOT NULL UNIQUE,
    entry_index     BIGINT NOT NULL,                -- posição na árvore Merkle
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    product         VARCHAR(50) NOT NULL,           -- legalscore, taxpredict, etc.
    tenant_id       UUID REFERENCES tenant.tenants(id),
    inputs_hash     VARCHAR(64) NOT NULL,
    outputs_hash    VARCHAR(64) NOT NULL,
    sources         JSONB NOT NULL DEFAULT '[]',
    weights_applied JSONB NOT NULL DEFAULT '{}',
    subject_token   TEXT,                           -- pseudônimo cifrado AES-256-GCM (não PII)
    leaf_hash       VARCHAR(64),                    -- hash da entrada nesta posição da árvore
    merkle_root     VARCHAR(64),                    -- raiz no momento da inserção
    -- Garante que dois requests concorrentes do mesmo tenant não bifurcam a cadeia Merkle.
    -- Sem esta constraint, um entry_index duplicado corrompe silenciosamente a prova.
    CONSTRAINT ledger_entries_tenant_idx_unique UNIQUE (tenant_id, entry_index)
);

CREATE INDEX IF NOT EXISTS idx_ledger_product   ON ledger.entries(product);
CREATE INDEX IF NOT EXISTS idx_ledger_created   ON ledger.entries(created_at);
CREATE INDEX IF NOT EXISTS idx_ledger_request   ON ledger.entries(request_id);
CREATE INDEX IF NOT EXISTS idx_ledger_tenant    ON ledger.entries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ledger_index     ON ledger.entries(entry_index);

-- Trigger: ledger é append-only — sem UPDATE ou DELETE
CREATE OR REPLACE FUNCTION ledger.prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Decision Ledger é imutável. Operação % não permitida.', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ledger_immutable ON ledger.entries;
CREATE TRIGGER ledger_immutable
    BEFORE UPDATE OR DELETE ON ledger.entries
    FOR EACH ROW EXECUTE FUNCTION ledger.prevent_modification();

-- Âncoras periódicas: checkpoint de raiz Merkle a cada _ANCHOR_INTERVAL entradas.
-- tenant_id: necessário para RLS (cada tenant tem sua própria cadeia de âncoras).
-- Não reduz O(N) do recálculo atual; suporta auditoria histórica sem replay total.
-- Migração para O(log N) requer MMR (ver Pendencia.md QT-08).
CREATE TABLE IF NOT EXISTS ledger.anchors (
    id              SERIAL PRIMARY KEY,
    anchor_at_index BIGINT NOT NULL,
    merkle_root     VARCHAR(64) NOT NULL,
    tenant_id       UUID REFERENCES tenant.tenants(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Schema de ingestão com linhagem completa
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS ingest;

CREATE TABLE IF NOT EXISTS ingest.runs (
    id              SERIAL PRIMARY KEY,
    source          VARCHAR(50) NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, success, failed
    records_in      INTEGER DEFAULT 0,
    records_out     INTEGER DEFAULT 0,
    transform_version VARCHAR(20),                           -- semver da versão ETL
    error_msg       TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingest_runs_source ON ingest.runs(source);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_status ON ingest.runs(status);

-- =============================================================================
-- Tabela de alertas (outbox pattern — fonte única de verdade para entregas)
-- Consumida por Celery (hoje) ou Oban/Elixir (quando gatilho de SLA disparar)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.alerts_outbox (
    alert_id        TEXT PRIMARY KEY,                       -- UUID, chave de idempotência
    dedup_key       TEXT NOT NULL,
    envelope        JSONB NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',        -- pending|claimed|done|failed
    attempts        INT  NOT NULL DEFAULT 0,
    available_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_outbox_dispatch ON public.alerts_outbox (status, available_at);

-- Cooldown de 24h: dedup_key único dentro da janela (evita alertas duplicados)
DROP INDEX IF EXISTS ux_outbox_dedup_window;
CREATE UNIQUE INDEX ux_outbox_dedup_window
    ON public.alerts_outbox (dedup_key)
    WHERE created_at > NOW() - INTERVAL '24 hours';

-- =============================================================================
-- Row-Level Security (RLS) — isolamento de tenant
--
-- ARMADILHA PgBouncer (pool_mode: transaction):
--   A conexão de servidor é reutilizada entre requests de tenants diferentes.
--   NÃO usar SET app.tenant_id (sem LOCAL): persiste na conexão e vaza.
--   USAR SEMPRE: SET LOCAL app.tenant_id = :id  (dentro de BEGIN...COMMIT)
--   A policy abaixo usa current_setting SEM missing_ok → falha fechado se
--   o GUC não estiver definido (não vaza dados de tenant indefinido).
-- =============================================================================

ALTER TABLE ledger.entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger.entries FORCE ROW LEVEL SECURITY;

-- ATENÇÃO: com FORCE ROW LEVEL SECURITY o owner da tabela É sujeito à RLS.
-- Porém, superusuários (SUPERUSER) AINDA bypassam FORCE RLS no PostgreSQL —
-- esse bypass não pode ser eliminado por política SQL.
-- A aplicação DEVE conectar como app_user (definido abaixo), NÃO como postgres.
ALTER TABLE ledger.entries OWNER TO CURRENT_USER;

DROP POLICY IF EXISTS ledger_tenant_isolation ON ledger.entries;
CREATE POLICY ledger_tenant_isolation ON ledger.entries
    USING (
        tenant_id = (current_setting('app.tenant_id'))::uuid
    );

-- Policy para SELECT (leitura restrita ao tenant)
DROP POLICY IF EXISTS ledger_tenant_select ON ledger.entries;
CREATE POLICY ledger_tenant_select ON ledger.entries
    FOR SELECT
    USING (
        tenant_id = (current_setting('app.tenant_id'))::uuid
    );

-- Policy para INSERT (só o tenant correto pode inserir)
DROP POLICY IF EXISTS ledger_tenant_insert ON ledger.entries;
CREATE POLICY ledger_tenant_insert ON ledger.entries
    FOR INSERT
    WITH CHECK (
        tenant_id = (current_setting('app.tenant_id'))::uuid
    );

-- RLS para ledger.anchors (checkpoints de raiz por tenant)
ALTER TABLE ledger.anchors ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger.anchors FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ledger_anchors_tenant_isolation ON ledger.anchors;
CREATE POLICY ledger_anchors_tenant_isolation ON ledger.anchors
    USING (
        tenant_id = (current_setting('app.tenant_id'))::uuid
    );

DROP POLICY IF EXISTS ledger_anchors_tenant_insert ON ledger.anchors;
CREATE POLICY ledger_anchors_tenant_insert ON ledger.anchors
    FOR INSERT
    WITH CHECK (
        tenant_id = (current_setting('app.tenant_id'))::uuid
    );

-- RLS para idempotency_keys (isolamento de tenant)
ALTER TABLE tenant.idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant.idempotency_keys FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS idempotency_tenant_isolation ON tenant.idempotency_keys;
CREATE POLICY idempotency_tenant_isolation ON tenant.idempotency_keys
    USING (
        tenant_id = (current_setting('app.tenant_id'))::uuid
    );

-- =============================================================================
-- Dados iniciais para desenvolvimento
-- =============================================================================
INSERT INTO tenant.tenants (id, slug, name, plan)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'dev-tenant',
    'Tenant de Desenvolvimento',
    'enterprise'
) ON CONFLICT (slug) DO NOTHING;

-- =============================================================================
-- Role de aplicação dedicado (não-superusuário)
--
-- Superusuários bypassam FORCE ROW LEVEL SECURITY no PostgreSQL.
-- DATABASE_URL DEVE apontar para app_user, nunca para postgres.
-- Senha padrão abaixo deve ser substituída por Docker Secret em produção:
--   docker secret create DB_APP_PASSWORD <(openssl rand -hex 32)
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT LOGIN
            PASSWORD 'change_in_production';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA ledger TO app_user;
GRANT USAGE ON SCHEMA tenant TO app_user;
GRANT USAGE ON SCHEMA ingest TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- Ledger: INSERT + SELECT apenas (UPDATE/DELETE bloqueado por trigger)
GRANT SELECT, INSERT ON ledger.entries TO app_user;
GRANT SELECT, INSERT ON ledger.anchors TO app_user;
GRANT USAGE ON SEQUENCE ledger.anchors_id_seq TO app_user;

-- Tenant: leitura de tenants/users; escrita completa em idempotency_keys
GRANT SELECT ON tenant.tenants TO app_user;
GRANT SELECT ON tenant.users TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant.idempotency_keys TO app_user;

-- Alertas outbox: leitura + escrita + atualização de status (worker Celery/Oban)
GRANT SELECT, INSERT, UPDATE ON public.alerts_outbox TO app_user;

-- =============================================================================
-- Tabela de sonda para testes de isolamento de tenant (CI + integração local)
-- Criada pelo bootstrap para que os testes rodem como app_user sem DDL privileges.
-- Pré-condição: testes de integração em CI executam bootstrap-db.sql antes de rodar.
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.tenant_isolation_probe (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    payload   TEXT NOT NULL
);

ALTER TABLE public.tenant_isolation_probe ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_isolation_probe FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS probe_isolation ON public.tenant_isolation_probe;
CREATE POLICY probe_isolation ON public.tenant_isolation_probe
    USING (tenant_id = (current_setting('app.tenant_id'))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id'))::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.tenant_isolation_probe TO app_user;

COMMIT;
