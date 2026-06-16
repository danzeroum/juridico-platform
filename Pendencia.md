# Pendências — Decisões e Bloqueios

> Documento de anotações para o dono (danzeroum) revisar quando voltar.
> Atualizado em: 2026-06-16

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

### Fase 3a 🔄 EM ANDAMENTO (ComplianceRadar — aguardando CI)
- data contracts SNIS (saneamento) e IBGE (indicadores municipais) ✅
- ComplianceRadar monitor: avalia regras arrecadacao_critica e saneamento_baixo ✅
- AlertEnvelopes gerados via SEAMS contracts/alerts.py ✅
- Compliance router: municipalities, municipality detail, alerts, evaluate ✅
- DATASUS EXCLUÍDO — aguarda PD-06 (parecer DPO) ✅
- Coverage: 91.9% (261 testes) ✅

### Fase 3b 🔜 PRÓXIMA (TaxPredict)
- Pré-requisito: PR #6 merged
- PyMC5 com set_data/MutableData (substituir PyMC3)
- MCMC apenas em treino/recalibração (Celery Beat), não no path da request
- predict() condiciona no caso com RAG (ChromaDB + BGE-M3)
- Validar com desfechos reais

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

### QT-06 — PyMC3 → PyMC5 para TaxPredict
**Status:** Pendente (Fase 3b)  
**Contexto:** `services/taxpredict/model/bayesian.py` usa API PyMC3 obsoleta; `predict()` ignora input; MCMC no path da request  
**Ação:** Migrar para PyMC5 com `pm.set_data`/`MutableData`; MCMC em Celery Beat
