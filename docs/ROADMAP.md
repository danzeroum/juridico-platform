# ROADMAP — Plataforma Jurídico-Contábil

> **Contrato de execução.** Este documento é o único ponto de verdade sobre o que
> construir, em que ordem e com quais critérios. Nenhum código de produto começa
> antes de este roadmap ser aprovado. Nenhum produto é considerado "pronto" enquanto
> os critérios da Seção de Definition of Done não estiverem todos verdes.
>
> **Precedência de documentos:**
> (1) Este roadmap → (2) `SEAMS_README.md` → (3) `plano-handoff-tecnico-v1_0.pdf`
> → (4) `Plano-Integracao-Trilingue-Python-Elixir-Rust.docx`

---

## Princípios transversais

Antes da sequência de fases: cinco eixos que todo produto deve satisfazer. Eles
são **requisitos**, não sugestões, e aparecem no checklist e na DoD de cada produto.

### P1 — Atributos de qualidade e custo cumulativo

| Atributo | Tática concreta |
|---|---|
| Escalabilidade | Réplicas horizontais FastAPI/Celery. Fronteiras SEAMS para Rust/Elixir só quando gatilho medido disparar — nunca antecipado. |
| Performance | SLA por endpoint medido em load test real; cache de LLM/embeddings; engines puros (sem I/O no caminho do cálculo). |
| Segurança | Security by Design: sem portas de banco expostas; segredos em KMS/Docker Secrets; TLS 1.3; privilégio mínimo. |
| Manutenibilidade | Contract-first; baixo acoplamento; cobertura ≥ 80%; observabilidade nas fronteiras. |
| Resiliência | Timeout + retry/backoff/jitter + circuit breaker em toda chamada a fonte governamental. |

Cada decisão arquitetural registrada no roadmap deve ser justificada pelo **custo
cumulativo ao longo da vida do sistema** — não só pelo custo imediato. A estratégia
SEAMS ("pagar a migração depois, não antes") é o exemplo-guia.

### P2 — Governança de API

Toda API dos 8 produtos segue uma convenção única, verificável como gate no CI:

- **Versionamento:** `/api/v1/{produto}/{recurso}` em toda a plataforma. Os endpoints
  existentes divergem (`/v1/score/company` no PDF vs `/legalscore/score/company`) —
  padronizar na Fase 0. Mudança incompatível → `v2`.
- **Substantivos autoexplicativos,** métodos HTTP com semântica correta (score é
  `POST` porque gera registro auditável no Ledger; perfis são `GET`).
- **Contrato de erro** `application/problem+json` (RFC 9457): campos `type`, `title`,
  `status`, `detail`, `instance`, `contract_version`. Nunca stack trace cru.
- **Exemplos de resposta reais** (sucesso + erros principais) em cada endpoint da
  OpenAPI 3.1.
- **Rate limiting por tenant** verificado por teste de carga.
- **Idempotência** em POSTs que criam estado: header `Idempotency-Key` nos endpoints
  de score (entrada no Ledger) e de publicação de alerta (reflete o `alert_id` já
  existente no outbox).
- **Anti-patterns proibidos** (gate no CI): ausência de versionamento, endpoints não
  documentados, sem rate limiting, sem logs estruturados, coleções sem paginação/filtro,
  erro sem contrato `problem+json`.

Documentação de referência: `docs/API-GUIDELINES.md` (criado na Fase 0).

### P3 — Microsserviços e resiliência

- Cada serviço é dono dos seus dados. Sem tabela mutável compartilhada entre
  domínios — exceto os contratos explícitos: `alerts_outbox` (Seção 5) e
  Decision Ledger (read-only para outros serviços).
- Dockerfile + compose override por serviço; deploy independente.
- Toda chamada a fonte governamental (DATAJUD, PGFN, PNCP etc.) tem: **timeout**
  configurado, **retry com backoff exponencial + jitter** (tenacity), **circuit
  breaker por fonte** (estado aberto impede chamadas em cascata), **bulkhead** via
  filas Celery separadas por cadência (já estruturadas: daily/weekly/monthly/hourly).
- **Degradação graciosa:** score parcial com campo `data_freshness: "stale"` quando
  alguma fonte está indisponível. Nunca retornar 500 quando é possível retornar
  dados parciais com aviso.

### P4 — Sistemas de uso intensivo de dados

- **5 Vs por domínio:** Volume (DATAJUD ~2 GB/dia), Velocidade (horária a anual),
  Variedade (JSON/PDF/XBRL/grafo), Veracidade (lag e qualidade por fonte) e **Valor**
  (justificar cada fonte pelo produto que ela habilita — sem ingestão gratuita).
- **ETL completo com gates:** validação de schema na ingestão (data contract por
  fonte), tratamento de faltantes, detecção/remoção de outliers de *higiene de dado*
  (distinto da detecção de anomalia, que é feature de produto), normalização,
  deduplicação.
- **Linhagem:** toda linha carrega `source`, `ingested_at`, `transform_version` ao
  longo de bronze → silver → gold. Contagem de reconciliação (registros in vs out)
  por execução.
- **Ciclo analítico completo:** problema → coleta → preparação → modelagem →
  comunicação → **feedback**. Métricas SMART definidas antes de codar; loop de
  feedback ligando predições a desfechos reais (ver LegalScore e TaxPredict).

### P5 — Privacy by Design / LGPD

Sete princípios PbD, todos verificáveis:

| Princípio | Como é atendido |
|---|---|
| 1. Proativo/preventivo | Pseudonimização HMAC-SHA256 no ingest, antes de qualquer persistência |
| 2. Privacy by default | Dados pessoais nunca em claro em nenhum banco; buckets privados por padrão |
| 3. Privacidade no design | ROPA com base legal por fonte; classificação pessoal × sensível |
| 4. Soma positiva | Explicabilidade (SHAP, breakdown do score); usuário não perde funcionalidade para ter privacidade |
| 5. Segurança ponta-a-ponta | TLS 1.3 em trânsito; nenhuma porta de banco exposta; privilégio mínimo |
| 6. Transparência | OpenAPI documentada; Decision Ledger auditável; fontes de dados declaradas no payload |
| 7. Centrado no usuário | Right-to-erasure implementado e testado; audit trail de acesso |

Requisitos adicionais:
- **ROPA** (`docs/ROPA.md`): base legal por fonte (obrigação legal / interesse
  legítimo / dado tornado público) e finalidade. Sem base legal documentada, a fonte
  não entra em produção.
- **Classificação pessoal × sensível:** CPF/nome = pessoal. **DATASUS/SIH (saúde) =
  sensível (LGPD art. 11)** — exige proteção adicional, k-anonymity reforçada
  (supressão de células < 5) e justificativa de processamento. Dados de processos
  judiciais podem conter categorias sensíveis — classificar e proteger.
- **Resposta a incidentes:** cenários mínimos documentados (vazamento de bucket,
  acesso indevido a banco, comprometimento da chave HMAC → rotação) com cadeia de
  evidências para auditoria (Decision Ledger + audit logs imutáveis) e prazo de
  comunicação à ANPD/titulares conforme LGPD art. 48.

---

## 1. Sequência global

### 1.1 Ordem de construção e justificativa

| Fase | Semanas | Foco | Justificativa da ordem |
|---|---|---|---|
| **0** | 1–3 | Segurança + Infra + Fundações transversais | Corrige todos os guardrails violados e estabelece padrões de API, dados e PbD antes de qualquer produto |
| **1** | 4–13 | LegalScore PJ | Primeiro produto a exercitar o stack completo: ingest, scoring+SEAMS, ledger, API |
| **2** | 14–23 | ContabilIA | Reusa ingest da Fase 1 (DATAJUD, PGFN); adiciona CAGED, SICONFI, PNCP; cross-check e anomalia |
| **3a** | 24–31 | ComplianceRadar | Alertas multicanal (fronteira Elixir via outbox); reusa ContabilIA e dado municipal |
| **3b** | 32–39 | TaxPredict | Modelo Bayesiano (PyMC5); reusa RAG e DATAJUD jurisprudência |
| **4** | 40–52 | LicitaWatch, DanoBot, PetiBot, ConciliaIA + K8s | Reuso puro dos engines de 1–4; migração K8s se gatilhos dispararem |

Produtos 5–8 são combinações dos engines dos produtos 1–4 (**reuso real**, sem
engines novas). Por isso entram só na Fase 4, depois que as bases estão estáveis.

### 1.2 SLA honesto por marco de infraestrutura

> O badge `SLA-99.5%` no `README.md` está incorreto para nó único e deve ser
> corrigido na Fase 0.

| Marco infra | Fase | SLA prometível | Condição |
|---|---|---|---|
| Nó único | 0–2 | ~99,0% | Janela de manutenção ≥ 1h/mês prevista contratualmente |
| PG primary + réplica síncrona | 3 | ~99,5% | Réplica PG + Redis Sentinel ativo |
| K8s / HA full | 4+ | ~99,9% | Cluster K8s com HPA, PG HA (Patroni), Redis HA |

### 1.3 Gatilhos de migração de ferramenta

| De | Para | Gatilho |
|---|---|---|
| Celery | Airflow | > 15 DAGs ativos **ou** > 5M registros/DAG |
| Docker Compose | Kubernetes | > 70% CPU sustentado **ou** > 50 containers |
| Python scorer | Rust (PyO3) | p95 > 2s para 1k CNPJs em load test |
| Celery delivery | Elixir/Oban | Cliente exige SLA 99% de entrega com confirmação |

---

## 2. Fase 0 — Segurança, Infra e Fundações Transversais (Semanas 1–3)

> **Pré-requisito absoluto.** Nenhum produto vai a produção enquanto os itens desta
> fase não estiverem no checklist da Seção 8.

### 2.1 Correções obrigatórias no código existente

Estas são defeitos identificados no repositório. Implementar a versão corrigida
desde o início; não reproduzir o que está no código atual.

| Arquivo | Defeito identificado | Correção |
|---|---|---|
| `docker/compose/base.yml` | Portas de todos os bancos expostas no host: Postgres :5432, PgBouncer :6432, Neo4j :7474/:7687, Redis :6379, MinIO :9000/:9001, ChromaDB :8001 | Remover **todos** os `ports:` das bases de dados. Apenas Traefik expõe 80/443. Acesso admin via rede interna/VPN/túnel SSH |
| `docker/compose/traefik.yml` | `--api.insecure=true` expõe dashboard sem autenticação | Dashboard acessível só via rede interna/VPN. Sem `--api.insecure` em produção |
| `services/shared/lgpd.py` | SHA-256 truncado (CPF em 12 chars, nome em 10): reversível por força bruta (~10¹¹ CPFs possíveis) e truncamento causa colisão de identidade | HMAC-SHA256 com chave gerenciada em KMS/Docker Secret. Sem truncamento. Hash determinístico por chave (mesmo CPF + mesma chave → mesmo hash; chave diferente → hash diferente; não derivável do SHA-256 do CPF sem a chave) |
| `services/shared/ledger/merkle.py` | `self.entries[-100:]` cobre só as últimas 100 entradas. `get_proof()` e `verify_integrity()` ausentes | Merkle sobre o ledger inteiro via tabela Postgres particionada + âncoras periódicas (raiz gravada a cada N entradas). Implementar `get_proof(entry_id)` e `verify_integrity(entry_id, proof)` com testes: integridade da entrada nº 1 deve ser verificável com ≥ 10k entradas |
| `docker/compose/base.yml` (minio-init) | Sem política explícita de acesso; risco de bucket público | Buckets privados por padrão. Sem `anonymous set download`. Dados bronze nunca acessíveis sem autenticação |
| `docker/compose/base.yml` (neo4j) | `neo4j:5-enterprise` com licença developer: limite de 1 GB, proibida em produção | **Decisão a registrar neste documento antes da Fase 1:** Community (sem clustering/backup a quente) × Enterprise (licença comercial paga). A decisão condiciona a estratégia de HA da Fase 3 |
| `services/shared/ai/rag.py` | Embedding retorna `None` (TODO) | Implementar geração de embedding via Ollama BGE-M3 na Fase 1 |
| `services/audit/anomaly/detector.py` | `decision_function()` chamado sem `fit()` prévio → falha em runtime. Fallback MiniBatchKMeans: `scores < np.percentile([scores], 5)` compara um escalar com o percentil de si mesmo → condição sempre True | Separar `fit(X_train)` de `detect(x)`. Fallback com lógica correta: comparar score do ponto com distribuição do conjunto de treino |
| `services/taxpredict/model/bayesian.py` | Usa API PyMC3. `predict()` ignora o input (retorna constante). MCMC no caminho da request — incompatível com p95 < 3s | PyMC5 com `pm.set_data`/`MutableData`. `predict(case)` condiciona no caso via `set_data`. MCMC só em treino/recalibração agendada (Celery Beat); request recebe preditiva posterior pré-calculada |
| `services/scoring/engine/model.py` | Não implementa o contrato SEAMS. IC via bootstrap sobre coeficientes fixos (mede ruído das features, não incerteza real do modelo) | Substituir por `PythonScoreEngine` de `services/scoring/engine/engines.py` (implementa `ScoreEngine` Protocol). IC derivado do sigma do modelo (covariância dos coeficientes) |
| `README.md` | Badge `SLA-99.5%` sem cluster | Atualizar para refletir SLA honesto por fase (Seção 1.2) |
| `README.md` | "Decision Ledger: Merkle tree + SHA-256" — ambíguo quanto ao uso de SHA-256 em PII | Esclarecer: Ledger hasheia inputs/outputs (não PII diretamente). PII é pseudonimizado via HMAC antes de entrar em qualquer campo |
| LegalScore (geral) | Score apresentado como "rating" calibrado | Rotular como **heurística** até validação contra desfechos reais com AUC, Brier e curva de calibração |

### 2.2 Fundações transversais a entregar na Fase 0

**Governança de API (P2):**
- `docs/API-GUIDELINES.md`: convenção `/api/v1/{produto}/{recurso}`, contrato de
  erro `problem+json`, paginação/filtros, idempotência, lista de anti-patterns
  proibidos e gate do CI que os verifica.
- Um endpoint de referência funcional (ex.: `GET /api/v1/health` + `POST /api/v1/legalscore/score` stub)
  implementando todo o padrão — serve como template para os demais.

**Qualidade de dados (P4):**
- Template de **data contract** por fonte: schema esperado, cadência, campos
  obrigatórios, tratamento de faltantes, SLA de frescor.
- Campos de linhagem padronizados em todos os registros bronze: `source` (string),
  `ingested_at` (timestamptz), `transform_version` (semver).

**Privacy by Design (P5):**
- `docs/ROPA.md`: tabela das 14 fontes com base legal e finalidade (ver Seção 6.1).
- Tabela de classificação pessoal × sensível das 14 fontes.
- `services/shared/lgpd.py` reescrito com HMAC-SHA256.
- Rotina de rotação de chave HMAC documentada (procedimento de re-pseudonimização).

**Observabilidade (P1):**
- Logging JSON estruturado com contexto `request_id`, `tenant`, `source` → Loki.
- Métricas Prometheus no gateway (latência, taxa de erro, saturation).
- OpenTelemetry span no endpoint de referência — padrão a ser replicado em todos
  os serviços e nas fronteiras SEAMS.

### 2.3 Migração dos contratos SEAMS para os caminhos canônicos

> **Na Fase 0**, não na implementação dos produtos. A Fase 1 importa dos canônicos.
> As cópias em `docs/` permanecem como referência histórica.

| Origem (`docs/`) | Destino canônico |
|---|---|
| `scoring.py` | `services/shared/contracts/scoring.py` |
| `engines.py` | `services/scoring/engine/engines.py` (substitui `model.py`) |
| `factory.py` | `services/scoring/engine/factory.py` |
| `alerts.py` | `services/shared/contracts/alerts.py` |
| `publishers.py` | `services/shared/alerts/publishers.py` |
| `alert.v1.json` | `schemas/alert.v1.json` |
| `test_score_engine_contract.py` | `services/scoring/tests/contract/test_score_engine_contract.py` |
| `test_alert_contract.py` | `services/shared/alerts/tests/test_alert_contract.py` |

### 2.4 Decisão de licença Neo4j (obrigatória antes da Fase 1)

| Opção | Prós | Contras | Gatilho para Enterprise |
|---|---|---|---|
| **Community** | Gratuita, open-source | Sem clustering, sem backup a quente, sem monitoramento corporativo | Necessidade de HA ou backup online |
| **Enterprise** | Clustering, backup a quente, suporte comercial | Licença paga (contrato com Neo4j Inc.) | Desde o início se HA for requisito |

**Decisão registrada aqui:** `[ ] Community` `[ ] Enterprise`
*(Preencher antes do fim da Fase 0. Condiciona a estratégia de HA da Fase 3.)*

### 2.5 Critérios de aceite da Fase 0

- [ ] Nenhuma porta de banco exposta no host (`docker ps` confirma: só Traefik em 80/443).
- [ ] Traefik dashboard inacessível externamente; sem `--api.insecure=true`.
- [ ] `lgpd.py`: HMAC-SHA256 com chave em Docker Secret. Teste: mesmo CPF + mesma chave → mesmo hash; mesma chave em chaves diferentes → hashes diferentes; hash não reproduzível sem a chave.
- [ ] `DecisionLedger.get_proof(entry_id)` e `verify_integrity(entry_id, proof)` implementados. Teste: integridade da entrada nº 1 verificável com ≥ 10k entradas.
- [ ] Todos os buckets MinIO privados por padrão; teste de acesso anônimo retorna 403.
- [ ] Contratos SEAMS nos caminhos canônicos; suítes de contrato passando no CI.
- [ ] `docs/API-GUIDELINES.md` e `docs/ROPA.md` (com esqueleto das 14 fontes) criados.
- [ ] Decisão de licença Neo4j registrada neste documento.
- [ ] CI configurado com jobs Python (unit + integração + contrato) e gate de cobertura ≥ 80%.
- [ ] Endpoint de referência implementando todo o padrão P2 (versionamento, error contract, rate limit, OTel span, OpenAPI com exemplo).

---

## 3. Produto 1 — LegalScore PJ (Fase 1, Semanas 4–13)

### 3.1 Objetivo e entrega principal

**Objetivo:** Score de risco jurídico-financeiro de pessoas jurídicas, calculado a
partir de dados públicos (processos judiciais, dívida ativa, emprego, cadastro).

**Entregas:**
- API `POST /api/v1/legalscore/score` (score unitário) e `POST /api/v1/legalscore/batch` (até 1k CNPJs).
- `GET /api/v1/legalscore/company/{cnpj}` (perfil + processos + breakdown).
- `GET /api/v1/legalscore/audit/{request_id}` (trilha do Decision Ledger).
- Dashboard Next.js `frontend/apps/legalscore`.
- Score rotulado como **heurística** até validação de Fase 1d.

**SLA:** p95 < 1,5s (score unitário); batch 1k CNPJs em < 30s; disponibilidade ~99,0% (nó único).

### 3.2 Fases do produto

**Fase 1a — Ingest e enriquecimento (Sem. 4–6)**

Entregas:
- Ingest DATAJUD diário funcional (já parcialmente implementado em `tasks/datajud.py`).
- Ingests PGFN semanal e Receita Federal diário implementados.
- Pipeline bronze → silver → gold com campos de linhagem e data contracts.
- Neo4j populado com grafo societário (empresa ↔ sócio ↔ processo).
- Feature store: derivação das 7 features do score a partir dos dados silver.

Dependências de stack: Postgres+PgBouncer, Redis, Neo4j, MinIO, Celery.

Gatilho de revisão: pipeline roda sem erros por 5 dias consecutivos; reconciliação in/out < 2% de divergência.

Critérios de aceite:
- [ ] Data contract validado na entrada de cada fonte; registros inválidos rejeitados e logados.
- [ ] Campos `source`, `ingested_at`, `transform_version` em todos os registros bronze.
- [ ] Feature store popula as 7 features para ≥ 95% dos CNPJs com dado disponível.
- [ ] Circuit breaker ativo por fonte (DATAJUD, PGFN, Receita); degradação graciosa testada.

**Fase 1b — Scoring engine + fronteira SEAMS (Sem. 7–9)**

Entregas:
- `services/shared/contracts/scoring.py` no caminho canônico.
- `services/scoring/engine/engines.py` com `PythonScoreEngine` (IC via sigma do modelo).
- `services/scoring/engine/factory.py` com `get_score_engine()`.
- Coeficientes MLR por CNAE de 2 dígitos carregados do PostgreSQL (não hardcoded).
- Suíte de contrato `test_score_engine_contract.py` passando no CI.
- Decision Ledger: `add_entry()` com `get_proof()` e `verify_integrity()` testados.

Critérios de aceite:
- [ ] Nenhum chamador importa `PythonScoreEngine` diretamente; todos passam por `get_score_engine()`.
- [ ] Features chegam ao engine como `dict[str, float]` já calculadas; engine não faz I/O.
- [ ] IC derivado do sigma do modelo (não bootstrap sobre coeficientes fixos).
- [ ] `test_deterministico`, `test_intervalo_de_confianca_coerente` e `test_versao_do_contrato` passando.
- [ ] Score rotulado explicitamente como heurística na OpenAPI e no payload de resposta.

**Fase 1c — API + Decision Ledger (Sem. 10–11)**

Entregas:
- Gateway wired: `POST /api/v1/legalscore/score` → feature store → `get_score_engine()` → Decision Ledger → resposta.
- Batch endpoint com fila Celery e streaming de resultado via webhook/polling.
- Contrato de erro `problem+json` em todos os endpoints.
- Rate limiting por tenant (100 req/min default).
- Idempotência em `POST /api/v1/legalscore/score` via `Idempotency-Key`.
- OpenAPI 3.1 com exemplos de resposta (score, breakdown, IC, disclaimer de heurística).

Critérios de aceite:
- [ ] Endpoint de score retorna `disclaimer: "heurística — não validado contra desfechos reais"`.
- [ ] Erro de validação retorna `problem+json` com `detail` informativo.
- [ ] `Idempotency-Key` duplicada retorna 200 com resultado cacheado (não recalcula).
- [ ] Rate limit testado: 101ª req retorna 429 com `Retry-After`.
- [ ] OTel span criado por request, visível no Jaeger/trace.

**Fase 1d — Dashboard + load test + validação (Sem. 12–13)**

Entregas:
- Dashboard Next.js: busca por CNPJ, score + breakdown + IC + histórico + trilha de auditoria.
- Load test Locust: 500 req/s por 5 min; p95, p99 e taxa de erro medidos.
- Início da coleta de dados para validação: vincular CNPJs com eventos de falência/recuperação judicial públicos (dataset de validação).

Critérios de aceite:
- [ ] Load test: p95 < 1,5s; taxa de erro < 0,1% em 500 req/s sustentados.
- [ ] Dashboard carrega em < 2s (LCP); sem erros no console.
- [ ] Dataset de validação definido com ≥ 500 CNPJs com desfecho conhecido.
- [ ] Cobertura de testes ≥ 80% no serviço de scoring.

### 3.3 Contratos e fronteiras SEAMS

| Interface | Arquivo | Chamador |
|---|---|---|
| `ScoreEngine` (Protocol) | `services/shared/contracts/scoring.py` | Gateway router, Celery batch task |
| `ScoreRequest` / `ScoreResult` | `services/shared/contracts/scoring.py` | Todos os callers do scoring |
| `get_score_engine(backend)` | `services/scoring/engine/factory.py` | **Único ponto de instanciação** |

### 3.4 Definition of Done (LegalScore PJ)

- [ ] Fases 1a–1d com todos os critérios de aceite verdes.
- [ ] Testes unit + integração + contrato + E2E passando no CI; cobertura ≥ 80%.
- [ ] SLA medido em load test (p95 < 1,5s; batch < 30s).
- [ ] Score rotulado como heurística com disclaimer na API e no dashboard.
- [ ] Fronteira `ScoreEngine` com contrato + suíte no lugar.
- [ ] Decision Ledger com `get_proof()` e `verify_integrity()` testados.
- [ ] API conforme P2: versionamento, `problem+json`, rate limit, idempotência, exemplos na OpenAPI.
- [ ] Dados: data contract por fonte, linhagem bronze→gold, data+lag da fonte no payload.
- [ ] PbD: CPF/nome pseudonimizados com HMAC antes de persistência; ROPA atualizado.
- [ ] Observabilidade: OTel tracing, métricas Prometheus por endpoint, logs JSON→Loki.
- [ ] Playbook de incidentes do produto (score errado, indisponibilidade de fonte, Ledger corrompido).

### 3.5 Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| DATAJUD indisponível (frequente) | Alta | Alto | Circuit breaker + cache Redis 48h + score parcial com flag |
| Score apresentado como rating calibrado | Alta | Alto | Disclaimer obrigatório no payload e dashboard; bloqueio no gate do CI |
| IC via bootstrap (implementação errada) | Média | Alto | Revisar antes de Fase 1b; teste automatizado verifica que IC vem de sigma |
| Coeficientes não calibrados por CNAE | Alta | Médio | Fase 1b carrega do PostgreSQL; validação contra dataset de desfechos na Fase 1d |
| Neo4j 1 GB limite (licença developer) | Alta | Alto | Resolver decisão de licença na Fase 0 |

---

## 4. Produto 2 — ContabilIA (Fase 2, Semanas 14–23)

### 4.1 Objetivo e entrega principal

**Objetivo:** Auditoria contábil automatizada cruzando demonstrações financeiras
(DRE, balanço) com 14 fontes de dados públicos, gerando relatório de achados.

**Entregas:**
- API `POST /api/v1/contabilia/audit/upload` (upload DRE + disparo de auditoria).
- `GET /api/v1/contabilia/audit/{report_id}` (resultado + PDF gerado).
- `GET /api/v1/contabilia/audit/{report_id}/findings` (achados com evidências).
- Dashboard Next.js `frontend/apps/contabilia`.

**SLA:** p95 < 60s por empresa; 8 cross-checks implementados (CC01–CC08).

### 4.2 Fases do produto

**Fase 2a — Ingest de fontes complementares (Sem. 14–16)**

Entregas: Ingests CAGED mensal, SICONFI mensal, PNCP diário e ComexStat mensal.
Data contracts e gates de qualidade para cada fonte. Enriquecimento do grafo Neo4j
com vínculos contratuais (empresa ↔ PNCP ↔ município).

Critérios de aceite:
- [ ] Data contract validado na entrada de cada fonte.
- [ ] Gate de qualidade antes do cross-check: faltantes e outliers de higiene tratados.
- [ ] Reconciliação in/out < 2% por execução.

**Fase 2b — OCR + parser de demonstrações (Sem. 17–18)**

Entregas: Pipeline de OCR (Tesseract via pytesseract) para PDFs de DRE/balanço.
Parser extrai contas e valores; validação de schema (resultado do parse).
Armazenamento do documento bruto em MinIO (bucket `documents`, privado).

Critérios de aceite:
- [ ] Upload de PDF retorna `report_id`; status consultável via `GET /api/v1/contabilia/audit/{report_id}`.
- [ ] Parser reconhece ≥ 90% das contas em um conjunto de teste de 20 DREs públicas.
- [ ] Documento bruto acessível só via signed URL com TTL de 15min.

**Fase 2c — CrossCheckEngine + AnomalyDetector (Sem. 19–21)**

Entregas: Implementação das 8 regras CC01–CC08 com thresholds calibrados.
`AnomalyDetector` corrigido: `fit(X_train)` separado de `detect(x)`; fallback
MiniBatchKMeans com lógica correta (comparar score do ponto com distribuição treino).

**As correções do AnomalyDetector são pré-requisito desta fase** — aplicar na Fase 0.

Regras mínimas a implementar:

| Código | Nome | Severidade | Threshold |
|---|---|---|---|
| CC01 | Empregados vs CAGED | ALTO | Delta > 20% entre folha declarada e vínculos CAGED |
| CC02 | Receita vs SICONFI | CRÍTICO | Delta > 30% (prefeituras) |
| CC03 | Contratos vs PNCP | MÉDIO | Receita sem contratos correspondentes no PNCP |
| CC04 | Importações vs Estoque | MÉDIO | Crescimento desproporcional (> 2σ) |
| CC05 | Capital social vs PGFN | ALTO | Dívida ativa > 50% do capital social |
| CC06 | Emprego vs CAGED yoy | MÉDIO | Variação > 30% sem evento societário justificador |
| CC07 | Benford (1ª digit) | ALTO | Divergência χ² > p = 0,05 |
| CC08 | Anomalia multivariada | MÉDIO | IsolationForest score > percentil 95 do treino |

Critérios de aceite:
- [ ] CC07 (Benford) e CC08 (IsolationForest) só rodam após higiene de dado (CC07 exige N ≥ 100 registros).
- [ ] Fallback AnomalyDetector testado: km score comparado com `np.percentile(train_scores, 95)`.
- [ ] Cada achado inclui: `rule_id`, `severity`, `evidence` (dados usados), `source` com data e lag.

**Fase 2d — Geração de relatório e load test (Sem. 22–23)**

Entregas: Relatório em PDF (WeasyPrint ou ReportLab) e JSON com achados, evidências
e metadados (fontes usadas, data/lag de cada fonte). Dashboard.

Critérios de aceite:
- [ ] Load test: p95 < 60s para empresa com 50 contas e 8 cross-checks.
- [ ] Cobertura ≥ 80%.

### 4.3 Conformidade transversal

**API (P2):** `/api/v1/contabilia/...`; upload retorna 202 Accepted + `Location` header; polling por status.
**Dados (P4):** Gates de higiene (faltantes/outliers) antes de qualquer cross-check. Benford e Z-score não rodam sem dado limpo. Toda fonte citada no relatório com data e lag.
**Resiliência (P3):** OCR é CPU-bound e vai para fila Celery dedicada (não bloqueia requests). Circuit breaker por fonte pública.
**PbD (P5):** DRE/balanço contêm dados empresariais, não pessoais; mas podem conter CPF de sócios → HMAC antes de persistência. Bucket `documents` privado; signed URL com TTL.

### 4.4 Definition of Done (ContabilIA)

- [ ] Fases 2a–2d com critérios verdes; cobertura ≥ 80%.
- [ ] 8 cross-checks implementados, com testes unitários por regra.
- [ ] `AnomalyDetector` com `fit()` separado e fallback correto.
- [ ] API conforme P2; relatório contém fontes com data+lag.
- [ ] SLA medido: p95 < 60s.

### 4.5 Riscos e mitigações

| Risco | Mitigação |
|---|---|
| OCR falha em PDFs escaneados de baixa qualidade | Pré-processamento de imagem (deskew, enhance) antes do OCR; flag `ocr_confidence` no payload |
| Thresholds CC01–CC08 gerando falsos positivos | Calibrar com amostra de DREs validadas antes de ir a produção |
| IsolationForest sem `fit()` (bug existente) | Pré-requisito: corrigir na Fase 0 |
| Dado SICONFI anual desatualizado (~365d lag) | Toda referência inclui `source_date` e `lag_days` no payload |

---

## 5. Produto 3 — ComplianceRadar (Fase 3a, Semanas 24–31)

### 5.1 Objetivo e entrega principal

**Objetivo:** Monitoramento contínuo de indicadores de saúde fiscal e social de
municípios brasileiros, com sistema de alertas multicanal.

**Entregas:**
- API `GET /api/v1/compliance/municipalities` (lista com indicadores) e `GET /api/v1/compliance/municipality/{ibge_code}` (perfil detalhado).
- `POST /api/v1/compliance/alerts/subscribe` (cadastro de assinatura por município/indicador).
- `GET /api/v1/compliance/alerts` (histórico de alertas com status de entrega).
- Dashboard Next.js `frontend/apps/compliance-radar` com mapa de calor.

**SLA:** 99% alertas entregues com confirmação de dedup; dashboard atualiza < 30s após detecção.

### 5.2 Fases do produto

**Fase 3a-i — Ingest municipal + detecção (Sem. 24–26)**

Entregas: Ingests SICONFI, SNIS, IBGE, INEP e DATASUS (dado sensível — ver P5).
Pipeline de detecção: rolling Z-score, change-point detection (Prophet), e
AnomalyDetector (reusa ContabilIA, já corrigido).

**Frescor de dados crítico:** SNIS ~548 dias de lag, INEP/SICONFI ~365 dias. Toda
saída que usa essas fontes carrega `source_date` e `lag_days` explicitamente.
**Nunca apresentar dado anual como "tempo real".**

Critérios de aceite:
- [ ] Payload de indicadores inclui `source_date` e `lag_days` por fonte.
- [ ] DATASUS tratado como dado sensível: k-anonymity reforçada (supressão de células < 5); base legal documentada no ROPA.
- [ ] Pipeline de detecção roda para todos os 5.570 municípios em < 2h (Celery batch).

**Fase 3a-ii — AlertPublisher + outbox (Sem. 27–28)**

Entregas: `services/shared/contracts/alerts.py` e `schemas/alert.v1.json` nos
caminhos canônicos (migrados na Fase 0). `OutboxAlertPublisher` funcional. DDL da
tabela `alerts_outbox` em migration Alembic.

Toda publicação de alerta passa por `get_alert_publisher("outbox", db_conn=conn)`.
**Nenhum chamador instancia `OutboxAlertPublisher` diretamente.**

Critérios de aceite:
- [ ] `alerts_outbox` criada com: `alert_id` (PK), `dedup_key` (unique index parcial 24h), `status`, `attempts`.
- [ ] Insert idempotente: segundo `publish()` com mesmo `alert_id` retorna `dedup_hit=True`.
- [ ] `test_alert_contract.py` passando: envelope Python valida contra `alert.v1.json`.
- [ ] Dado sensível (DATASUS) **nunca** entra no `payload` do `AlertEnvelope` em claro. Só `subject_ref` com referências não-pessoais (código IBGE, faixa, não CPF).

**Fase 3a-iii — Worker de entrega + canais (Sem. 29–30)**

Entregas: Worker Celery que faz polling de `alerts_outbox (status='pending')` e
entrega via webhook, e-mail e Slack. Retry com backoff; `status` atualizado de
`pending → claimed → done | failed`. Dedup key garante cooldown de 24h.

Critérios de aceite:
- [ ] Load test: 1k alertas enfileirados em < 5s; 99% entregues em < 60s.
- [ ] Retry automático até 3 tentativas; `status=failed` após esgotamento.
- [ ] Dashboard mostra status de entrega em tempo real.

**Fase 3a-iv — Dashboard + E2E + load test (Sem. 31)**

Critérios de aceite:
- [ ] E2E: anomalia artificial detectada → alerta em `alerts_outbox` → entregue via webhook em < 30s.
- [ ] Cobertura ≥ 80%.

### 5.3 Contratos e fronteiras SEAMS

| Interface | Arquivo | Padrão de uso |
|---|---|---|
| `AlertPublisher` (Protocol) | `services/shared/contracts/alerts.py` | Todos os callers via `get_alert_publisher()` |
| `AlertEnvelope` | `services/shared/contracts/alerts.py` | Único formato de mensagem (Python ↔ Elixir) |
| `alert.v1.json` | `schemas/alert.v1.json` | Schema neutro validado por Python e Elixir |
| `alerts_outbox` | Tabela Postgres (DDL em migration) | Costura Python (writer) ↔ Elixir/Oban (reader) |

### 5.4 Definition of Done (ComplianceRadar)

- [ ] Fases 3a-i–iv com critérios verdes; cobertura ≥ 80%.
- [ ] 99% alertas entregues (medido em load test).
- [ ] Fronteira `AlertPublisher` com contrato + suíte no lugar.
- [ ] DATASUS classificado como sensível; ROPA atualizado; k-anonymity reforçada.
- [ ] `source_date` e `lag_days` em toda saída que usa dado com lag.
- [ ] SLA medido: detecção → dashboard < 30s.

### 5.5 Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Dado sensível DATASUS vaza em alerta ou log | `AlertEnvelope.subject_ref` permite só strings não-pessoais (validado pelo schema); log scrubbing |
| SNIS 548d lag apresentado como atual | `lag_days: 548` obrigatório no payload; dashboard exibe aviso |
| Celery não garante 99% de entrega | Outbox pattern garante atomicidade (alerta só existe se transação commitou); retries cobrem falhas transientes |
| Elixir/Oban não disponível ainda | O outbox é compatível com ambos; migração é troca de consumer, não de producer |

---

## 6. Produto 4 — TaxPredict (Fase 3b, Semanas 32–39)

### 6.1 Objetivo e entrega principal

**Objetivo:** Previsão bayesiana de desfecho tributário em processos administrativos
e judiciais, com intervalo de confiança calibrado e explicação SHAP.

**Entregas:**
- API `POST /api/v1/taxpredict/predict` (caso como input; probabilidade + IC + SHAP como output).
- `POST /api/v1/taxpredict/model/recalibrate` (trigger de recalibração — admin only).
- Dashboard Next.js `frontend/apps/taxpredict`.

**SLA:** p95 < 3s (MCMC **nunca** no caminho da request).

### 6.2 Fases do produto

**Fase 3b-i — Ingest jurídico-tributário + RAG (Sem. 32–34)**

Entregas: Ingest DATAJUD com filtro por matéria tributária. Pipeline RAG (ChromaDB
+ Ollama BGE-M3) para acórdãos e súmulas. Embedding gerado na ingestão (não na
request). Cache de LLM habilitado (`LLMMemoizer`, já estruturado em `shared/ai/cache.py`).

Critérios de aceite:
- [ ] Embedding via Ollama BGE-M3 funcional (corrige o TODO em `rag.py`).
- [ ] Busca semântica retorna k = 10 acórdãos relevantes em < 500ms (P99).
- [ ] Cache de embedding com hit rate > 90% após warm-up de 7 dias.

**Fase 3b-ii — Modelo Bayesiano PyMC5 (Sem. 35–37)**

Entregas: `TaxPredictionModel` reescrito em PyMC5 com:
- `pm.MutableData` para features do caso (permite `pm.set_data(case)` no predict).
- Modelo hierárquico: prior nacional + nível tribunal + nível matéria.
- Treinamento/recalibração em Celery Beat (agendado; MCMC roda offline).
- Salvar trace serializado em MinIO; `predict(case)` carrega trace e amostra posterior predictive.
- IC derivado da covariância dos parâmetros (não bootstrap).
- SHAP values via `shap.KernelExplainer` sobre o modelo treinado.

Critérios de aceite:
- [ ] `predict(case)` condiciona no caso via `pm.set_data(case)` — não retorna constante.
- [ ] MCMC nunca roda no path da request; trace pré-computado carregado na inicialização.
- [ ] Load test: p95 < 3s; rate de cold-start (trace reload) documentado.
- [ ] API PyMC5 validada: nenhum import de `pymc3` ou `theano`.

**Fase 3b-iii — Validação e calibração (Sem. 38–39)**

Entregas: Dataset de validação com processos tributários de desfecho conhecido
(CARF, TJSP). Métricas AUC, Brier, curva de calibração. Dashboard de validação.

Critérios de aceite:
- [ ] AUC > 0,65 no conjunto de validação (mínimo para heurística útil).
- [ ] Curva de calibração plotada; se calibração ruim, modelo permanece rotulado como heurística.
- [ ] Apenas após AUC e calibração satisfatórios, score pode ser chamado de "modelo calibrado".

### 6.3 Conformidade transversal

**API (P2):** `/api/v1/taxpredict/...`; `POST /predict` recebe JSON do caso; resposta inclui `probability`, `ci_lower`, `ci_upper`, `shap_values`, `jurisprudencia_refs` (top-5 acórdãos), `model_version`, `model_status` ("heurística" | "calibrado").
**Dados (P4):** Dataset de validação com métricas SMART; loop de feedback: predição vs desfecho real logado e comparado trimestralmente.
**PbD (P5):** Casos tributários podem conter CPF de contribuintes → HMAC antes de persistência; nenhum dado pessoal em payload de resposta.

### 6.4 Definition of Done (TaxPredict)

- [ ] Fases 3b-i–iii com critérios verdes; cobertura ≥ 80%.
- [ ] MCMC nunca no path da request (testado com mock de trace ausente → carrega do MinIO).
- [ ] PyMC5 API exclusivamente; zero imports PyMC3/Theano.
- [ ] `predict(case)` condiciona no caso (teste: dois casos diferentes → probabilidades diferentes).
- [ ] SLA medido: p95 < 3s.
- [ ] Status "calibrado" só após AUC e calibração validados.

### 6.5 Riscos e mitigações

| Risco | Mitigação |
|---|---|
| PyMC5 API diferente do PyMC3 | Reescrever do zero usando `pm.MutableData`; não migrar código legado linha a linha |
| MCMC no path da request (bug existente) | Teste de integração que verifica: se MinIO está offline, predict retorna erro imediato (não bloqueia tentando MCMC) |
| Modelo não calibrado apresentado como preciso | `model_status` obrigatório no payload; gate no CI verifica campo presente |
| Dataset de validação pequeno | Partir de CARF público (decisões administrativas federais); expandir com dados reais após go-live |

---

## 7. Produtos Secundários (Fase 4, Semanas 40–52)

Os produtos 5–8 são **combinações dos engines dos produtos 1–4** (reuso real).
Não criam engines novas e não criam fronteiras SEAMS novas — herdam as dos engines
que reutilizam.

### 7.1 LicitaWatch (Semanas 40–43)

**Objetivo:** Monitoramento diário de licitações no PNCP com detecção de anomalias
(preços, critérios, prazos) e alertas para assinantes.

**Engines reutilizados:** ComplianceRadar (AlertPublisher + outbox), ContabilIA
(CrossCheckEngine para verificar contratos vs PNCP), ingest PNCP (já implementado).

**SLA:** Diário (ciclo de 24h); alerta publicado em < 1h após detecção.

**Riscos específicos:** PNCP API com taxa de disponibilidade variável → circuit
breaker + retry idêntico ao DATAJUD.

### 7.2 DanoBot (Semanas 44–46)

**Objetivo:** Laudo automatizado de danos socioeconômicos municipais a partir dos
28 indicadores das fontes disponíveis (inclui DATASUS).

**Engines reutilizados:** ComplianceRadar (indicadores municipais + alertas),
TaxPredict (RAG para referências normativas), ai-engine (geração de texto para o
laudo via LLM local + OpenAI).

**SLA:** p95 < 5s; laudo em PDF gerado < 30s.

**Atenção PbD:** DanoBot usa DATASUS (dado sensível, art. 11). Mesma proteção da
ComplianceRadar: k-anonymity reforçada, base legal documentada, `source_date` e
`lag_days` no laudo.

### 7.3 PetiBot (Semanas 47–49)

**Objetivo:** Gerador de peças processuais com citação de jurisprudência verificável.

**Engines reutilizados:** TaxPredict (RAG jurisprudencial), DanoBot (para laudos
de suporte), ai-engine (geração GENERATION → OpenAI; citações via RAG consensual
com ≥ 3 acórdãos por afirmação).

**SLA:** p95 < 10s; citações verificáveis (link para DATAJUD ou número do processo).

**Riscos:** Alucinação de citações → RAG consensual com verificação cruzada; cada
citação gerada é verificada contra o índice OpenSearch antes de ser incluída na peça.

### 7.4 ConciliaIA (Semanas 50–52)

**Objetivo:** Análise de viabilidade de acordos tributários e judiciais.

**Engines reutilizados:** LegalScore (risco da contraparte), ComplianceRadar
(indicadores fiscais do município), TaxPredict (probabilidade de desfecho).

**SLA:** p95 < 3s.

### 7.5 Migração K8s (Paralelo à Fase 4)

**Gatilho:** > 70% CPU sustentado por 7 dias **ou** > 50 containers em produção.

Sequência: Helm charts por serviço → HPA por serviço → PG HA (Patroni) → Redis HA
(Sentinel/Cluster) → Neo4j HA (se Enterprise) → Ingress NGINX (substitui Traefik)
→ testes de caos (Chaos Monkey) → corte de produção.

SLA pós-K8s: ~99,9% (conforme Seção 1.2).

---

## 8. Mapa de migração futura

> **Regra:** nenhuma fronteira SEAMS é criada antes de existir evidência medida de
> que a migração vale o custo. A exceção são as fronteiras que já existem
> (`ScoreEngine` e `AlertPublisher`) — estas são mantidas porque o custo de criá-las
> foi pago e elas não trazem overhead operacional.

| Componente | Contrato | Suíte de contrato | Gatilho medido | Recomendação de hoje | Dia da migração |
|---|---|---|---|---|---|
| **MLR Batch Scorer** (LegalScore) | `ScoreEngine` Protocol + `ScoreRequest`/`ScoreResult` (scoring/v1) — `services/shared/contracts/scoring.py` | `services/scoring/tests/contract/test_score_engine_contract.py` — inclui equivalência cruzada Python × Rust | p95 > 2s para 1k CNPJs em load test | Todo chamador via `get_score_engine(settings.SCORING_BACKEND)`. Features chegam ao engine como `dict[str, float]` já calculadas. Engine nunca faz I/O. Nenhum caller importa `PythonScoreEngine` diretamente | `maturin develop --release` (crate `pyo3-scorer`). Rodar suíte de contrato: Rust e Python devem concordar no score para os mesmos inputs. `SCORING_BACKEND=auto`. **Nenhum chamador muda.** |
| **Alert Delivery** (ComplianceRadar + todos que publicam alertas) | `AlertPublisher` Protocol + `AlertEnvelope` (alerts/v1) — `services/shared/contracts/alerts.py` + `schemas/alert.v1.json` | `services/shared/alerts/tests/test_alert_contract.py` — valida que o envelope Python é aceito pelo schema que o Elixir usará | Cliente exige SLA 99% de entrega com confirmação que o Celery não consegue garantir | Todos os callers via `get_alert_publisher("outbox", db_conn=conn)`. `alerts_outbox` é a única fonte. `publish()` nunca muda | Subir Elixir/Oban apontando para `alerts_outbox` (mesma tabela Postgres). Desligar worker Celery de entrega. **Nenhum caller muda.** Idempotência (`alert_id`) e cooldown (`dedup_key`) já estão no banco — sem entrega dupla na transição. |
| **IsolationForest** (ContabilIA) | Sem fronteira SEAMS agora — escala com réplicas Python (ContabilIA é I/O-bound, não CPU-bound) | Criar `AnomalyEngine` Protocol + suíte apenas quando o gatilho aparecer | p95 > 5s para 10k linhas contábeis em load test de ContabilIA | Python puro. Não criar fronteira prematuramente. | A definir se e quando gatilho for atingido. Ponto de partida: `AnomalyEngine` Protocol análogo ao `ScoreEngine`. |
| **TribunaConnect** (Fase 4+, colaboração multi-escritório) | Elixir protagonista (LiveView + PubSub + GenServer). Python chamado para análise RAG via HTTP com header `X-Contract-Version` | `tests/contract/test_python_elixir_contract.py` — valida schema HTTP neutro (JSON Schema) | Necessidade real de colaboração multi-escritório em tempo real | Não existe ainda. Quando o produto for construído, nasce direto em Elixir — não há migração de Python. | N/A — já nasce em Elixir |

---

## 9. Engenharia de dados — visão por fonte

### 9.1 Tabela de fontes: 5 Vs, cadência e produto

| Fonte | Volume | Velocidade | Variedade | Veracidade (lag) | Valor (produto habilitado) |
|---|---|---|---|---|---|
| Receita Federal | ~45M CNPJs | Diária | JSON/CSV | 1–2 dias | LegalScore (cadastro) |
| DATAJUD (CNJ) | ~2 GB/dia | Diária | JSON | 1–7 dias | LegalScore, TaxPredict, PetiBot |
| PGFN | ~30M registros | Semanal | CSV | 7–14 dias | LegalScore, ContabilIA |
| CAGED (MTE) | ~15M vínculos/mês | Mensal | CSV | ~30 dias | ContabilIA (CC01) |
| SICONFI (STN) | ~5.570 municípios | Mensal | JSON/XML | ~60 dias | ContabilIA (CC02), ComplianceRadar |
| PNCP | Variável | Diária | JSON | 1–3 dias | ContabilIA (CC03), LicitaWatch |
| DATASUS/SIH | ~30M registros/mês | Mensal | CSV | ~90 dias | ComplianceRadar (sensível), DanoBot (sensível) |
| SNIS (MDR) | ~5.570 municípios | **Anual** | CSV | **~548 dias** | ComplianceRadar |
| INEP | ~200k escolas | **Anual** | CSV | **~365 dias** | ComplianceRadar, DanoBot |
| ComexStat | Variável | Mensal | CSV | ~30 dias | ContabilIA (CC04) |
| Portal Transparência | Variável | Horária | JSON | ~1 hora | ContabilIA, ComplianceRadar |
| Câmara Deputados | Variável | On-demand | JSON | Dias | PetiBot |
| BCB/ESTBAN | ~5.570 municípios | Mensal | CSV | ~30 dias | ComplianceRadar |
| IBGE | ~5.570 municípios | **Anual** | CSV | **~365 dias** | ComplianceRadar, DanoBot |

### 9.2 Gates de qualidade de dados por fase

**Fase 0:** Template de data contract definido.

**Fase 1 (DATAJUD, PGFN, Receita):** schema validado na entrada; faltantes < 5% nos campos obrigatórios; deduplicação por `numero_processo`/CNPJ; linhagem bronze→gold.

**Fase 2 (CAGED, SICONFI, PNCP, ComexStat):** mesmos gates + validação de Benford só após N ≥ 100 registros + Z-score só após higiene (outliers de higiene removidos antes de calcular).

**Fase 3 (DATASUS, SNIS, INEP, IBGE):** todo registro com `lag_days` preenchido; k-anonymity reforçada para DATASUS (células < 5 suprimidas); reconciliação in/out < 1% para fontes anuais.

### 9.3 ROPA — Registro de base legal (resumo)

> Documento completo em `docs/ROPA.md`. Esta tabela é o resumo de referência rápida.

| Fonte | Classificação | Base legal LGPD | Finalidade |
|---|---|---|---|
| Receita Federal (CNPJ) | Dado público | Art. 7º, §3º (dado público) | Enriquecimento cadastral de PJ |
| DATAJUD | Dado público (processos) | Art. 7º, §3º + interesse legítimo (art. 10) | LegalScore, TaxPredict |
| PGFN | Dado público | Art. 7º, §3º | LegalScore |
| CAGED | Dado agregado (sem PF identificável) | Interesse legítimo (art. 10) | ContabilIA CC01 |
| SICONFI | Dado público de ente público | Art. 7º, §3º | ContabilIA, ComplianceRadar |
| PNCP | Dado público | Art. 7º, §3º | ContabilIA CC03, LicitaWatch |
| **DATASUS/SIH** | **Dado sensível — saúde (art. 11)** | **Pesquisa ou interesse público legítimo com salvaguardas** | ComplianceRadar, DanoBot |
| SNIS | Dado público de ente público | Art. 7º, §3º | ComplianceRadar |
| INEP | Dado público | Art. 7º, §3º | ComplianceRadar, DanoBot |
| ComexStat | Dado público | Art. 7º, §3º | ContabilIA CC04 |
| Portal Transparência | Dado público | Art. 7º, §3º | ContabilIA, ComplianceRadar |
| Câmara Deputados | Dado público | Art. 7º, §3º | PetiBot |
| BCB/ESTBAN | Dado público | Art. 7º, §3º | ComplianceRadar |
| IBGE | Dado público | Art. 7º, §3º | ComplianceRadar, DanoBot |

> **DATASUS é dado sensível (saúde, art. 11 LGPD).** Todo processamento requer
> base legal específica, k-anonymity reforçada (células < 5 suprimidas) e
> nenhum dado identificável no payload de alertas ou no laudo.

---

## 10. Checklist de qualidade e segurança

> Cada item é marcável e verificável por teste. "Feito" sem teste que comprove
> não conta como feito.

### Por fase

**Fase 0 — Obrigatório antes de qualquer produto:**
- [ ] Nenhuma porta de banco exposta no host.
- [ ] Traefik dashboard seguro (sem `--api.insecure`).
- [ ] HMAC-SHA256 com chave Docker Secret para pseudonimização; sem SHA-256 simples; sem truncamento.
- [ ] Buckets MinIO privados; acesso anônimo retorna 403.
- [ ] Decision Ledger: `get_proof()` e `verify_integrity()` implementados e testados.
- [ ] Contratos SEAMS nos caminhos canônicos; suítes de contrato passando.
- [ ] `docs/API-GUIDELINES.md` criado; endpoint de referência conforme o padrão.
- [ ] `docs/ROPA.md` com base legal das 14 fontes e classificação pessoal × sensível.
- [ ] Decisão de licença Neo4j registrada.
- [ ] CI com jobs unit + integração + contrato; gate de cobertura ≥ 80%.
- [ ] SLA honesto por fase documentado; badge README atualizado.

**Por produto (repetido em cada fase):**
- [ ] API na convenção `/api/v1/{produto}/{recurso}`; versionamento único.
- [ ] Contrato de erro `application/problem+json` em todos os endpoints.
- [ ] Rate limiting por tenant testado.
- [ ] Idempotência em POSTs de criação testada.
- [ ] OpenAPI 3.1 com exemplos reais de resposta (sucesso + erros).
- [ ] Zero anti-patterns de API (gate no CI).
- [ ] Data contract por fonte; tratamento de faltantes/outliers/normalização antes de qualquer análise.
- [ ] Linhagem bronze→silver→gold com `source`, `ingested_at`, `transform_version`.
- [ ] Reconciliação in/out < 2% por execução.
- [ ] Toda saída com dado de lag carrega `source_date` e `lag_days`.
- [ ] Métricas SMART de negócio e modelo definidas; loop de feedback planejado.
- [ ] Timeout + backoff/jitter + circuit breaker por fonte externa.
- [ ] Degradação graciosa com flag em vez de 500.
- [ ] Testes unit ≥ 80%; integração com Docker real; contrato por fronteira; E2E por produto.
- [ ] Load test com SLA medido (não estimado).
- [ ] CPF/nome pseudonimizados com HMAC antes de qualquer persistência.
- [ ] Dado de saúde (DATASUS): k-anonymity reforçada; base legal no ROPA.
- [ ] Right-to-erasure implementado e testado para o produto.
- [ ] Audit trail de acesso a dados pessoais.
- [ ] Logs JSON estruturados com `request_id`, `tenant`, `source` → Loki.
- [ ] Métricas Prometheus por endpoint (latência, erros, saturation).
- [ ] OpenTelemetry span em todas as fronteiras de serviço.
- [ ] Playbook de incidentes do produto (score errado / falha de entrega / Ledger corrompido).
- [ ] Docker Secrets em produção; `.env` só em dev; nenhum segredo em variável de ambiente.

### Qualidade de modelos

- [ ] LegalScore: rotulado como heurística até AUC, Brier e calibração medidos contra desfechos reais.
- [ ] LegalScore: IC derivado do sigma do modelo (não bootstrap sobre coeficientes fixos).
- [ ] TaxPredict: MCMC nunca no path da request; preditiva posterior pré-calculada.
- [ ] TaxPredict: `predict(case)` condiciona no caso de entrada (`pm.set_data`).
- [ ] TaxPredict: API PyMC5 exclusivamente.
- [ ] AnomalyDetector: `fit()` separado de `detect()`; fallback com lógica correta.
- [ ] Modelo rotulado como "calibrado" apenas após métricas de discriminação e calibração satisfatórias.

---

## 11. Definition of Done (por produto — resumo)

Um produto está "completo" quando todos os itens abaixo estão verdes:

1. Todas as fases do roadmap com critérios de aceite verificados.
2. Suítes unit / integração / contrato / E2E passando no CI; cobertura ≥ 80%.
3. Guardrails de segurança e LGPD aplicáveis verificados por teste.
4. SLA medido em load test sustentado (não estimado).
5. API conforme P2: versionamento, `problem+json`, rate limit, idempotência, exemplos OpenAPI.
6. Gates de qualidade de dados verdes: data contract, linhagem, reconciliação, `source_date`+`lag_days`.
7. Fronteiras de migração com contrato + suíte de contrato no lugar (mesmo que Python puro hoje).
8. Observabilidade: logs/métricas/tracing e playbook de incidentes.
9. OpenAPI 3.1 com exemplos reais de resposta.
10. ROPA atualizado com base legal do produto; dado sensível identificado e protegido.

---

## 12. Estimativas e gatilhos de ferramenta

| Decisão | De | Para | Gatilho | Custo de não-migrar | Custo de migrar |
|---|---|---|---|---|---|
| Orquestração | Celery + Beat | Apache Airflow | > 15 DAGs ativos **ou** > 5M registros/DAG | Dependências implícitas entre tasks; debugging difícil | ~2 sprints para migrar DAGs; overhead operacional do Airflow |
| Container runtime | Docker Compose | Kubernetes (Helm) | > 70% CPU sustentado por 7d **ou** > 50 containers | Auto-scaling manual; sem HA nativo | ~3–4 sprints para Helm charts + testes de caos |
| Scoring engine | Python (MLR) | Rust via PyO3 | p95 > 2s para 1k CNPJs | Latência alta em batch | ~2 sprints (crate + suíte de equivalência) |
| Entrega de alertas | Celery | Elixir/Oban | Cliente exige SLA 99% com confirmação | SLA de entrega não garantido | ~3 sprints (umbrella Elixir + Oban + Phoenix Channels) |
| LLM classificação/NER | OpenAI | Ollama (local) | Custo OpenAI > R$ X/mês | Custo crescente | ~1 sprint (já configurado; ativar rota Ollama) |
| Busca textual | OpenSearch single-node | OpenSearch cluster | > 50GB de índice **ou** p99 > 5s em busca | Indisponibilidade em manutenção | ~1–2 sprints para configurar cluster |

---

## Apêndice — Recomendações das fontes de referência

> Estes blocos sintetizam os quatro eixos de boas práticas usados neste roadmap.
> Anexar ao ROADMAP.md para referência do time.

**Projeto e Arquitetura de APIs (Lachi / Ress):** avaliar substantivos autoexplicativos e métodos HTTP corretos; verificar anti-patterns (versionamento ausente, sem documentação, sem rate limiting, sem logs estruturados); exigir observabilidade completa (logs com contexto, métricas, distributed tracing); arquitetura de plugins via Protocol/interface (ponto de entrada único, ciclo de vida, compatibilidade entre versões).

**Arquitetura de Software (Carezzato):** mapear atributos de qualidade a táticas concretas; justificar cada decisão pelo custo cumulativo (não custo imediato); exigir CI/CD com automação de testes e containers desde o início; verificar logging/tracing/monitoring em toda fronteira; aplicar Security by Design (criptografia, privilégio mínimo, conformidade LGPD/GDPR) como requisito, não como auditoria posterior.

**Sistemas de Uso Intensivo de Dados (Cartolano):** avaliar os 5 Vs e o alinhamento ao negócio antes de ingerir qualquer fonte; verificar ETL completo (faltantes, outliers de higiene, normalização, integração rastreável); aplicar princípios de microsserviços (domínio definido, baixo acoplamento, deploy independente, resiliência); seguir o ciclo analítico completo (problema → coleta → preparação → modelagem → comunicação → **feedback**) com métricas SMART e loop que liga predição a desfecho real.

**Privacy by Design / LGPD (Schuch):** seguir os 7 princípios PbD como requisitos verificáveis; documentar a base legal por tratamento antes de ir a produção (ROPA); classificar dado pessoal × sensível explicitamente — dado de saúde (DATASUS, art. 11) exige proteção adicional e justificativa de processamento; manter plano de resposta a incidentes com cadeia de evidências auditável e prazo de comunicação à ANPD conforme art. 48.
