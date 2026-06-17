# Pendências — Decisões e Bloqueios

> Documento de anotações para o dono (danzeroum) revisar quando voltar.
> Atualizado em: 2026-06-17 (PR #22 merged — serialização por tenant + constraint única + anchors RLS + DATABASE_URL app_user)
>
> **Distinção importante:** "Código merged / CI verde" ≠ "DoD verde (pronto)".
> A tabela de fases abaixo usa duas colunas. Nenhuma fase está "pronta" enquanto
> os gates de P0 não fecharem.

---

## STATUS DAS FASES — DUAS COLUNAS

| Fase | Código merged / CI verde | DoD verde (pronto) |
|---|---|---|
| 0 — Segurança/Infra | ✅ PRs #3,#9–#15 | ⚠️ P0-2 (restore não testado em VM limpa), P0-4: E2E Docker pendente |
| 1 — LegalScore PJ | ✅ PR #4 | ⚠️ P0-1 (SLA não medido validamente), P0-4: E2E Docker |
| 2 — ContabilIA | ✅ PR #5 | ⚠️ P0-1, P0-4: E2E Docker |
| 3a — ComplianceRadar | ✅ PRs #6,#13 | ⚠️ P0-1, P0-4: E2E Docker |
| 3b — TaxPredict | ✅ PR #7 | ⚠️ P0-1, P0-4: E2E Docker, validação modelo com desfechos reais |
| 4 — LicitaWatch/PetiBot/ConciliaIA | ✅ PR #8 | ⚠️ P0-1, P0-4: E2E Docker |

---

## P0 — Bloqueadores de DoD (nenhum produto fica "pronto" sem estes)

### P0-1 — SLA não foi medido validamente
**Arquivo:** `tests/load/locustfile.py` (corrigido neste PR), `Makefile` (`load-test`)  
**Problema:** A versão anterior marcava 401/403 como sucesso e usava CNPJ sintético sem token — media o caminho de rejeição de auth, não o cálculo. Corrigido: agora autentica, usa JWT real, trata 401/403/5xx como falha.  
**Ação restante:** Semear dados de ingestão, rodar em ambiente representativo (não CI), commitar `tests/load/report.html` com p95 medido.  
**Aceite:** relatório commitado; LegalScore score p95 < 1,5s; batch 1k < 30s; erro < 0,1%.

### P0-2 — Backup com restore não testado
**Arquivo:** `infra/scripts/backup.sh`, `Makefile` (`backup`)  
**Problema:** Script existe, restore nunca executado. Gate da Fase 0 aberto.  
**Ação:** Executar backup (PG + Neo4j + MinIO), enviar offsite, restaurar em VM limpa, reexecutar `verify_integrity()` sobre entradas do ledger restaurado.  
**Aceite:** log do restore + raiz Merkle idêntica pós-restore commitados; procedimento no playbook.

### P0-3 — Crypto-shredding (right-to-erasure) ✅ IMPLEMENTADO (PR #11)
**Arquivo:** `services/shared/lgpd_crypto.py`  
**Implementado:** AES-256-GCM por titular; `erase_titular()` apaga a chave; `verify_integrity()` continua True após erasure.  
**Pendência de produção:** migrar `_KEY_STORE` em memória para KMS real (PD-05).  
**Aceite:** 15 testes em `test_lgpd_crypto.py` passando ✅

### P0-4 — DoD por produto: itens presentes mas sem teste que comprove
**Arquivo:** suites em `tests/` por serviço  
**Ação — confirmar (ou criar) teste para cada item, por produto:**
- [x] Rate limit por tenant: 101ª req → `429` com `Retry-After` — ✅ PR #12 (`test_middleware_ratelimit.py`)
- [x] Idempotência: `Idempotency-Key` repetida em 24h → mesmo resultado sem recálculo e sem 2ª entrada no Ledger — ✅ PR #15 (`TestIdempotencyLedgerGate` via `asyncio.run` + patch mock Ledger)
- [x] `problem+json` em **todos** os endpoints de erro — ✅ PR #13 (`test_problem_json_handler.py`, `RequestValidationError` 422, `_status_title` 503)
- [x] OpenAPI 3.1 com exemplos de sucesso **e** erro por endpoint — ✅ PR #14 (taxpredict, petibot, concilia, compliance) + PR #4 (legalscore)
- [x] **Isolamento de tenant sob reuso de pool** → `tests/integration/test_tenant_isolation.py` — ✅ PR #10 (requer banco para rodar)
- [x] MinIO: acesso anônimo a qualquer bucket → `403` — ✅ PR #15 (`check_docker_security.py` verifica `mc anonymous set none` para bronze/silver/gold/documents/backups e proíbe `set download/public`; gate no CI sem infra necessária)
- [x] `source_date` + `lag_days` no payload de toda saída com lag — ✅ PR #13 (ComplianceRadar SNIS 548d)
- [x] Audit trail de acesso a dados pessoais — ✅ PR #14 (`audit_log.py`, `test_audit_log.py`, wired em decrypt/erase/ledger.write)
- [ ] E2E por produto com Docker real; contrato por fronteira SEAMS (requer infra)
- [x] OTel span em **todas** as fronteiras — ✅ PR #15 (legalscore, taxpredict, petibot, concilia, compliance, contabilia, licitawatch)
- [x] Métricas Prometheus em todas as fronteiras — ✅ `prometheus_fastapi_instrumentator` em `main.py` (PR #3), expõe `/metrics`; auto-instrumenta todos os routers (request count, duration, status codes por endpoint)
- [x] Playbook de incidentes por produto — ✅ PR #14 (`docs/INCIDENT-PLAYBOOK.md`)  
**Aceite:** cada checkbox com teste nomeado correspondente verde no CI.

---

## DECISÕES OBRIGATÓRIAS (Fase 0)

### PD-01 — Licença Neo4j
**Status:** Pendente de decisão do dono  
**Prazo:** Antes de finalizar a Fase 0 / início da Fase 1  
**Contexto:** O `docker/compose/base.yml` usa `neo4j:5-enterprise` com licença developer (limite de 1 GB de dados, proibida em produção). É preciso escolher:

| Opção | Custo | Limitações | Quando usar |
|---|---|---|---|
| **Community** | Gratuito | Sem clustering nativo, sem backup a quente, sem monitoramento enterprise | Fase 0–2 (nó único, sem HA) |
| **Enterprise** | Licença comercial (contato Neo4j Inc.) | Nenhuma técnica | Se HA na Fase 3 for crítico |

**Ação temporária adotada:** Substituído para `neo4j:5-community` no compose. Se a decisão for Enterprise, reverter e adicionar licença.

---

### PD-02 — Domínio / TLS para produção
**Status:** Pendente  
**Contexto:** O `traefik.yml` referencia variáveis `${DOMAIN}` e `${ACME_EMAIL}` para Let's Encrypt. O `.env.example` mostra `DOMAIN=app.juridico.io` (placeholder). Antes de ir a produção, preencher `.env` com o domínio real.  
**Ação necessária:** Registrar domínio real e configurar DNS apontando para o IP do servidor antes de `docker compose up` em produção.

---

### PD-03 — Servidor de identidade JWT
**Status:** Implementado um issuer simples interno (`services/gateway/auth/`). Em produção, avaliar substituição por Keycloak/Auth0/Cognito.  
**Contexto:** O roadmap exige JWT RS256 com `/.well-known/jwks.json`. A implementação atual gera o par de chaves RSA internamente (ok para dev/staging). Em produção com múltiplos tenants, um IdP dedicado oferece auditoria, MFA, federação, etc.  
**Ação:** Avaliar antes do go-live da Fase 1.

---

### PD-04 — Backup offsite + restore testado
**Status:** Script de backup criado em `infra/scripts/backup.sh`. Restore NÃO testado ainda.  
**Contexto:** O critério de aceite da Fase 0 exige restore testado em ambiente limpo.  
**Ação necessária:** Executar o script de backup, transferir para local offsite (S3, Backblaze, etc.), e fazer restore em VM limpa para confirmar integridade. Isso requer infraestrutura real (VM). Não é possível simular no ambiente de CI.  
**Desbloqueio:** Quando o servidor de produção estiver provisionado.

---

### PD-05 — Configuração de KMS para chave HMAC
**Status:** Implementado com Docker Secret como fallback.  
**Contexto:** Em produção, a chave HMAC deve estar em KMS (AWS KMS, GCP KMS, HashiCorp Vault). A implementação atual usa `load_secret("HMAC_KEY")` que lê de `/run/secrets/HMAC_KEY` (Docker Secret) ou variável de ambiente. Docker Secrets é adequado para Docker Compose; em K8s (Fase 4), migrar para External Secrets Operator + Vault.  
**Ação:** Provisionar o secret antes do go-live: `docker secret create HMAC_KEY <(openssl rand -hex 32)`

---

### PD-07 — DATABASE_URL deve usar credenciais de app_user (não postgres) ✅ IMPLEMENTADO (PR #22)
**Status:** Implementado para o gateway (serviço de aplicação principal).  
**O que foi feito:**
- `docker/products/legalscore/compose.override.yml`: `DATABASE_URL=postgresql://app_user:${APP_USER_PASSWORD}@postgres:5432/${POSTGRES_DB}` (direto no Postgres, não via PgBouncer — ver QT-09)
- `.env.example`: adicionado `APP_USER_PASSWORD=TROQUE_SENHA_FORTE`
- `scripts/migrations/001_...sql`: migration idempotente para bancos existentes
**Pendência de produção:** Substituir `APP_USER_PASSWORD` por Docker Secret: `docker secret create APP_USER_PASSWORD <(openssl rand -hex 32)`  
**Aceite:** `SHOW CURRENT_USER` retorna `app_user`; não retorna `postgres` ou `superuser`.

---

### PD-06 — Validação ROPA com DPO/advogado
**Status:** `docs/ROPA.md` criado com classificação das 14 fontes.  
**Bloqueio crítico (LGPD):** O uso de DATASUS/SIH (dado de saúde = sensível, art. 11) na ComplianceRadar e DanoBot precisa de parecer jurídico. A base legal defensável é uso agregado/anonimizado (art. 12), mas requer:
- Opinião formal do DPO
- Análise de risco de re-identificação
- Possível RIPD (Relatório de Impacto à Proteção de Dados)
**Ação:** Contratar/consultar DPO antes da Fase 3 (ComplianceRadar). Não bloqueia Fases 0–2.

---

## QUESTÕES TÉCNICAS MENORES

### QT-01 — `services/scoring/requirements.txt` corrompido
**Status:** Encontrado com conteúdo inválido (`from sklearn...`). Substituído por requirements.txt válido.

### QT-02 — Neo4j Community sem backup a quente
**Status:** Anotado. Backup manual via `neo4j-admin dump` funciona, mas exige parar o serviço (ou usar snapshot de volume). Impacto: janela de manutenção para backup até decisão PD-01.

### QT-08 — Ledger O(N) por operação — requer migração para MMR
**Status:** Documentado; mitigado mas não resolvido  
**Contexto:** `add_entry` e `get_proof` leem **todas** as folhas do tenant (`SELECT leaf_hash ... ORDER BY entry_index`) para recalcular a raiz Merkle. Custo: O(N) queries + O(N) CPU por inserção. Em 7 anos de uso, N cresce sem limite e o p95 do `/score` irá estourar o SLA de 1,5s.  
**Mitigações implementadas (PR #22):**
- `pg_advisory_xact_lock` serializa escritas por tenant (previne bifurcação da cadeia)
- `UNIQUE (tenant_id, entry_index)` torna corrida detectável (erro em vez de corrupção silenciosa)
- Checkpoint em `ledger.anchors` a cada 1024 entradas (auditoria histórica)
**O que NÃO foi resolvido:** O SELECT O(N) em si. Checkpoints não reduzem o custo porque o algoritmo `_compute_merkle_root` requer ALL leaf hashes para o balanced binary tree.  
**Solução real:** Migrar para **Merkle Mountain Range (MMR)** — O(log N) por inserção e prova, com peaks armazenados em `ledger.anchors`. Requer mudança no formato de prova (compatibilidade quebrada). Fazer ANTES de N > 10k entries por tenant.  
**Gatilho:** p95 de `/score` > 1,0s em load test, ou N > 5000 entries por tenant.

### QT-09 — PgBouncer não conhece app_user (multi-user auth pendente)
**Status:** Gateway conecta direto ao Postgres (não via PgBouncer) como workaround  
**Contexto:** PgBouncer está configurado com apenas um usuário (`POSTGRES_USER`). Para aceitar `app_user`, é necessário montar um `userlist.txt` com ambos os usuários (ou usar `auth_query`). O gateway atualmente bypassa o PgBouncer, perdendo o pooling de transações.  
**Impacto:** Em alta concorrência, o gateway abre conexões diretas ao Postgres. O SQLAlchemy QueuePool (padrão: 5 conexões) mitiga isso, mas sob carga real pode saturar o limite de conexões do PG.  
**Ação sugerida:** Configurar PgBouncer com `auth_query` ou `userlist.txt` incluindo `app_user`, e atualizar `DATABASE_URL` do gateway para apontar para `pgbouncer:6432`.

### QT-07 — tenant.idempotency_keys é código morto
**Status:** Identificado no review (PR #21)  
**Contexto:** A tabela `tenant.idempotency_keys` existe em `bootstrap-db.sql`, mas o caminho real de idempotência usa Redis (`services/shared/idempotency.py`) — não o Postgres. A tabela nunca é lida nem escrita em produção. Políticas RLS criadas para ela em `bootstrap-db.sql` também são mortas.  
**Ação sugerida (não bloqueante):** Remover a tabela e suas políticas do `bootstrap-db.sql` numa limpeza futura. Ou manter como fallback explicitamente documentado. Decisão a critério do dono.

---

### QT-03 — OpenSearch vs Elasticsearch
**Status:** O compose inclui OpenSearch 2.12. O código do produto ainda não o usa diretamente (será usado por PetiBot e DanoBot na Fase 4). Sem bloqueio atual.

---

## HISTÓRICO DE DECISÕES TÉCNICAS

| Data | Decisão | Justificativa |
|---|---|---|
| 2026-06-16 | `neo4j:5-enterprise` → `neo4j:5-community` no compose de dev | Licença developer proibida em produção; Community adequado para Fases 0–2 |
| 2026-06-16 | Chave HMAC via Docker Secret (não KMS real) em dev | KMS requer infraestrutura de nuvem; Docker Secret é a camada de abstração correta via `load_secret()` |
| 2026-06-16 | JWT RS256 com par de chaves gerado internamente | Adequado para dev/staging; migrar para IdP dedicado antes do go-live |
| 2026-06-16 | Fase 0 merged to main (PR #3) | CI green (5 jobs) — segurança, SEAMS, CI, LGPD fundações |
| 2026-06-16 | Fase 1 (PR #4) aberta — aguardando CI | 1a: ingest pipeline, 1b: engine+ledger, 1c: batch+idemp, 1d: validação |

---

## PROGRESSO ATUAL (2026-06-16)

### Fase 0 ✅ CONCLUÍDA (merged PR #3)
- HMAC-SHA256 em lgpd.py ✅
- Merkle full-ledger com get_proof()/verify_integrity() ✅
- Contratos SEAMS canônicos ✅
- CI 5 jobs verdes ✅
- API-GUIDELINES.md + ROPA.md ✅

### Fase 1 ✅ CONCLUÍDA (merged PR #4)
- **1a**: data contracts DATAJUD/PGFN/Receita, pipeline bronze→silver, CircuitBreaker ✅
- **1b**: FeatureAssembler, PythonScoreEngine via SEAMS, Decision Ledger ✅
- **1c**: batch endpoint HTTP 202, Redis idempotency 24h, Celery run_batch_score ✅
- **1d**: validation.py (AUC/Brier), model-metrics endpoint, locust load test ✅
- Coverage: 85% (118 testes) ✅

### Fase 2 ✅ CONCLUÍDA (merged PR #5)
- AnomalyDetector corrigido (fit/detect separados, fallback com threshold correto) ✅
- data contracts CAGED e SICONFI (Bronze/Silver + transform) ✅
- Ingest tasks CAGED e SICONFI com CircuitBreaker + cache Redis ✅
- Benford analysis module (MAD, status CONFORME/MARGINAL/SUSPEITO) ✅
- Z-score outlier detection (threshold 3σ) ✅
- CrossCheckEngine CC01–CC08 (headcount, receita, contratos, estoque, Benford, Z-score, liquidez, EBITDA) ✅
- ContabilIA router: POST /audit/upload (CSV→relatório JSON síncrono), GET /audit/{id} ✅
- Coverage: 91.5% (221 testes) ✅

### Fase 3a ✅ CONCLUÍDA (merged PR #6)
- data contracts SNIS (saneamento) e IBGE (indicadores municipais) ✅
- ComplianceRadar monitor: avalia regras arrecadacao_critica e saneamento_baixo ✅
- AlertEnvelopes gerados via SEAMS contracts/alerts.py ✅
- Compliance router: municipalities, municipality detail, alerts, evaluate ✅
- DATASUS EXCLUÍDO — aguarda PD-06 (parecer DPO) ✅
- Coverage: 91.9% (261 testes) ✅

### Fase 3b ✅ CONCLUÍDA (merged PR #7)
- `services/shared/contracts/taxpredict.py`: Materia/Decisao enums, TaxPredictRequest, JurisprudenciaHit, TaxPredictResponse, extract_features() ✅
- `services/taxpredict/model/bayesian.py`: PyMC5 com MutableData, fit() só em Celery, predict() condiciona no caso ✅
- `services/taxpredict/tasks.py`: recalibrate_model Celery Beat (MCMC off-path) ✅
- `services/shared/ai/rag.py`: Ollama BGE-M3 implementado (fallback para embedder padrão ChromaDB) ✅
- `services/gateway/routers/taxpredict.py`: POST /api/v1/taxpredict/predict com fallback prior nacional ✅
- `services/shared/config.py`: MINIO_URL, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, OLLAMA_URL ✅
- Coverage: 91.98% (271 testes) ✅

### Fase 4 ✅ CONCLUÍDA (merged PR #8)
- `services/ingest/contracts/pncp.py`: Modalidade enum, PncpContratoBronze, PncpContratoSilver, pncp_bronze_to_silver() ✅
- `services/shared/contracts/petibot.py`: TipoAcao, PetiRequest, PetiSection, PetiResponse, SECOES_MINIMAS_POR_TIPO ✅
- `services/shared/contracts/concilia.py`: ConciliaRequest, ConciliaFator, ConciliaResponse ✅
- `services/licitawatch/monitor.py`: LicitacaoIndicadores, build_indicadores_from_silver, evaluate_licitacoes (LL01–LL04) ✅
- `services/petibot/assembler.py`: assemble_petition com RAG graceful degradation ✅
- `services/concilia/recommender.py`: recommend_settlement com prior por tipo + ajuste probability/risk ✅
- `services/gateway/routers/licitawatch.py`: GET /contratos/{cnpj} + POST /orgao/{cnpj}/evaluate ✅
- `services/gateway/routers/petibot.py`: POST /petibot/assemble ✅
- `services/gateway/routers/danobot.py`: POST /danobot/predict → 501 (PD-06 bloqueado) ✅
- `services/gateway/routers/concilia.py`: POST /concilia/recommend ✅
- `services/gateway/main.py`: todos os 7 routers registrados ✅
- 80 novos testes; coverage total: 93.16% (351 testes) ✅

---

## ROADMAP — CÓDIGO COMPLETO; DoD PENDENTE

Todas as 6 fases têm código merged e CI verde. **Nenhum produto está "pronto"
pela DoD** até os gates P0 fecharem (ver tabela acima e seção P0).

| Fase | PR | Coverage | Código/CI | DoD |
|---|---|---|---|---|
| 0 — Segurança/Infra | #3 | — | ✅ | ⚠️ P0-2, P0-3 |
| 1 — LegalScore PJ | #4 | 85% / 118 testes | ✅ | ⚠️ P0-1, P0-4 |
| 2 — ContabilIA | #5 | 91.5% / 221 testes | ✅ | ⚠️ P0-1, P0-4 |
| 3a — ComplianceRadar | #6 | 91.9% / 261 testes | ✅ | ⚠️ P0-1, P0-4 |
| 3b — TaxPredict | #7 | 91.98% / 271 testes | ✅ | ⚠️ P0-1, P0-4, P2-3 |
| 4 — LicitaWatch/PetiBot/ConciliaIA | #8 | 93.16% / 351 testes | ✅ | ⚠️ P0-1, P0-4 |
| E2E HTTP + PNCP task | #16 | 467 testes | ✅ | E2E Docker pendente (infra) |
| Cobertura 95%+ (kmeans/RAG/factory/ratelimit/quality) | #17–#19 | 502 testes | ✅ | — |
| Cobertura ~99% (todos os gaps cobríveis eliminados) | #20 | 528 testes | ✅ merged (ecea0b4) | — |
| Fase 1c: PostgresDecisionLedger + RLS wired no router | #21 | 540+ testes | ✅ merged | ⚠️ PD-07 |
| Serialização + constraint + anchors + DATABASE_URL app_user | #22 | 14 testes ledger | ✅ merged | ⚠️ QT-08, QT-09 |

**Caminho mínimo para o LegalScore ir a produção:** P0-1 (SLA medido) + P0-2 (restore testado) + P0-3 (crypto-shredding ✅) + fatia P0-4 do LegalScore + PD-01/02/03/05 decididos.

### Cobertura de testes — estado final (pós PR #20 + commits extras)

| Módulo | Cobertura | Linhas descobertas | Razão |
|---|---|---|---|
| `engines.py` | 76% | 106, 113-117, 120-129 | Crate Rust não compilado em CI |
| `factory.py` | 93% | 59, 63 | Requer `rust.healthy()` = True |
| `config.py` | 98% | 8 | `path.read_text()` requer Docker Secret em `/run/secrets/` |
| **Todos os outros** | **100%** | — | — |
| **TOTAL (suite completa)** | **~99%** | 18 linhas impossíveis | Rust + Docker Secret |

Módulos que atingiram 100% após PR #20 (antes estavam abaixo):
`lgpd.py`, `merkle.py`, `idempotency.py`, `contracts/scoring.py`,
`benford.py`, `compliance/monitor.py`, `crosscheck/engine.py`,
`ingest/contracts/datajud.py`, `ingest/contracts/receita.py`,
`ingest/contracts/pgfn.py`, `ingest/contracts/ibge.py`,
`ingest/contracts/snis.py`, `ingest/contracts/pncp.py`,
`ingest/pipeline/base.py`, `shared/config.py`.

### Pendências bloqueadas por decisões externas

1. **DanoBot** — 501 placeholder. Desbloqueia com parecer DPO (PD-06).
2. **K8s migration** — condicional: p95 > 2s → Rust; >70% CPU sustentado → K8s. Nenhum gatilho atingido.
3. **PNCP ingest task** (Celery) — ✅ implementado e merged (PR #16): `run_daily_ingest(cnpj_orgao, ano)` com paginação, circuit breaker, reconciliação e cache Redis `pncp:{cnpj_orgao}:{ano}:{numero_controle}` TTL 24h. 23 testes unitários passando. `requests` adicionado ao ambiente CI. Total geral: 467 testes (437 unit + 30 E2E), cobertura 93.45%.

---

## QUESTÕES TÉCNICAS PARA FASE 2

### QT-04 — AnomalyDetector ✅ CORRIGIDO (Fase 2)
**Status:** Corrigido em `services/audit/anomaly/detector.py`  
- `fit()` e `detect()` separados; `RuntimeError` se `detect()` chamado sem `fit()` prévio  
- Fallback MiniBatchKMeans: threshold calculado na distribuição de treino em `fit()`, não em cada `detect()`  
- 7 testes passando, cobertura 85%

---

## QUESTÕES TÉCNICAS PARA FASE 3

### QT-05 — DATASUS bloqueado (PD-06) nas Fases 3a e 4
**Status:** Bloqueado aguardando parecer DPO  
**Impacto:** ComplianceRadar (CC03-SNIS ok; DATASUS excluído) e DanoBot (Fase 4) não podem usar dados de saúde  
**Ação:** Contratar DPO antes da Fase 3b (ou 4 se DanoBot for prioritário)

### QT-06 — PyMC3 → PyMC5 para TaxPredict ✅ CONCLUÍDO (Fase 3b)
**Status:** Migrado para PyMC5 com `pm.MutableData`, `pm.set_data()`, MCMC apenas em Celery Beat  
**Contexto:** `services/taxpredict/model/bayesian.py` migrado; `predict()` condiciona no input via `set_data`; `recalibrate_model` Celery task
