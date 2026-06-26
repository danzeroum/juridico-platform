# Production Readiness — juridico-platform

**Status: 🔴 NO-GO para produção** (cliente final). O sistema é um **scaffold Fase 0.x
bem arquitetado**: fundação de segurança, observabilidade e contratos prontas, mas o
caminho de dados, autenticação real e pipeline de deploy ainda não existem.

Avaliação consolidada de 4 auditorias independentes (segurança, backend, frontend,
infra) em 2026-06-26. Itens marcados ✅ já foram corrigidos na branch
`claude/prod-hardening-quick-wins`.

---

## P0 — Bloqueadores (impedem qualquer deploy)

| # | Item | Camada | Status |
|---|------|--------|--------|
| P0-1 | **Build do frontend quebrado** — `next.config.ts` não suportado no Next 14; erros de tipo em `@juridico/tokens` e `ScoreGauge`. | Frontend | ✅ **Corrigido** — `next.config.mjs`, desambiguação de tipos, `tailwindcss` dep, `ScoreGauge` anotado. Build verde (23 rotas). |
| P0-2 | **Login não valida senha** — endpoint emitia JWT sem checar credenciais; lógica de `ENV` invertida (default `dev` = bypass). | Segurança | ✅ **Mitigado** — `auth.py` agora falha fechado: default `ENV=production`, emite token só em dev/test. ⏳ **Falta:** validação real contra `tenant.users` (hash argon2/bcrypt) + lookup de tenant por slug. |
| P0-3 | **Rotas do frontend sem proteção** — não havia `middleware.ts`; acesso direto por URL. | Segurança | ✅ **Mecanismo adicionado** — `middleware.ts` exige cookie `jwt` quando `REQUIRE_AUTH=true`. ⏳ **Falta:** verificar assinatura RS256 via JWKS (hoje só checa presença). |
| P0-4 | **`demoMode=true` + `role=admin` por padrão**; shell nunca hidrata do JWT. | Frontend | ✅ **Parcial** — `demoMode` agora respeita `NEXT_PUBLIC_DEMO_MODE=false`. ⏳ **Falta:** derivar `tenant`/`role` do JWT em vez de defaults fixos. |
| P0-5 | **Celery conecta como superuser → bypassa RLS** na ingestão. | Infra | ✅ **Corrigido** — `ingest.yml` usa `app_user`/`APP_USER_PASSWORD`. |
| P0-6 | **CI não buildava o app** — regressões de build passavam despercebidas. | CI | ✅ **Corrigido** — job `frontend-build` (type-check + `next build`). |
| P0-7 | **Rate limiting em memória** (dict por processo) — não funciona com réplicas, reinicia zerado. | Backend | ⏳ Migrar para Redis `INCR` com TTL; **falhar fechado** (503) se Redis indisponível. |
| P0-8 | **Chaves JWT efêmeras** se os secrets não forem setados — tokens invalidados a cada restart / divergem entre réplicas. | Segurança | ⏳ Exigir `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` (Docker Secret/Vault); **falhar no boot** se ausentes, sem fallback silencioso. |
| P0-9 | **`alembic` não instalado** — `make migrate` falha; sem caminho de migração de schema. | Infra | ⏳ Adicionar `alembic` aos requirements + runner de migração no startup do container. |
| P0-10 | **Sem pipeline de deploy** — nenhum build/push/scan de imagem; sem manifests K8s/Helm. | Infra/CI | ⏳ Build+push de imagem, scan (Trivy/Grype), secret scanning, deploy para staging. |

## P1 — Antes do lançamento (Fase 1)

| # | Item | Camada |
|---|------|--------|
| P1-1 | **Núcleo do produto é stub** — LegalScore `/score` heurístico, `/processes` e `/risk-breakdown` 501. | Backend |
| P1-2 | **Dados ingeridos não persistem** — Receita/DATAJUD/PGFN só vão para cache Redis (TTL); sem Silver (OpenSearch/Neo4j/MinIO). | Backend |
| P1-3 | **Sem scheduler** — tasks Celery definidas mas nunca executam (sem Beat/cron). | Infra |
| P1-4 | **Decision Ledger em memória se `DATABASE_URL` ausente** — trilha some no restart, sem aviso. | Backend |
| P1-5 | **Healthcheck é stub** — `/health` sempre 200, não checa DB/Redis/Neo4j. | Infra |
| P1-6 | **Sem CORS explícito** no gateway — adicionar allowlist de origens. | Segurança |
| P1-7 | **Idempotência silenciosamente ignorada** se Redis cair (legalscore). | Backend |
| P1-8 | **Backup/restore nunca testado** — validar restauração em VM limpa. | Infra |
| P1-9 | **Sem refresh token** — access token de 1h; sem rotação. | Segurança |
| P1-10 | **Egress allowlist** — só `servicodados.ibge.gov.br` liberado; 6 de 8 produtos dependem de hosts bloqueados (DATAJUD, Receita, PGFN, BCB, Consumidor.gov, PNCP). | Infra |

## P2 — Hardening / escala (pós-lançamento)

| # | Item |
|---|------|
| P2-1 | Merkle root O(N) por insert (mitigar com MMR acima de ~5k entries/tenant). |
| P2-2 | Circuit breaker e rate limit por processo → estado compartilhado (Redis). |
| P2-3 | Neo4j Community (sem clustering) → decidir Enterprise para HA. |
| P2-4 | Single-node assumido ("~99% · nó único") → estratégia de HA/failover. |
| P2-5 | JWKS recalculado por request → cache com ETag/Cache-Control. |
| P2-6 | Migrar emissão de JWT para IdP gerenciado (Keycloak/Auth0/Cognito). |
| P2-7 | Pool de conexões do DB (`pool_size=5`) → dimensionar por nº de réplicas. |
| P2-8 | `tenant.idempotency_keys` existe mas é código-morto (Redis usado no lugar). |

---

## O que JÁ está sólido (não regredir)

- **RLS arquiteturalmente correto** — `FORCE ROW LEVEL SECURITY`, `SET LOCAL` por
  transação, PgBouncer em `transaction` mode; testes de integração reais no CI.
- **Observabilidade completa** — Prometheus, Grafana, Loki/Promtail, OTel (com
  degradação graciosa), `/metrics`, AlertManager, Flower.
- **TLS via Traefik** (Let's Encrypt, sem `--api.insecure`), DB sem portas expostas.
- **Secrets por env/Docker Secret** — `.env.example` com placeholders, nada sensível
  commitado, PgBouncer gera `userlist.txt` em runtime.
- **Decision Ledger + Merkle**, erros `problem+json` (RFC 9457), design LGPD/DPO.
- **Degradação graciosa honesta** — LLM/RAG/Chroma caem para template e sinalizam
  proveniência; coletores retornam vazio quando o host está bloqueado.
- **Gate de cobertura 80%** + lint (ruff) + validação de schema + checagens de
  segurança Docker no CI.

---

## Receita mínima para um deploy de produção (após P0)

```bash
# Variáveis obrigatórias (exemplo)
ENV=production
REQUIRE_AUTH=true
NEXT_PUBLIC_DEMO_MODE=false
NEXT_PUBLIC_GATEWAY_URL=https://api.seu-dominio.com.br
NEXT_SERVER_ACTIONS_ALLOWED_ORIGINS=app.seu-dominio.com.br
# Secrets (Docker Secret / Vault — nunca em .env commitado)
JWT_PRIVATE_KEY / JWT_PUBLIC_KEY        # par RSA persistente
APP_USER_PASSWORD                       # app_user (NOSUPERUSER)
HMAC_KEY                                # ledger
```

**Estimativa para GA:** ~4–6 semanas de trabalho focado (P0 restantes + P1).
