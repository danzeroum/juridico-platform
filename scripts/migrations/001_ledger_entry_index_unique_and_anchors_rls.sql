-- =============================================================================
-- Migration 001: unique constraint em (tenant_id, entry_index) + tenant_id
-- e RLS em ledger.anchors
--
-- Segura para execução em banco existente (idempotente).
-- Executar como POSTGRES_USER (owner do banco), não como app_user.
-- =============================================================================

-- 1. Constraint única em (tenant_id, entry_index): transforma corrida de concorrência
--    em erro explícito em vez de corrupção silenciosa da cadeia Merkle.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ledger_entries_tenant_idx_unique'
          AND conrelid = 'ledger.entries'::regclass
    ) THEN
        ALTER TABLE ledger.entries
            ADD CONSTRAINT ledger_entries_tenant_idx_unique
            UNIQUE (tenant_id, entry_index);
    END IF;
END $$;

-- 2. Adicionar tenant_id a ledger.anchors (checkpoints são por tenant).
ALTER TABLE ledger.anchors
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant.tenants(id);

-- 3. RLS em ledger.anchors — isolamento de tenant nos checkpoints.
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

-- 4. Grants para app_user (caso migration seja aplicada após o bootstrap).
GRANT SELECT, INSERT ON ledger.anchors TO app_user;
GRANT USAGE ON SEQUENCE ledger.anchors_id_seq TO app_user;
