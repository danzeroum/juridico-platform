# 99 — Dicionário Global de Dados

> Consolidação de **todos os dados que circulam no sistema**, extraída dos mapeamentos linha a linha (arquivos 01–10).
> Cada tabela lista o dado, seu formato, quem **produz** (⇒) e quem **consome** (⇐). É o índice mestre para rastrear
> qualquer dado de ponta a ponta.
>
> **Legenda:** 🔒 sensível (PII/segredo) · 🌐 cruza fronteira de linguagem/processo.

---

## 1. Chaves Redis (cache · idempotência · broker · rate-limit)

| Chave | Conteúdo | TTL | Produtor (⇒) | Consumidor (⇐) |
|---|---|---|---|---|
| `receita:{cnpj}` 🔒 | JSON cadastral Receita (silver) | 7d | ingest `receita` | scoring `assemble_features`, gateway `company_profile` |
| `pgfn:{cnpj}` 🔒 | JSON dívida ativa (silver) | 7d | ingest `pgfn` | scoring `assemble_features` |
| `pncp:{cnpj_orgao}:{ano}:{numero}` | contrato PNCP (silver) | 24h | ingest `pncp` | licitawatch |
| `caged:{cnpj}:{competencia}` | emprego (silver) | 30d | ingest `caged` | compliance/scoring (futuro) |
| `siconfi:{cod_ibge}:{exercicio}` | execução orçamentária | 7d | ingest `siconfi` | compliance |
| `ibge:{cod_ibge}` | indicadores socioeconômicos | 30d | ingest `ibge` | compliance |
| `snis:{cod_ibge}` | saneamento | — | ingest (contrato snis) | compliance |
| `consumidor:{slug}` | reputação Consumidor.gov (agregada) | 30d | ingest `consumidor_gov` | defensor `reputacao` |
| `datajud:{date}` 🔒 | resposta bruta DATAJUD (fallback) | 48h | ingest `datajud` | ingest (recuperação) |
| `score:{cnpj}` 🔒 | LegalScore recente | — | (produtor externo/cache) | concilia `_get_legalscore` |
| `idemp:{tenant_id}:{key}` | resultado idempotente (retry-safety) | 24h | gateway (legalscore/fiscal) | gateway |
| `batch:{job_id}` | estado do batch de scoring | 24h | scoring `create_batch_job`/`update_batch_progress` | gateway `batch_status` |
| `ratelimit:{tenant_id}:{minuto}` | contador INCR | 60s | `RateLimitMiddleware` | `RateLimitMiddleware` |
| `llm:{sha256(model:template_ver:prompt)}` | resposta LLM memoizada | 30d | `LLMMemoizer` | `LLMMemoizer` |
| `compliance_alert:*` | alertas municipais renderizados | — | compliance | gateway `/compliance/alerts` |
| broker `REDIS_URL` (db 0) | filas Celery + backend de resultado | — | gateway `send_task`, beat | workers |

---

## 2. PostgreSQL — schemas, tabelas e colunas

**RLS FORCE** (isolamento por tenant via `SET LOCAL app.tenant_id`): schemas `tenant`, `ledger`, `fiscal.triage_*`.
Tabelas de referência (`fiscal.*` exceto triage, `jurimetria.*`) são **globais** (sem RLS).

### schema `tenant`
| Tabela | Colunas |
|---|---|
| `tenant.tenants` | id(uuid PK), slug(UK), name, plan, active, created_at |
| `tenant.users` | id(uuid PK), tenant_id(FK), email, role(admin\|analyst\|viewer), active, created_at, password_hash 🔒 (`pbkdf2_sha256$iters$salt$hash`), name; UNIQUE(tenant_id,email) |
| `tenant.idempotency_keys` | key(PK), tenant_id(PK/FK), response(jsonb), created_at |

### schema `ledger`
| Tabela | Colunas |
|---|---|
| `ledger.entries` | id, request_id(UK), entry_index, created_at, product, tenant_id(FK), inputs_hash(sha256), outputs_hash(sha256), sources(jsonb), weights_applied(jsonb), subject_token 🔒 (AES-256-GCM), leaf_hash, merkle_root; UNIQUE(tenant_id,entry_index); trigger append-only (bloqueia UPDATE/DELETE) |
| `ledger.anchors` | id, anchor_at_index, merkle_root, tenant_id(FK), created_at (checkpoint a cada 1024) |

### schema `ingest` / `public`
| Tabela | Colunas |
|---|---|
| `ingest.runs` | id, source, started_at, finished_at, status, records_in, records_out, transform_version, error_msg |
| `public.alerts_outbox` | alert_id(PK), dedup_key, envelope(jsonb, `alerts/v1`), status, attempts, available_at, created_at; idx(status,available_at), idx(dedup_key) |
| `public.tenant_isolation_probe` | id, tenant_id, payload (teste de RLS) |
| `public.schema_migrations` | version(PK), checksum(sha256), applied_at |

### schema `fiscal`
| Tabela | Colunas |
|---|---|
| `fiscal.ncm` | id, ncm_codigo, descricao, capitulo, vigencia(daterange, EXCLUDE no-overlap), source, ingested_at, transform_version |
| `fiscal.ncm_migracao` | id, ncm_origem, ncm_destino, vigencia_inicio, vigencia_fim, ato_legal, ingested_at |
| `fiscal.ipi_aliquota` | id, ncm_codigo, excecao, aliquota_pct, vigencia, fundamento_legal, source, ingested_at, transform_version |
| `fiscal.icms_interestadual` | id, uf_origem, uf_destino, aliquota_pct, importado, fundamento_legal, vigencia, source, ingested_at |
| `fiscal.icms_interno` | id, uf, ncm_prefix, aliquota_pct, fcp_pct, ibs_pct, cbs_pct, fundamento_legal, vigencia, source, ingested_at, transform_version |
| `fiscal.categoria` | id, slug, nome, descricao |
| `fiscal.ncm_categoria` | id, ncm_prefix, categoria_id(FK), confianca |
| `fiscal.doc_hash` | id, fonte, file_hash(sha256), url, processed_at (dedup CONFAZ/Diário) |
| `fiscal.triage_job` 🔒(RLS) | job_id(PK), tenant_id, status, total, processed, spreadsheet_key, result_key, batch_merkle_root, ledger_request_id, created_at, completed_at |
| `fiscal.triage_item` 🔒(RLS) | id, job_id(FK), tenant_id, leaf_index, sku_descricao, ncm_sugerido, confidence, fonte_regra, icms_interno_efetivo_pct, icms_inter_pct, difal_pct, categoria, conflito, observacoes(jsonb) |

### schema `jurimetria` (global, gold)
| Tabela | Colunas |
|---|---|
| `jurimetria.tpu_classe` | codigo(PK), label, parent_codigo, hierarchy_path, source, ingested_at, transform_version |
| `jurimetria.tpu_assunto` | codigo(PK), label, parent_codigo, ramo, source, ingested_at, transform_version |
| `jurimetria.indicador` | tribunal, classe_tpu, assunto_tpu, periodo, fonte(DATAJUD\|BLEND\|ABJ) — PK composta; n_processos, duracao_mediana_dias, duracao_p25_dias, duracao_p75_dias, taxa_congestionamento, taxa_litigiosidade, pct_provimento, source, ingested_at, transform_version |
| `jurimetria.abj_indicador_raw` | id, tribunal, classe_cnj, assunto_cnj, periodo, tempo_medio_dias, taxa_congestionamento, casos_novos, casos_baixados, casos_pendentes, source, ingested_at, transform_version |

**Role de aplicação:** `app_user` (NOSUPERUSER — necessário para RLS FORCE valer). **Seeds:** tenant `00000000-…-0001`/`dev-tenant`; user `admin@dev.com`/`dev12345` 🔒; 702 ICMS interestadual + 3 interno + 5 categorias.

---

## 3. MinIO (S3) — buckets e chaves

| Bucket | Chave | Conteúdo | Produtor | Consumidor |
|---|---|---|---|---|
| `bronze-{source}` (ex.: `bronze-datajud`, `bronze-abj`) | `dt=YYYY-MM-DD/part-{uuid.hex}.jsonl` | bronze cru (JSONL, Hive-partitioned) | ingest `persist_silver` | data lake / reprocesso |
| `documents` | `{spreadsheet_key}` (ex.: `fiscal/uploads/{tenant}/{job}.xlsx`) | planilhas fiscais | gateway/fiscal `upload_spreadsheet` | fiscal-worker `download_spreadsheet` |
| `gold` | `taxpredict/{materia}.nc` | trace ArviZ NetCDF (modelo Bayesiano) | taxpredict `recalibrate_model` | taxpredict `load_from_minio` |
| `gold` | `taxpredict/training/{materia}.parquet` | dataset de treino | (pipeline offline) | taxpredict `recalibrate_model` |
| `silver`, `backups` | — | reservados (medalhão / backup) | — | — |

Buckets criados por `minio-init` (privados; versionamento em bronze/silver/gold).

---

## 4. OpenSearch — índices

| Índice | `_id` | Conteúdo | Produtor | Consumidor |
|---|---|---|---|---|
| `datajud-silver-{YYYY-MM}` 🔒 | `id_processo` | processos silver (pseudonimizados) | ingest `datajud` → `persist_silver` | jurimetria_aggregate (`datajud-silver-*`) |
| `abj-silver` | `tribunal` | indicadores ABJ | ingest `abj` | jurimetria_aggregate |

---

## 5. ChromaDB — coleções (RAG)

| Coleção | Conteúdo | Embedding | Produtor | Consumidor |
|---|---|---|---|---|
| `juridico` | documentos jurídicos gerais (default) | BGE-M3 (Ollama) | `RAGEngine.upsert_document` | RAG genérico |
| `petibot_jurisprudencia` | precedentes | BGE-M3 | indexação PetiBot | petibot/defensor `_lookup_precedentes` |
| `fiscal_ncm` | descrições NCM oficiais | BGE-M3 | `RagNcmSource.index_ncm` | fiscal `classify` (fallback semântico) |
| `taxpredict_jurisprudencia` | jurisprudência tributária | BGE-M3 | indexação taxpredict | gateway taxpredict `_rag_lookup` |

Métrica `hnsw:space=cosine`; dedup por `content_hash` (sha256 do conteúdo).

---

## 6. Neo4j — grafo de litigância

- **Nós:** `Empresa {cnpj}` · `Processo {id, tribunal, classe, assunto, ramo, data_julgamento, valor_log}`.
- **Aresta:** `(:Empresa)-[:PARTE_EM]->(:Processo)`.
- **Constraints:** `processo_id`, `empresa_cnpj`.
- **Escrita:** `upsert_process_edges(records)` (ingest datajud, `UNWIND … MERGE`).
- **Leitura:** `count_processos_por_cnpj(cnpj)`→`{total,trabalhistas,repetitivos}` (scoring); `company_processes`, `litigant_network`, `graph_stats` (knowledge_graph).

---

## 7. Celery — tasks, filas e apps

| App | Task | Args | Fila |
|---|---|---|---|
| `services.scoring.celery_app` | `scoring.tasks.run_batch_score` | job_id, cnpjs 🔒 | `scoring` |
| `services.fiscal.celery_app` | `fiscal.tasks.enrich_spreadsheet` | job_id, tenant_id, spreadsheet_key, uf_origem | `fiscal` |
| ″ | `fiscal.tasks.classify_chunk` | rows, uf_origem | `fiscal` |
| ″ | `fiscal.tasks.finalize_enrichment` | chunk_results, job_id, tenant_id | `fiscal` |
| ″ (worker fiscal) | `fiscal.ingestion.rfb_tipi.run_ingest` | url | `fiscal_ingest` |
| ″ | `fiscal.ingestion.sefaz_scraper.run_ingest` | uf | `fiscal_ingest` |
| ″ | `fiscal.ingestion.confaz_discovery.run_ingest` → enfileira `confaz_ocr` | index_url / pdf_url | `fiscal_ingest` |
| ″ | `fiscal.ingestion.ncm_history.run_ingest` | url | `fiscal_ingest` |
| `services.ingest.celery_app` | `datajud.run_daily_ingest` | date? | `daily` |
| ″ | `receita.run_weekly_ingest(_single)`, `pgfn.run_weekly_ingest(_single)` | cnpjs/cnpj | `weekly` |
| ″ | `pncp.run_daily_ingest` | cnpj_orgao, ano | `daily` |
| ″ | `caged.run_monthly_ingest`, `siconfi.run_monthly_ingest`, `abj.run_monthly_ingest`, `jurimetria_aggregate.run_aggregation` | vários | `monthly` |
| ″ | `ibge.run_ingest`, `consumidor_gov.run_ingest`, `transparencia.run_hourly_check` (stub) | uf/url | `daily`/`hourly` |
| `services.taxpredict.celery_app` | `taxpredict.recalibrate` | materia | `taxpredict` |

Beat: `fiscal-beat` (TIPI mensal, CONFAZ/SEFAZ semanal); scheduling geral do ingest é externo (Makefile/gateway).

---

## 8. Variáveis de ambiente e segredos

**Segredos 🔒** (`/run/secrets/<lower>` → env `<UPPER>`, via `load_secret`): `POSTGRES_PASSWORD`, `APP_USER_PASSWORD`,
`NEO4J_PASSWORD`, `REDIS_PASSWORD`, `MINIO_PASSWORD`/`MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`, `LLM_API_KEY`, `JWT_SECRET`
(+ `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` RS256), `HMAC_KEY`, `DATAJUD_TOKEN`, `GRAFANA_PASSWORD`, `SLACK_WEBHOOK_URL`,
`CONSUMIDOR_GOV_USER/PASSWORD`, `PROCON_SP_USER/PASSWORD`; DSNs derivadas `DATABASE_URL`, `MIGRATIONS_DATABASE_URL`,
`REDIS_URL`, `CELERY_BROKER_URL`.

**Config (não-secreta):** `POSTGRES_USER/DB`, `PGBOUNCER_*`, `NEO4J_URL/USER`, `OPENSEARCH_URL`, `CHROMA_URL`, `MINIO_URL`,
`OLLAMA_URL`/`OLLAMA_HOST`, `LLM_PROVIDER/BASE_URL/MODEL/MODEL_LOCAL/MODEL_PRIMARY/MODEL_FAST`, `PROTOCOLO_MODO`,
`SCORING_BACKEND` (python\|rust\|auto), `RATE_LIMIT_PER_MIN`, `RATE_LIMIT_FAIL_CLOSED`, `JWT_EXPIRY_HOURS/SECONDS`, `JWT_ISSUER`,
`DATAJUD_API_URL`, `ABJ_ENABLED/DATA_URL`, `TIPI_CSV_URL`, `PLAYWRIGHT_EXECUTABLE/BROWSERS_PATH`, `LETSENCRYPT_EMAIL`,
`DOMAIN`, `ALERT_EMAIL`, `OTEL_EXPORTER_OTLP_ENDPOINT`.

**Frontend (build/runtime):** `NEXT_PUBLIC_GATEWAY_URL` (default `http://localhost:8000`), `NEXT_PUBLIC_DEMO_MODE`
(`!=='false'`→demo ON), `REQUIRE_AUTH` (`==='true'`→middleware), `NODE_ENV`, `NEXT_SERVER_ACTIONS_ALLOWED_ORIGINS`.
**CI:** `HMAC_KEY` 🔒, `ENV=test`.

---

## 9. Contratos cross-linguagem (DTOs) 🌐

Espelhamento **manual** (sem code-gen), sincronizado por `contract_version`. Fronteira: Pydantic (Python) → JSON (HTTP) → interface (TS).

| Python (`services/shared/contracts`) | contract_version | TypeScript (`frontend/.../lib/api`) |
|---|---|---|
| `ScoreResult` / router `ScoreResponse` | `scoring/v1` | `LegalScoreResult` |
| `TaxPredictResponse` / `JurisprudenciaHit` | `taxpredict/v1` | `TaxPredictResult` / `JurisprudenciaHit` |
| `PetiResponse` / `PetiSection` | `petibot/v1` | `PetiResult` / `PetiSection` |
| `ConciliaResponse` / `ConciliaFator` | `concilia/v1` | `ConciliaResult` / `ConciliaFator` |
| `DefensorResponse` / `EventoAgente` | `defensor/v1` | `DefensorResult` / `EventoAgente`(≈`AgentEvent`) |
| `ProtocoloResultado` | `protocolo/v1` | `ProtocoloResult` |
| `NcmTriageResult` / `IcmsResolution` | `fiscal/v1` | (sem interface TS dedicada) |
| `AlertEnvelope` | `alerts/v1` | `AlertItem` (parcial) **e** `schemas/alert.v1.json` (🌐 Elixir/Oban) |
| erro RFC 9457 (gateway) | `1.0` | `ProblemJson` / `ApiError` |
| claims JWT `{sub,tenant_id,role}` | — | `MeResponse` |

**Nota:** `alert.v1.json` é **mais estrito** que o `AlertEnvelope` Pydantic (`minLength:1`, `minItems:1`). `LegalScoreResult` e
`MeResponse` são as únicas respostas TS sem `contract_version`.

---

## 10. Enums canônicos (mesmos valores em Python e TS)

| Enum | Valores | Python | TS (`@juridico/tokens`) |
|---|---|---|---|
| RiskLevel | BAIXO, MODERADO, ALTO, CRITICO | `contracts/scoring` | `RiskLevel` |
| Severity / AlertSeverity | LOW, MEDIUM, HIGH, CRITICAL | `contracts/alerts` | `AlertSeverity` |
| Channel / AlertChannel | webhook, email, slack, whatsapp | `contracts/alerts` | `AlertChannel` |
| TipoAcao / TipoCaso | TRABALHISTA, CIVEL, TRIBUTARIO, PREVIDENCIARIO, ADMINISTRATIVO, CONSUMERISTA | `contracts/petibot`,`defensor` | — |
| Canal | PROCON, CONSUMIDOR_GOV, OUVIDORIA, CONTENCIOSO | `contracts/defensor` | — |
| ProtocoloModo | simulacao, real | `contracts/protocolo` | `ProtocolMode` |
| ProtocoloStatus | SIMULADO, ENVIADO, FALHA, AGUARDA_CREDENCIAIS, CANAL_NAO_SUPORTADO | `contracts/protocolo` | `ProtocolStatus` |
| Materia | PIS_COFINS, IRPJ, CSLL, ICMS, IPI, ISS, SIMPLES | `contracts/taxpredict` | — |
| Decisao | FAVORAVEL, DESFAVORAVEL, PARCIAL, DESCONHECIDO | `contracts/taxpredict` | — |
| UF | 27 siglas | `contracts/fiscal` | — |
| FonteRegra | TIPI, SENADO, CONFAZ, SEFAZ, FUZZY, RAG | `contracts/fiscal` | — |
| RbacRole | admin, analyst, viewer | claim JWT `role` | `RbacRole` |
| FreshnessBand | fresh, stale, very_stale | (derivado lag) | `FreshnessBand` |
| DataClass | publico, pessoal, sensivel | — | `DataClass` |
| DeliveryStatus | pending, claimed, done, failed | — | `DeliveryStatus` |
| JobStatus | queued, running, done, failed | estado batch | `JobStatus` |
| ModelStatus | heuristica, calibrado | validation | `ModelStatus` |
| EventoAgente.status | ok, running, pending | `contracts/defensor` | `EventStatus` |

---

## 11. APIs governamentais externas (origem de dados) 🌐

| Fonte | Base URL | Auth | Cadência |
|---|---|---|---|
| DATAJUD (CNJ) | `api-publica.datajud.cnj.jus.br` | `Authorization: APIKey {DATAJUD_TOKEN}` 🔒 | diária |
| Receita (CNPJ) | `publica.cnpj.ws/cnpj` | — | semanal |
| PGFN | `regularize.pgfn.gov.br/api` | — | semanal |
| PNCP | `pncp.gov.br/api/pncp/v1` | — | diária |
| CAGED | `api.dados.gov.br/v1/.../novo-caged` | — | mensal |
| SICONFI (STN) | `apidatalake.tesouro.gov.br/ords/siconfi/tt` | — | mensal |
| IBGE | `servicodados.ibge.gov.br/api/v1,v3` (agregados SIDRA) | — | anual/on-demand |
| BCB | `api.bcb.gov.br/dados/serie` (SGS 432 Selic, 1 câmbio) | — | mensal |
| Consumidor.gov | `consumidor.gov.br/pages/dadosabertos/...` | — | on-demand |
| TIPI (RFB) | `gov.br/receitafederal/.../tipi.csv` | — | mensal |
| CONFAZ | `confaz.fazenda.gov.br/legislacao/convenios` | — | semanal |
| SEFAZ (SP/RJ/MG) | portais estaduais (Playwright) | — | semanal |
| Ollama (LLM local) | `OLLAMA_URL` (`ollama:11434`) | — | runtime |
| OpenAI (opcional) | `LLM_BASE_URL` | `Bearer LLM_API_KEY` 🔒 | runtime |
| Elixir/Oban (alertas) | `{elixir}/api/v1/alertas/publicar` | `X-Contract-Version: alerts/v1` | on-event |

---

## 12. Fronteiras de linguagem (seams)

| Seam | Dado que cruza | Estado |
|---|---|---|
| **Python ↔ Rust** (`ScoreEngine`, PyO3) | ida `(cnae_2dig:str, features:dict[str,float])`; volta `{score:int, confidence_interval:(int,int), breakdown:dict}` | **Sem código Rust** — `RustScoreEngine.healthy()==False`; troca por `SCORING_BACKEND=rust` (futuro) |
| **Python ↔ Elixir** (`AlertPublisher`, `alerts/v1`) | `AlertEnvelope` (JSON) via outbox (`alerts_outbox`) ou HTTP POST | Publisher Python presente; consumidor Elixir/Oban planejado |
| **Python ↔ TypeScript** (HTTP REST) | DTOs da §9 (JSON `application/problem+json` nos erros) | Ativo; espelhamento manual |
| **Python ↔ FFI C++** (rapidfuzz, pdfplumber, PyMC/arviz, openpyxl, Playwright, Tesseract) | primitivos/bytes | Ativo (libs nativas) |

---

## Chaves de rastreabilidade

- **Correlação de request:** `request_id` (uuid) → `ledger.entries.request_id` → `GET /{produto}/audit/{request_id}` (prova Merkle).
- **Correlação de titular (LGPD):** CNPJ/CPF 🔒 → `hash_user_id` (HMAC-SHA256) → `encrypt_for_ledger` (AES-256-GCM) → `subject_token`;
  `erase_titular` (crypto-shredding) apaga a chave sem quebrar a prova.
- **Correlação de lote fiscal:** `job_id` → `fiscal.triage_job.batch_merkle_root` + `ledger_request_id`; cada item tem `decision_proof` (prova O(log N)).
- **Versão de transformação:** `transform_version` (linage em toda tabela ingerida) + `contract_version` (todo DTO).

---

*Fim do mapeamento de dados. Ver arquivos 01–10 para o detalhe linha a linha de cada módulo.*
