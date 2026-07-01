-- =============================================================================
-- Migration 003: schema `fiscal` — módulo FiscalEngine (NCM + ICMS)
--
-- Tabelas de REFERÊNCIA (globais, dado público igual para todo tenant) — SEM RLS,
-- apenas GRANT ao app_user. Tabelas de JOBS/RESULTADOS (por tenant) — com RLS
-- FORCED, no mesmo padrão de ledger.entries.
--
-- Segura para execução em banco existente (idempotente).
-- Executar como POSTGRES_USER (owner do banco), não como app_user.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS fiscal;

-- btree_gist habilita operador `=` sobre tipos escalares dentro de índices/constraints
-- GiST — necessário para as constraints EXCLUDE de não-sobreposição de vigência.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- -----------------------------------------------------------------------------
-- 1. NCM — Nomenclatura Comum do Mercosul (8 dígitos), temporal.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fiscal.ncm (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ncm_codigo         CHAR(8) NOT NULL,
    descricao          TEXT NOT NULL,
    capitulo           CHAR(2),
    vigencia           DATERANGE NOT NULL DEFAULT daterange(CURRENT_DATE, NULL),
    source             VARCHAR(50) NOT NULL DEFAULT 'TIPI',
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transform_version  VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    -- Uma vigência por código: nunca duas descrições vigentes na mesma data.
    CONSTRAINT no_overlap_ncm
        EXCLUDE USING gist (ncm_codigo WITH =, vigencia WITH &&)
);
CREATE INDEX IF NOT EXISTS idx_ncm_codigo ON fiscal.ncm (ncm_codigo);

-- 2. Histórico de migração de códigos NCM (unificação/desmembramento/extinção).
CREATE TABLE IF NOT EXISTS fiscal.ncm_migracao (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ncm_origem       CHAR(8) NOT NULL,
    ncm_destino      CHAR(8),                -- NULL = código extinto sem sucessor
    vigencia_inicio  DATE NOT NULL,
    vigencia_fim     DATE,
    ato_legal        TEXT,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ncm_migracao_origem ON fiscal.ncm_migracao (ncm_origem);

-- 3. IPI por NCM (TIPI). Campo EX (exceção) tratado à parte — maior foco de erro.
--    NULLS NOT DISTINCT (PG15+): trata múltiplos EX nulos como o mesmo valor,
--    permitindo ON CONFLICT (ncm_codigo, excecao) limpo, sem COALESCE.
CREATE TABLE IF NOT EXISTS fiscal.ipi_aliquota (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ncm_codigo         CHAR(8) NOT NULL,
    excecao            VARCHAR(10),
    aliquota_pct       NUMERIC(6,3) NOT NULL,
    vigencia           DATERANGE NOT NULL DEFAULT daterange(CURRENT_DATE, NULL),
    fundamento_legal   TEXT,
    source             VARCHAR(50) NOT NULL DEFAULT 'TIPI',
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transform_version  VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    CONSTRAINT uq_ipi_ncm_excecao UNIQUE NULLS NOT DISTINCT (ncm_codigo, excecao),
    CONSTRAINT no_overlap_ipi
        EXCLUDE USING gist (ncm_codigo WITH =, (COALESCE(excecao, '')) WITH =, vigencia WITH &&)
);

-- 4. ICMS interestadual — fundamento é RESOLUÇÃO DO SENADO FEDERAL (22/1989, 13/2012),
--    NÃO CONFAZ. 4% aplica-se só a importados com conteúdo de importação > 40%.
CREATE TABLE IF NOT EXISTS fiscal.icms_interestadual (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uf_origem          CHAR(2) NOT NULL,
    uf_destino         CHAR(2) NOT NULL,
    aliquota_pct       NUMERIC(5,2) NOT NULL,
    importado          BOOLEAN NOT NULL DEFAULT FALSE,
    fundamento_legal   TEXT,
    vigencia           DATERANGE NOT NULL DEFAULT daterange(CURRENT_DATE, NULL),
    source             VARCHAR(50) NOT NULL DEFAULT 'SENADO',
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT no_overlap_icms_inter
        EXCLUDE USING gist (uf_origem WITH =, uf_destino WITH =, importado WITH =, vigencia WITH &&)
);

-- 5. ICMS interno por UF. Alíquota efetiva = aliquota_pct + COALESCE(fcp_pct, 0)
--    (FCP/FECP tem base legal e vigência próprias). ibs_pct/cbs_pct reservados
--    para a transição da reforma tributária (EC 132/2023, LC 214/2025).
CREATE TABLE IF NOT EXISTS fiscal.icms_interno (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uf                 CHAR(2) NOT NULL,
    ncm_prefix         VARCHAR(8),             -- NULL = alíquota geral do estado
    aliquota_pct       NUMERIC(5,2) NOT NULL,
    fcp_pct            NUMERIC(5,2),           -- Fundo de Combate à Pobreza / FECP
    ibs_pct            NUMERIC(5,2),           -- reservado — transição IBS
    cbs_pct            NUMERIC(5,2),           -- reservado — transição CBS
    fundamento_legal   TEXT,
    vigencia           DATERANGE NOT NULL DEFAULT daterange(CURRENT_DATE, NULL),
    source             VARCHAR(50) NOT NULL DEFAULT 'SEFAZ',
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transform_version  VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    CONSTRAINT no_overlap_icms_interno
        EXCLUDE USING gist (uf WITH =, (COALESCE(ncm_prefix, '')) WITH =, vigencia WITH &&)
);
CREATE INDEX IF NOT EXISTS idx_icms_interno_uf ON fiscal.icms_interno (uf);

-- 6. Categorias contábeis e mapa NCM→categoria.
CREATE TABLE IF NOT EXISTS fiscal.categoria (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(64) NOT NULL UNIQUE,
    nome        VARCHAR(120) NOT NULL,
    descricao   TEXT
);
CREATE TABLE IF NOT EXISTS fiscal.ncm_categoria (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ncm_prefix    VARCHAR(8) NOT NULL,
    categoria_id  UUID NOT NULL REFERENCES fiscal.categoria(id),
    confianca     NUMERIC(4,3) NOT NULL DEFAULT 1.0,
    CONSTRAINT uq_ncm_categoria UNIQUE (ncm_prefix, categoria_id)
);

-- 7. Dedupe/monitoramento de PDFs (Diário Oficial, CONFAZ) por hash.
CREATE TABLE IF NOT EXISTS fiscal.doc_hash (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fonte         VARCHAR(50) NOT NULL,
    file_hash     CHAR(64) NOT NULL,
    url           TEXT,
    processed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_doc_hash UNIQUE (fonte, file_hash)
);

-- Grants nas tabelas de referência (globais, sem RLS).
GRANT SELECT, INSERT, UPDATE, DELETE ON
    fiscal.ncm, fiscal.ncm_migracao, fiscal.ipi_aliquota, fiscal.icms_interestadual,
    fiscal.icms_interno, fiscal.categoria, fiscal.ncm_categoria, fiscal.doc_hash
    TO app_user;

-- -----------------------------------------------------------------------------
-- 8. Jobs e resultados de triagem — POR TENANT (RLS FORCED).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fiscal.triage_job (
    job_id             VARCHAR(64) PRIMARY KEY,
    tenant_id          UUID NOT NULL REFERENCES tenant.tenants(id),
    status             VARCHAR(20) NOT NULL DEFAULT 'queued',
    total              INTEGER NOT NULL DEFAULT 0,
    processed          INTEGER NOT NULL DEFAULT 0,
    spreadsheet_key    TEXT,
    result_key         TEXT,
    batch_merkle_root  CHAR(64),
    ledger_request_id  VARCHAR(64),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS fiscal.triage_item (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                    VARCHAR(64) NOT NULL REFERENCES fiscal.triage_job(job_id),
    tenant_id                 UUID NOT NULL REFERENCES tenant.tenants(id),
    leaf_index                INTEGER NOT NULL,
    sku_descricao             TEXT,
    ncm_sugerido              CHAR(8),
    confidence                NUMERIC(4,3),
    fonte_regra               VARCHAR(20),
    icms_interno_efetivo_pct  NUMERIC(5,2),
    icms_inter_pct            NUMERIC(5,2),
    difal_pct                 NUMERIC(5,2),
    categoria                 VARCHAR(64),
    conflito                  BOOLEAN NOT NULL DEFAULT FALSE,
    observacoes               JSONB NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_triage_item_job ON fiscal.triage_item (job_id);

-- RLS por tenant (mesmo padrão de ledger.entries / ledger.anchors).
ALTER TABLE fiscal.triage_job ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal.triage_job FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS triage_job_tenant_isolation ON fiscal.triage_job;
CREATE POLICY triage_job_tenant_isolation ON fiscal.triage_job
    USING (tenant_id = (current_setting('app.tenant_id'))::uuid);
DROP POLICY IF EXISTS triage_job_tenant_insert ON fiscal.triage_job;
CREATE POLICY triage_job_tenant_insert ON fiscal.triage_job
    FOR INSERT WITH CHECK (tenant_id = (current_setting('app.tenant_id'))::uuid);

ALTER TABLE fiscal.triage_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal.triage_item FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS triage_item_tenant_isolation ON fiscal.triage_item;
CREATE POLICY triage_item_tenant_isolation ON fiscal.triage_item
    USING (tenant_id = (current_setting('app.tenant_id'))::uuid);
DROP POLICY IF EXISTS triage_item_tenant_insert ON fiscal.triage_item;
CREATE POLICY triage_item_tenant_insert ON fiscal.triage_item
    FOR INSERT WITH CHECK (tenant_id = (current_setting('app.tenant_id'))::uuid);

GRANT SELECT, INSERT, UPDATE ON fiscal.triage_job, fiscal.triage_item TO app_user;
