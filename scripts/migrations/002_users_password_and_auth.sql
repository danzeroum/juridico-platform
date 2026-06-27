-- =============================================================================
-- Migration 002 — autenticação real contra tenant.users
--
-- Adiciona as colunas necessárias para validar credenciais (P0-2):
--   - password_hash: hash PBKDF2-HMAC-SHA256 (formato pbkdf2_sha256$iter$salt$hash)
--   - name:          nome de exibição do usuário
--
-- Idempotente (IF NOT EXISTS / ON CONFLICT). Aplicar após bootstrap-db.sql.
-- =============================================================================

ALTER TABLE tenant.users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE tenant.users ADD COLUMN IF NOT EXISTS name VARCHAR(255);

-- -----------------------------------------------------------------------------
-- Seed de usuário de DESENVOLVIMENTO (somente para o tenant 'dev-tenant').
--
-- ⚠️  DEV ONLY — credencial conhecida, NÃO usar em produção:
--       email:  admin@dev.com
--       senha:  dev12345
--       papel:  admin
--
-- Em produção: criar usuários via fluxo de gestão (P1) e NUNCA aplicar este seed
-- (o tenant 'dev-tenant' não deve existir em produção).
-- -----------------------------------------------------------------------------
INSERT INTO tenant.users (tenant_id, email, name, role, password_hash, active)
SELECT
    t.id,
    'admin@dev.com',
    'Admin de Desenvolvimento',
    'admin',
    'pbkdf2_sha256$600000$g9gLadCiKMaLDkcSM5KIbg==$9d2VPknk/IesKc65jhIbV9KIvkm+9zyFd/YICkX9CXM=',
    TRUE
FROM tenant.tenants t
WHERE t.slug = 'dev-tenant'
ON CONFLICT (tenant_id, email) DO NOTHING;
