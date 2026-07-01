-- =============================================================================
-- Migration 004: schema `jurimetria` — fundação de jurimetria (TPU + indicadores)
--
-- Todas as tabelas aqui são de REFERÊNCIA (dado público agregado, igual para todo
-- tenant) — portanto SEM RLS, apenas GRANT ao app_user (mesmo padrão das tabelas
-- fiscais de referência em 003). Escrita exclusiva da task de agregação
-- (services.ingest.tasks.jurimetria_aggregate), que roda sem contexto de tenant.
-- Nenhuma PII: DATAJUD já é pseudonimizado no ingest; aqui só há contagens/medianas.
--
-- Idempotente e seguro em banco existente. Executar como owner (POSTGRES_USER).
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS jurimetria;
GRANT USAGE ON SCHEMA jurimetria TO app_user;

-- -----------------------------------------------------------------------------
-- 1. Dicionários canônicos TPU (Resolução CNJ 46). Espelham services/shared/tpu.py;
--    a ingestão (task ABJ/CNJ) popula a tabela completa, o módulo é o fallback.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jurimetria.tpu_classe (
    codigo             VARCHAR(20) PRIMARY KEY,
    label              TEXT NOT NULL,
    parent_codigo      VARCHAR(20),
    hierarchy_path     TEXT,
    source             VARCHAR(50) NOT NULL DEFAULT 'CNJ',
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transform_version  VARCHAR(20) NOT NULL DEFAULT '1.0.0'
);

CREATE TABLE IF NOT EXISTS jurimetria.tpu_assunto (
    codigo             VARCHAR(20) PRIMARY KEY,
    label              TEXT NOT NULL,
    parent_codigo      VARCHAR(20),
    ramo               VARCHAR(30),  -- TRABALHISTA|TRIBUTARIO|CONSUMIDOR|CIVEL|EMPRESARIAL|OUTRO
    source             VARCHAR(50) NOT NULL DEFAULT 'CNJ',
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transform_version  VARCHAR(20) NOT NULL DEFAULT '1.0.0'
);

-- -----------------------------------------------------------------------------
-- 2. Fato de indicadores jurimétricos.
--    Grão: (tribunal, classe_tpu, assunto_tpu, periodo, fonte).
--    `taxa_congestionamento` = pendentes / (baixados + pendentes) — fórmula
--    "Justiça em Números" (CNJ). `fonte` distingue DATAJUD | ABJ | BLEND.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jurimetria.indicador (
    tribunal              VARCHAR(20)  NOT NULL,
    classe_tpu            VARCHAR(20)  NOT NULL DEFAULT '',
    assunto_tpu           VARCHAR(20)  NOT NULL DEFAULT '',
    periodo               VARCHAR(10)  NOT NULL,  -- 'YYYY' | 'YYYY-Qn' | 'YYYY-MM'
    fonte                 VARCHAR(20)  NOT NULL DEFAULT 'DATAJUD',
    n_processos           INTEGER      NOT NULL DEFAULT 0,
    duracao_mediana_dias  NUMERIC,
    duracao_p25_dias      NUMERIC,
    duracao_p75_dias      NUMERIC,
    taxa_congestionamento NUMERIC(6,4),
    taxa_litigiosidade    NUMERIC,
    pct_provimento        NUMERIC(6,4),
    source                VARCHAR(50)  NOT NULL DEFAULT 'DATAJUD',
    ingested_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    transform_version     VARCHAR(20)  NOT NULL DEFAULT '1.0.0',
    CONSTRAINT pk_jurimetria_indicador
        PRIMARY KEY (tribunal, classe_tpu, assunto_tpu, periodo, fonte)
);
CREATE INDEX IF NOT EXISTS idx_indicador_tribunal_classe_assunto
    ON jurimetria.indicador (tribunal, classe_tpu, assunto_tpu);
CREATE INDEX IF NOT EXISTS idx_indicador_classe
    ON jurimetria.indicador (classe_tpu);
CREATE INDEX IF NOT EXISTS idx_indicador_periodo
    ON jurimetria.indicador (periodo);

-- -----------------------------------------------------------------------------
-- 3. Landing dos indicadores brutos da ABJ (silver), consultável e blendável
--    com os números derivados do DATAJUD. Fonte de duração quando o DATAJUD não
--    tem data de ajuizamento.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jurimetria.abj_indicador_raw (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tribunal              VARCHAR(20)  NOT NULL,
    classe_cnj            VARCHAR(20),
    assunto_cnj           VARCHAR(20),
    periodo               VARCHAR(10)  NOT NULL,
    tempo_medio_dias      NUMERIC,
    taxa_congestionamento NUMERIC(6,4),
    casos_novos           INTEGER,
    casos_baixados        INTEGER,
    casos_pendentes       INTEGER,
    source                VARCHAR(50)  NOT NULL DEFAULT 'ABJ',
    ingested_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    transform_version     VARCHAR(20)  NOT NULL DEFAULT '1.0.0'
);
-- UNIQUE com expressões exige índice (constraint de tabela não aceita COALESCE).
CREATE UNIQUE INDEX IF NOT EXISTS uq_abj_indicador
    ON jurimetria.abj_indicador_raw
    (tribunal, COALESCE(classe_cnj, ''), COALESCE(assunto_cnj, ''), periodo);

-- Grants nas tabelas de referência (globais, sem RLS).
GRANT SELECT, INSERT, UPDATE, DELETE ON
    jurimetria.tpu_classe, jurimetria.tpu_assunto,
    jurimetria.indicador, jurimetria.abj_indicador_raw
    TO app_user;
