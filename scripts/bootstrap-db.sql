-- =============================================================================
-- Bootstrap do banco de dados PostgreSQL
-- Executado automaticamente na inicialização do container
-- =============================================================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Schema para o Decision Ledger (append-only)
CREATE SCHEMA IF NOT EXISTS ledger;

-- Tabela principal do Decision Ledger (imutável)
CREATE TABLE IF NOT EXISTS ledger.entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id      VARCHAR(64) NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    product         VARCHAR(50) NOT NULL,   -- legalscore, taxpredict, etc
    user_hash       VARCHAR(64),            -- hash do usuário (LGPD)
    inputs_hash     VARCHAR(64) NOT NULL,
    outputs_hash    VARCHAR(64) NOT NULL,
    sources         JSONB NOT NULL DEFAULT '[]',
    weights_applied JSONB NOT NULL DEFAULT '{}',
    merkle_proof    VARCHAR(64),
    merkle_root     VARCHAR(64)
);

-- Índices do Ledger
CREATE INDEX IF NOT EXISTS idx_ledger_product ON ledger.entries(product);
CREATE INDEX IF NOT EXISTS idx_ledger_created ON ledger.entries(created_at);
CREATE INDEX IF NOT EXISTS idx_ledger_request ON ledger.entries(request_id);

-- Trigger para impedir updates/deletes no ledger (append-only)
CREATE OR REPLACE FUNCTION ledger.prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Decision Ledger é imutável. Operação % não permitida.', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ledger_immutable
    BEFORE UPDATE OR DELETE ON ledger.entries
    FOR EACH ROW EXECUTE FUNCTION ledger.prevent_modification();

-- Schema de ingestão
CREATE SCHEMA IF NOT EXISTS ingest;

-- Log de ingestões
CREATE TABLE IF NOT EXISTS ingest.runs (
    id          SERIAL PRIMARY KEY,
    source      VARCHAR(50) NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status      VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, success, failed
    records_in  INTEGER DEFAULT 0,
    records_out INTEGER DEFAULT 0,
    error_msg   TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingest_runs_source ON ingest.runs(source);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_status ON ingest.runs(status);

COMMIT;
