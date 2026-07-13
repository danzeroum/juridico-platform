# Arquitetura Completa — Diagramas de Todo o Repositório (`juridico-platform`)

> Conjunto **completo** de diagramas de arquitetura cobrindo o repositório inteiro: visões C4,
> modelo de dados (ER), pipeline de dados, topologia Celery, segurança/multi-tenant, IA/RAG,
> um diagrama por produto (9 + transversais), frontend, máquinas de estado e CI/CD.
>
> Complementa `docs/arquitetura-uml.md` (que traz as visões UML clássicas: casos de uso, pacotes,
> componentes, classes, sequência, atividades, implantação). Aqui o foco são as **visões
> arquiteturais** e a cobertura **produto a produto**. Todos os diagramas são Mermaid validados.

## Índice

| # | Visão | Seção |
|---|---|---|
| A | **C4** — Contexto, Containers, Componentes | §1–§3 |
| B | **Dados** — ER, pipeline medalhão, mapa de stores, Celery | §4–§7 |
| C | **Segurança** — auth/multi-tenant, Ledger/LGPD, alertas | §8–§10 |
| D | **IA** — RAG/LLM | §11 |
| E | **Produtos** — 9 produtos + cluster analítico | §12–§21 |
| F | **Frontend** — rotas, design system, dados React | §22–§23 |
| G | **Estados** — máquinas de estado | §24 |
| H | **Entrega** — CI/CD e build | §25–§26 |

---

## 1. C4 Nível 1 — Diagrama de Contexto do Sistema

**Objetivo:** situar a plataforma entre seus usuários e sistemas externos.

```mermaid
C4Context
    title Contexto — Plataforma Jurídico-Contábil

    Person(analista, "Analista jurídico/contábil", "Consome os 9 produtos via UI")
    Person(admin, "Admin do tenant", "Gere papéis (RBAC) e configuração")
    Person(auditor, "Auditor / DPO", "Verifica trilha Merkle e executa erasure LGPD")

    System_Boundary(sb, "juridico-platform") {
        System(plat, "Plataforma", "Next.js + Gateway FastAPI + Workers Celery + malha de dados")
    }

    System_Ext(gov, "Fontes governamentais", "DATAJUD, Receita, PGFN, PNCP, IBGE, BCB, SICONFI, SEFAZ, CONFAZ, Consumidor.gov")
    System_Ext(llm, "LLM externo (opcional)", "OpenAI — usado quando LLM_PROVIDER=openai")
    System_Ext(alertas, "Serviço de Alertas (Elixir/Oban)", "Consome contrato alerts/v1 — planejado")
    System_Ext(portais, "Portais de defesa do consumidor", "PROCON / Consumidor.gov — protocolo automatizado (gated)")
    System_Ext(le, "Let's Encrypt", "Emissão de certificados TLS")

    Rel(analista, plat, "Usa", "HTTPS")
    Rel(admin, plat, "Administra", "HTTPS")
    Rel(auditor, plat, "Audita", "HTTPS")
    Rel(plat, gov, "Ingere dados", "HTTPS/scraping")
    Rel(plat, llm, "Gera texto", "HTTPS")
    Rel(plat, alertas, "Publica alertas", "outbox / HTTP")
    Rel(plat, portais, "Protocola", "Playwright")
    Rel(le, plat, "Emite TLS", "ACME")
```

**Legenda:** `Person` = ator humano; `System` = o sistema em análise; `System_Ext` = sistema externo;
`Rel` = relação com tecnologia.

**Notas:** apenas dois atores externos de escrita saem do sistema (alertas Elixir e portais de protocolo);
todo o resto é ingestão de leitura de fontes públicas. LLM externo é **opcional** — o padrão é Ollama local.

---

## 2. C4 Nível 2 — Diagrama de Containers

**Objetivo:** os processos/containers executáveis e como se comunicam.

```mermaid
C4Container
    title Containers — juridico-platform (nó único Docker Compose)

    Person(user, "Usuário", "Navegador")

    Container_Boundary(edge, "Borda") {
        Container(traefik, "Traefik v3", "Go", "Proxy reverso + TLS 1.3")
    }
    Container_Boundary(app, "Aplicação") {
        Container(next, "platform", "Next.js 14 / TS", "SPA + BFF de auth (App Router)")
        Container(gw, "gateway", "FastAPI / Python", "20 routers, JWT, rate-limit, problem+json")
    }
    Container_Boundary(work, "Workers") {
        Container(cw, "celery-worker", "Celery / Python", "Ingestão (daily/weekly/monthly/hourly)")
        Container(fw, "fiscal-worker", "Celery + Playwright + Tesseract", "Triagem em lote + scraping fiscal")
        Container(beat, "celery-beat / fiscal-beat", "Celery Beat", "Agendamento")
    }
    ContainerDb(pg, "PostgreSQL + PgBouncer", "SQL / RLS", "tenant, ledger, ingest, fiscal, jurimetria")
    ContainerDb(neo, "Neo4j 5", "Cypher", "Grafo de litigância")
    ContainerDb(os, "OpenSearch 2.12", "Lucene", "Silver full-text")
    ContainerDb(redis, "Redis 7", "KV", "Cache + broker + idempotência + rate-limit")
    ContainerDb(minio, "MinIO", "S3", "Bronze JSONL + gold (modelos)")
    ContainerDb(chroma, "ChromaDB", "Vetorial", "Embeddings RAG")
    Container(ollama, "Ollama", "LLM local", "Llama3:8b + BGE-M3")

    System_Ext(gov, "APIs gov", "")
    System_Ext(elixir, "Alertas Elixir/Oban", "")

    Rel(user, traefik, "HTTPS")
    Rel(traefik, next, "Host DOMAIN")
    Rel(traefik, gw, "/api")
    Rel(next, gw, "REST (cookie JWT)", "HTTP")
    Rel(gw, redis, "send_task + cache", "RESP")
    Rel(cw, redis, "broker", "RESP")
    Rel(fw, redis, "broker", "RESP")
    Rel(gw, pg, "RLS", "SQL")
    Rel(gw, neo, "grafo", "Bolt")
    Rel(gw, chroma, "RAG", "HTTP")
    Rel(gw, ollama, "embeddings/LLM", "HTTP")
    Rel(cw, pg, "silver/jurimetria", "SQL")
    Rel(cw, os, "bulk", "HTTP")
    Rel(cw, neo, "upsert", "Bolt")
    Rel(cw, minio, "bronze", "S3")
    Rel(fw, pg, "fiscal", "SQL")
    Rel(fw, minio, "planilhas", "S3")
    Rel(cw, gov, "ingesta", "HTTPS")
    Rel(fw, gov, "scraping", "HTTPS")
    Rel(gw, elixir, "alerts/v1", "outbox/HTTP")
```

**Legenda:** `Container` = processo/serviço; `ContainerDb` = data store; `Container_Boundary` = agrupamento.

**Notas:** o `gateway` fala com quase toda a malha de dados **em processo** (é um monólito modular). Os
workers Celery são o único plano assíncrono. `fiscal-worker` é "gordo" (Chromium+Tesseract) e isolado.

---

## 3. C4 Nível 3 — Componentes do Gateway

**Objetivo:** decompor o container `gateway` em seus componentes internos.

```mermaid
C4Component
    title Componentes — Gateway FastAPI

    Container(next, "Frontend", "Next.js", "")

    Container_Boundary(gw, "gateway") {
        Component(mw, "Middlewares", "Starlette", "JWTAuth · RateLimit · SecurityHeaders")
        Component(routers, "20 Routers", "APIRouter", "/api/v1/* por produto")
        Component(authc, "Auth", "jwt/password/users", "RS256 + PBKDF2 + repo de usuários")
        Component(contracts, "Contracts", "Pydantic", "DTOs versionados (fronteira de tipos)")
        Component(ledger, "Decision Ledger", "Merkle", "Trilha auditável imutável")
        Component(lgpd, "LGPD", "HMAC + AES-GCM", "Pseudonimização + crypto-shredding")
        Component(dom, "Pacotes de domínio", "Python", "scoring, fiscal, defensor, … (in-process)")
    }
    ContainerDb(pg, "PostgreSQL", "", "")
    ContainerDb(redis, "Redis", "", "")

    Rel(next, mw, "REST", "HTTP")
    Rel(mw, routers, "request autenticado")
    Rel(routers, authc, "login/token")
    Rel(routers, contracts, "valida DTOs")
    Rel(routers, dom, "delega (import)")
    Rel(routers, ledger, "add_entry")
    Rel(routers, lgpd, "cifra subject_token")
    Rel(mw, redis, "rate-limit")
    Rel(authc, pg, "tenant.users")
    Rel(ledger, pg, "ledger.entries (RLS)")
```

**Legenda:** `Component` = componente lógico dentro do container.

**Notas:** o *pipeline* de request é `Middlewares → Routers → (Contracts + Domínio + Ledger + LGPD)`.
Middlewares aplicados de fora para dentro: SecurityHeaders → JWTAuth → RateLimit.

---

## 4. Modelo de Dados (ER) — Schema PostgreSQL

**Objetivo:** o esquema relacional completo (de `scripts/bootstrap-db.sql` + `scripts/migrations/00{1..4}`).

```mermaid
erDiagram
    TENANTS ||--o{ USERS : possui
    TENANTS ||--o{ IDEMPOTENCY_KEYS : escopo
    TENANTS ||--o{ LEDGER_ENTRIES : escopo
    TENANTS ||--o{ LEDGER_ANCHORS : escopo
    TENANTS ||--o{ TRIAGE_JOB : escopo
    TRIAGE_JOB ||--o{ TRIAGE_ITEM : contém
    LEDGER_ENTRIES ||--o| TRIAGE_JOB : ancora
    NCM ||--o{ NCM_CATEGORIA : classifica
    CATEGORIA ||--o{ NCM_CATEGORIA : agrupa
    TPU_CLASSE ||--o{ INDICADOR : dimensiona
    TPU_ASSUNTO ||--o{ INDICADOR : dimensiona

    TENANTS {
        uuid id PK
        string slug UK
        string name
        string plan
        bool active
    }
    USERS {
        uuid id PK
        uuid tenant_id FK
        string email
        string password_hash "pbkdf2_sha256"
        string role "admin|analyst|viewer"
        bool active
    }
    IDEMPOTENCY_KEYS {
        uuid tenant_id PK
        string key PK
        jsonb response
    }
    LEDGER_ENTRIES {
        string request_id UK
        int entry_index
        string product
        uuid tenant_id FK
        string inputs_hash "sha256"
        string outputs_hash "sha256"
        jsonb sources
        string subject_token "AES-256-GCM"
        string leaf_hash
        string merkle_root
    }
    LEDGER_ANCHORS {
        serial id PK
        int anchor_at_index
        string merkle_root
        uuid tenant_id FK
    }
    INGEST_RUNS {
        string source
        string status
        int records_in
        int records_out
        string transform_version
    }
    ALERTS_OUTBOX {
        uuid alert_id PK
        string dedup_key
        jsonb envelope "alerts/v1"
        string status
        int attempts
    }
    NCM {
        string ncm_codigo PK
        string descricao
        daterange vigencia "EXCLUDE no-overlap"
    }
    NCM_MIGRACAO {
        string ncm_origem
        string ncm_destino
    }
    IPI_ALIQUOTA {
        string ncm_codigo
        numeric aliquota_ipi
    }
    ICMS_INTERNO {
        string uf
        string ncm_prefix
        numeric aliquota
        numeric fcp
    }
    ICMS_INTERESTADUAL {
        string uf_origem
        string uf_destino
        numeric aliquota
    }
    CATEGORIA { string id PK }
    NCM_CATEGORIA { string ncm_codigo FK
        string categoria_id FK }
    TRIAGE_JOB {
        uuid job_id PK
        uuid tenant_id FK
        string batch_merkle_root
        string ledger_request_id
    }
    TRIAGE_ITEM {
        uuid job_id FK
        int idx
        string suggested_ncm
        string decision_proof
    }
    TPU_CLASSE { string codigo PK
        string label }
    TPU_ASSUNTO { string codigo PK
        string ramo }
    INDICADOR {
        string tribunal PK
        string classe PK
        string assunto PK
        string periodo PK
        string fonte PK "DATAJUD|BLEND|ABJ"
        numeric congestionamento
        numeric duracao_mediana
    }
    ABJ_INDICADOR_RAW { string tribunal
        numeric taxa_congestionamento }
```

**Legenda:** `PK`/`FK`/`UK` = chaves; `||--o{` = um-para-muitos. Schemas: `tenant`, `ledger`, `ingest`,
`fiscal`, `jurimetria`, `public`.

**Notas:** tabelas com `tenant_id` estão sob **RLS FORCE** (tenant, ledger, fiscal.triage_*). As tabelas de
referência fiscal e jurimetria são globais (sem RLS). `NCM.vigencia` usa `daterange` com constraint `EXCLUDE`
(btree_gist) para impedir sobreposição temporal — versionamento temporal de alíquotas.

---

## 5. Fluxo de Dados — Pipeline Medalhão (bronze → silver → gold)

**Objetivo:** o caminho dos dados das 14+ fontes públicas até os produtos.

```mermaid
flowchart LR
    subgraph SRC["Fontes públicas (14+)"]
        datajud["DATAJUD"]
        receita["Receita"]
        pgfn["PGFN"]
        pncp["PNCP"]
        caged["CAGED"]
        siconfi["SICONFI"]
        ibge["IBGE"]
        snis["SNIS"]
        abj["ABJ"]
        bcb["BCB"]
        sefaz["SEFAZ/CONFAZ/TIPI"]
    end

    subgraph ING["Ingestão (Celery)"]
        cb["CircuitBreaker por fonte"]
        val["Validação Bronze (contrato Pydantic)"]
        lgpd["Pseudonimização (HMAC)"]
        trans["bronze→silver (quality + TPU)"]
        cb --> val --> lgpd --> trans
    end

    subgraph BRONZE["Bronze"]
        minio[("MinIO JSONL<br/>Hive-partitioned")]
        rediscache[("Redis cache<br/>receita:/pgfn:/pncp:/…")]
    end
    subgraph SILVER["Silver"]
        os[("OpenSearch<br/>datajud-silver-*")]
        neo[("Neo4j<br/>:Empresa-[:PARTE_EM]->:Processo")]
    end
    subgraph GOLD["Gold"]
        indicador[("Postgres<br/>jurimetria.indicador")]
        modelos[("MinIO gold<br/>traces PyMC / parquet")]
        fiscalref[("Postgres<br/>fiscal.ncm/icms/…")]
    end

    SRC --> cb
    trans -->|persist_silver| minio
    trans -->|persist_silver| os
    trans -->|persist_silver| neo
    trans --> rediscache
    os -->|jurimetria_aggregate| indicador
    abj --> indicador
    sefaz --> fiscalref

    subgraph PROD["Consumo pelos produtos"]
        legalscore["LegalScore<br/>(features)"]
        forecasting["Forecasting"]
        taxpredict["TaxPredict"]
        fiscaleng["FiscalEngine"]
        compliance["ComplianceRadar"]
    end
    rediscache --> legalscore & compliance
    neo --> legalscore
    indicador --> forecasting & taxpredict
    modelos --> taxpredict
    fiscalref --> fiscaleng
```

**Legenda:** cilindro = loja de dados; retângulo = etapa de processamento. As 3 camadas do "medalhão"
(bronze cru → silver tratado → gold agregado) estão explícitas.

**Notas:** `persist_silver` é o **sink DRY** que escreve nas 3 lojas com isolamento de falha por loja.
A pseudonimização LGPD (HMAC) ocorre **antes** de qualquer persistência. `jurimetria_aggregate` é a etapa
gold (lê OpenSearch + ABJ, escreve `jurimetria.indicador`).

---

## 6. Mapa Data Store → Consumidores

**Objetivo:** quem lê/escreve em cada loja (para decisões de escala e isolamento).

```mermaid
flowchart TB
    gw["Gateway"]
    cw["celery-worker"]
    fw["fiscal-worker"]
    sw["scoring worker"]

    pg[("PostgreSQL/PgBouncer")]
    neo[("Neo4j")]
    os[("OpenSearch")]
    redis[("Redis")]
    minio[("MinIO")]
    chroma[("ChromaDB")]
    ollama["Ollama"]

    gw -->|"auth · ledger (RLS) · fiscal ref · jurimetria"| pg
    gw -->|"grafo litigância"| neo
    gw -->|"idempotência · rate-limit · caches · send_task"| redis
    gw -->|"RAG search"| chroma
    gw -->|"embeddings · LLM"| ollama
    gw -->|"traces de modelo (taxpredict)"| minio

    cw -->|"jurimetria.indicador · ingest.runs"| pg
    cw -->|"upsert PARTE_EM"| neo
    cw -->|"bulk silver"| os
    cw -->|"bronze JSONL"| minio
    cw -->|"caches + broker"| redis

    fw -->|"fiscal.* (RLS triage)"| pg
    fw -->|"planilhas + bronze"| minio
    fw -->|"broker"| redis

    sw -->|"features cache · batch"| redis
    sw -->|"count_processos"| neo
```

**Legenda:** rótulo de aresta = o que trafega. Redis é o hub mais compartilhado (broker + cache + estado).

**Notas:** **Postgres é o único store transacional/RLS**; os demais são derivados/cache. Se um produto exigir
isolamento de recursos, o candidato natural a extrair primeiro é o **taxpredict** (PyMC, CPU-bound).

---

## 7. Topologia Celery — Filas, Tasks e Beat

**Objetivo:** o plano assíncrono — 3 apps Celery, filas e agendamentos.

```mermaid
flowchart TB
    broker[("Redis broker/backend")]

    subgraph APP_INGEST["app: services.ingest.celery_app"]
        direction TB
        q_daily{{"fila: daily"}}
        q_weekly{{"fila: weekly"}}
        q_monthly{{"fila: monthly"}}
        t_datajud["datajud.run_daily_ingest"]
        t_pncp["pncp.run_daily_ingest"]
        t_receita["receita.run_weekly_ingest"]
        t_pgfn["pgfn.run_weekly_ingest"]
        t_caged["caged.run_monthly_ingest"]
        t_siconfi["siconfi.run_monthly_ingest"]
        t_abj["abj.run_monthly_ingest"]
        t_agg["jurimetria_aggregate.run_aggregation"]
    end

    subgraph APP_FISCAL["app: services.fiscal.celery_app (beat próprio)"]
        direction TB
        q_fiscal{{"fila: fiscal"}}
        q_fingest{{"fila: fiscal_ingest"}}
        t_enrich["enrich_spreadsheet → chord"]
        t_chunk["classify_chunk × N"]
        t_final["finalize_enrichment"]
        t_tipi["rfb_tipi.run_ingest (mensal)"]
        t_sefaz["sefaz_scraper.run_ingest (semanal)"]
        t_confaz["confaz_discovery → confaz_ocr"]
    end

    subgraph APP_SCORING["app: services.scoring.celery_app"]
        q_scoring{{"fila: scoring"}}
        t_batch["run_batch_score (ThreadPool 20)"]
    end

    subgraph APP_TAX["app: services.taxpredict.celery_app"]
        q_tax{{"fila: taxpredict"}}
        t_recal["recalibrate_model (PyMC MCMC)"]
    end

    beat_i["celery-beat"] -.->|schedule| q_monthly
    beat_f["fiscal-beat"] -.->|"TIPI mensal · SEFAZ/CONFAZ semanal"| q_fingest

    gw["Gateway send_task"] --> broker
    broker --> q_daily & q_weekly & q_monthly & q_fiscal & q_scoring
    q_daily --> t_datajud & t_pncp
    q_weekly --> t_receita & t_pgfn
    q_monthly --> t_caged & t_siconfi & t_abj & t_agg
    q_fiscal --> t_enrich
    t_enrich --> t_chunk --> t_final
    q_fingest --> t_tipi & t_sefaz & t_confaz
    q_scoring --> t_batch
    q_tax --> t_recal
```

**Legenda:** `{{ }}` = fila; retângulo = task; seta tracejada = agendamento (Beat).

**Notas:** **4 apps Celery independentes**. Só `fiscal` e (por exemplo docstring) `taxpredict` definem
`beat_schedule`; o ingest geral é disparado externamente (Makefile/gateway). O `enrich_spreadsheet` usa
**chord** (fan-out horizontal); o batch de scoring usa **ThreadPool** (I/O-bound). Modelos pesados
(`recalibrate_model`) rodam **só via Beat**, nunca no caminho de request.

---
## 8. Arquitetura de Segurança — Autenticação & Isolamento Multi-Tenant

**Objetivo:** as camadas que garantem isolamento entre tenants (defesa em profundidade).

```mermaid
flowchart TB
    subgraph EDGE["Borda / App"]
        traefik["Traefik — TLS 1.3"]
        sec["SecurityHeadersMiddleware<br/>HSTS · X-Frame · nosniff"]
        jwtmw["JWTAuthMiddleware<br/>valida RS256 → state.tenant_id/role"]
        rl["RateLimitMiddleware<br/>por tenant (Redis INCR)"]
    end
    subgraph AUTHN["Autenticação"]
        tokenep["POST /auth/token"]
        authu["authenticate()<br/>PBKDF2-SHA256 compare_digest"]
        issue["issue_token()<br/>RS256 {sub,tenant_id,role}"]
    end
    subgraph DATA["Isolamento no dado"]
        pgb["PgBouncer<br/>pool_mode=transaction"]
        setlocal["SET LOCAL app.tenant_id<br/>(set_config is_local=true)"]
        rls["Postgres RLS FORCE<br/>current_setting('app.tenant_id')"]
        appuser["conexão como app_user<br/>(NOSUPERUSER)"]
    end

    traefik --> sec --> jwtmw --> rl --> routers["Routers"]
    routers -->|"_get_tenant()"| tenantctx["tenant_id (request.state)"]
    tenantctx --> setlocal
    tokenep --> authu --> issue
    routers --> pgb --> rls
    setlocal --> rls
    appuser --> rls
    rls -->|"fail-closed se GUC ausente"| deny["nega acesso cross-tenant"]
```

**Legenda:** cada caixa é uma camada de controle; o dado só é liberado quando **todas** concordam.

**Notas:** 3 camadas precisam funcionar juntas — `SET LOCAL` + PgBouncer `transaction` + RLS `FORCE` com
`app_user` (superusuário burla RLS). O CI tem job dedicado (`integration-tests`) provando o isolamento.
Rotas públicas (`/health`, `/auth/token`, `/docs`, JWKS) pulam o JWT.

---

## 9. Arquitetura de Conformidade — Decision Ledger + Crypto-Shredding (LGPD)

**Objetivo:** como a trilha imutável coexiste com o direito ao esquecimento.

```mermaid
flowchart LR
    req["Request de produto"]
    pii["PII (CNPJ/CPF)"]
    hash["hash_user_id()<br/>HMAC-SHA256"]
    enc["encrypt_for_ledger()<br/>AES-256-GCM por titular+tenant"]
    keystore[("Key Store / KMS<br/>chave por titular")]
    entry["add_entry()<br/>inputs_hash · outputs_hash · subject_token"]
    merkle["Merkle root<br/>(recomputada)"]
    anchors[("ledger.anchors<br/>checkpoint a cada 1024")]
    audit["audit_log<br/>log_ledger_write"]

    req --> pii --> hash --> enc
    enc <-->|chave| keystore
    enc -->|subject_token| entry
    req -->|dados técnicos| entry
    entry --> merkle --> anchors
    entry --> audit

    erase["erase_titular()"] -->|apaga chave| keystore
    erase -.->|"PII irrecuperável,<br/>prova Merkle intacta"| merkle
    verify["verify_integrity(proof)"] --> merkle
```

**Legenda:** setas cheias = fluxo de escrita; tracejadas = propriedade garantida.

**Notas:** o **crypto-shredding** é a decisão central: apagar a chave AES (`erase_titular`) torna a PII
irrecuperável **sem quebrar a prova Merkle** — resolve "imutabilidade × LGPD". Nenhuma PII em claro entra no
ledger (só hashes + `subject_token` cifrado). Custo atual: `add_entry` é O(N) por inserção (dívida QT-08 → MMR).

---

## 10. Arquitetura de Alertas — Transactional Outbox → Elixir/Oban

**Objetivo:** entrega confiável e idempotente de alertas (seam Python↔Elixir).

```mermaid
flowchart LR
    subgraph PY["Produtores (Python)"]
        comp["ComplianceRadar<br/>evaluate_municipio"]
        licita["LicitaWatch<br/>evaluate_licitacoes"]
    end
    env["AlertEnvelope<br/>(alerts/v1, uuid5 dedup)"]
    subgraph PUB["AlertPublisher (Protocol)"]
        outbox["OutboxAlertPublisher<br/>INSERT ON CONFLICT DO NOTHING"]
        http["HttpAlertPublisher<br/>POST /alertas/publicar"]
    end
    tbl[("public.alerts_outbox<br/>alert_id PK · status · attempts")]
    elixir["Elixir/Oban<br/>(consumidor — planejado)"]
    canais["Canais: webhook · email · slack · whatsapp"]

    comp --> env
    licita --> env
    env --> outbox --> tbl
    env --> http --> elixir
    elixir -->|"poll/lê outbox"| tbl
    elixir --> canais
    schema["schemas/alert.v1.json<br/>(fonte de verdade — validada no CI)"] -.->|valida| env
```

**Legenda:** `Protocol` com duas implementações (outbox transacional ou HTTP direto).

**Notas:** o **outbox** garante idempotência (dedup por `alert_id`/`dedup_key`, `ON CONFLICT DO NOTHING`) e
entrega at-least-once. O JSON Schema `alert.v1.json` é o **contrato cross-linguagem** validado no CI —
honrado pelo publisher Python e pelo consumidor Elixir.

---

## 11. Arquitetura de IA — RAG & Roteamento de LLM

**Objetivo:** a camada de IA compartilhada (`services/shared/ai`).

```mermaid
flowchart TB
    subgraph CONSUM["Consumidores"]
        peti["PetiBot<br/>assemble_petition"]
        def["Defensor<br/>run_agente"]
        tax["TaxPredict<br/>jurisprudência"]
        fiscal["FiscalEngine<br/>RagNcmSource"]
    end
    subgraph AI["services/shared/ai"]
        rag["RAGEngine<br/>upsert/search"]
        gen["generate_text()<br/>never raises"]
        router["LLMRouter<br/>(custo: local vs pago)"]
        cache["LLMMemoizer<br/>sha256 key, TTL 30d"]
    end
    chroma[("ChromaDB<br/>coleções: juridico,<br/>petibot_jurisprudencia,<br/>fiscal_ncm")]
    ollama["Ollama<br/>BGE-M3 (embed) + Llama3 (gen)"]
    openai["OpenAI<br/>(se LLM_PROVIDER=openai)"]
    redis[("Redis<br/>cache LLM")]

    peti --> rag
    def --> rag
    def --> gen
    tax --> rag
    fiscal --> rag
    rag -->|"embeddings"| ollama
    rag -->|"upsert/query"| chroma
    gen --> router
    router -->|"CLASSIFICATION/NER/EMBED"| ollama
    router -->|"GENERATION/REASONING"| openai
    gen --> cache --> redis
```

**Legenda:** `RAGEngine` e `generate_text` são as entradas; `LLMRouter`/`LLMMemoizer` são otimizações
(roteamento por custo e memoização) — hoje parcialmente stubs.

**Notas:** **degradação graciosa** é lei: `generate_text` **nunca lança** (retorna `None`), e `RAGEngine.search`
cai para `[]` se ChromaDB/Ollama estão fora. Embeddings usam **BGE-M3** local; geração usa Llama3 local por
padrão (OpenAI opcional). Só PetiBot e Defensor usam LLM de geração; os demais são estatísticos/determinísticos.

---
## 12. Produto — LegalScore PJ

**Objetivo:** rating de risco jurídico-financeiro de PJ (endpoint de referência P2).

```mermaid
flowchart LR
    ui["UI /legalscore"]
    r["router legalscore"]
    idem["idempotency (Redis 24h)"]
    fa["assemble_features"]
    eng["get_score_engine<br/>PythonScoreEngine (MLR/CNAE)"]
    lg["DecisionLedger.add_entry"]
    batch["run_batch_score (Celery)"]

    ui -->|"POST /score"| r
    r --> idem
    r --> fa
    fa -->|"receita:/pgfn: (Redis)"| redis[("Redis")]
    fa -->|"count_processos"| neo[("Neo4j")]
    fa --> eng
    eng --> lg
    lg --> pg[("Postgres ledger RLS")]
    ui -->|"POST /batch (até 1000)"| r --> batch --> redis
    r -->|"GET /audit/:id"| lg
    r -->|"GET /model-metrics"| val["validation (heurística)"]
```

**Endpoints:** `POST /score`, `POST /batch`, `GET /batch/:job`, `GET /company/:cnpj`, `GET /audit/:id`,
`GET /model-metrics`. **SLA:** p95 < 1.5s. **Nota:** score rotulado "heurística" até validação AUC/Brier (Fase 1d).

---

## 13. Produto — ContabilIA (auditoria contábil)

**Objetivo:** auditar DRE enviada via 8 cross-checks + testes estatísticos.

```mermaid
flowchart LR
    ui["UI /contabilia"]
    r["router contabilia"]
    parse["_parse_dre_csv"]
    eng["CrossCheckEngine.run_checks"]
    subgraph CHECKS["8 cross-checks"]
        cc1["CC01 headcount vs CAGED"]
        cc2["CC02 receita vs SICONFI"]
        cc5["CC05 Benford"]
        cc6["CC06 Z-score"]
        cc7["CC07 liquidez"]
        cc8["CC08 EBITDA"]
    end
    ben["analyze_benford"]
    zs["compute_zscore"]
    anom["AnomalyDetector<br/>(IsolationForest — não plugado)"]

    ui -->|"POST /audit/upload (CSV)"| r --> parse --> eng
    eng --> CHECKS
    cc5 --> ben
    cc6 --> zs
    eng --> findings["list~CrossCheckFinding~<br/>(severity: MEDIO/ALTO/CRITICO)"]
    findings --> ui
```

**Endpoints:** `POST /audit/upload`, `GET /audit/:report_id` (stub async Fase 3). **SLA:** p95 < 60s.
**Nota:** `public_data={}` hoje → CC01–CC04 pulados até integrar o feature store público. `AnomalyDetector`
existe mas não está ligado a nenhum router.

---

## 14. Produto — ComplianceRadar (monitoramento municipal)

**Objetivo:** avaliar indicadores municipais e gerar alertas.

```mermaid
flowchart LR
    ui["UI /compliance-radar"]
    r["router compliance"]
    redis[("Redis<br/>snis:/ibge:/siconfi:")]
    ing["ingest.tasks.ibge (live)"]
    mon["monitor.evaluate_municipio"]
    rules["ALERT_RULES<br/>arrecadacao_critica · saneamento_baixo"]
    env["AlertEnvelope[]"]

    ui -->|"GET /municipality/:ibge"| r --> redis
    ui -->|"POST /:ibge/evaluate"| r --> mon --> rules --> env
    ui -->|"GET /uf/:uf/municipios"| r --> ing
    env --> ui
```

**Endpoints:** `GET /municipalities`, `GET /municipality/:ibge`, `POST /:ibge/evaluate`, `GET /alerts`,
`GET /uf/:uf/municipios`, `GET /municipio/:cod/{populacao,perfil}`. **SLA:** 99% alertas. **Nota:** DATASUS
excluído (LGPD, PD-06). Alertas idempotentes via `uuid5(rule:ibge:ref)`.

---

## 15. Produto — TaxPredict (previsão bayesiana)

**Objetivo:** prever probabilidade de desfecho tributário (modelo hierárquico Bayesiano).

```mermaid
flowchart LR
    ui["UI /taxpredict"]
    r["router taxpredict"]
    feat["extract_features"]
    model["TaxPredictionModel<br/>(PyMC, trace carregado)"]
    rag["RAGEngine<br/>(jurisprudência)"]
    minio[("MinIO gold<br/>trace .nc")]
    recal["recalibrate_model<br/>(Celery Beat, MCMC)"]

    ui -->|"POST /predict"| r --> feat --> model
    model -->|"predict (posterior)"| resp["prob + IC"]
    r --> rag --> chroma[("ChromaDB")]
    model -.->|"load_from_minio (startup)"| minio
    recal -->|"fit + save"| minio
    ui -->|"GET /macro"| r -->|"IBGE/BCB live"| ext["ingest.tasks.ibge/bcb"]
    resp --> ui
```

**Endpoints:** `POST /predict`, `GET /macro`. **SLA:** p95 < 3s. **Nota:** MCMC (`fit`) roda **só via Beat**
(nunca por request); o request só faz `sample_posterior_predictive` sobre o trace carregado. Fallback nacional
`PRIOR_NACIONAL=0.30` se o modelo não estiver pronto.

---

## 16. Produto — FiscalEngine (NCM + ICMS/DIFAL)

**Objetivo:** triagem de NCM e resolução de ICMS interno/interestadual/DIFAL + enriquecimento de planilhas.

```mermaid
flowchart LR
    ui["UI (fiscal)"]
    r["router fiscal"]
    classify["triage.engine.classify (puro)"]
    exact["match_exact (TIPI)"]
    fuzzy["match_fuzzy (rapidfuzz)"]
    ragn["RagNcmSource (fallback)"]
    icms["resolve_icms<br/>Res.SF 22/89·13/12 · DIFAL EC 87/15"]
    repo["repository (Db*Source)"]
    pg[("Postgres fiscal.*")]
    enrich["enrich_spreadsheet (chord)"]
    anchor["build_batch_anchor (Merkle lote)"]
    minio[("MinIO planilhas")]

    ui -->|"POST /ncm/triage"| r --> classify
    classify --> exact & fuzzy
    fuzzy -->|"fraco"| ragn --> chroma[("ChromaDB fiscal_ncm")]
    classify --> icms
    classify --> repo --> pg
    ui -->|"POST /spreadsheet/enrich (202)"| r --> minio
    r -->|"send_task"| enrich --> anchor --> pg
```

**Endpoints:** `POST /ncm/triage`, `GET /ncm/:codigo`, `GET /icms/:ncm/:uf`, `POST /spreadsheet/enrich`,
`GET /jobs/:id`, `GET /audit/:id`. **SLA:** p95 < 2s (triagem). **Nota:** 100% determinístico (auditabilidade);
lote usa 1 entrada Ledger + prova O(log N) por item.

---

## 17. Produto — LicitaWatch (licitações PNCP)

**Objetivo:** detectar riscos de integridade em contratos públicos (PNCP).

```mermaid
flowchart LR
    ui["UI /licita-watch"]
    r["router licitawatch"]
    redis[("Redis pncp:")]
    silver["PncpContratoSilver"]
    mon["evaluate_licitacoes"]
    rules["LL01 concentração · LL02 dispensa<br/>LL03 único proponente · LL04 prazo"]
    env["AlertEnvelope[]"]

    ui -->|"GET /contratos/:orgao"| r --> redis
    ui -->|"POST /:orgao/evaluate"| r --> silver --> mon --> rules --> env --> ui
```

**Endpoints:** `GET /contratos/:cnpj_orgao`, `POST /orgao/:cnpj_orgao/evaluate`. **SLA:** diário.
**Nota:** indicadores agregados de contratos silver; alertas WEBHOOK idempotentes (`uuid5`).

---

## 18. Produto — PetiBot (geração de peças + RAG)

**Objetivo:** montar peça processual (seções mínimas por tipo + precedentes via RAG).

```mermaid
flowchart LR
    ui["UI /petibot"]
    r["router petibot"]
    asm["assemble_petition"]
    tmpl["_SECTION_TEMPLATES<br/>SECOES_MINIMAS_POR_TIPO"]
    rag["_lookup_precedentes → RAGEngine"]
    chroma[("ChromaDB<br/>petibot_jurisprudencia")]
    resp["PetiResponse (seções + precedentes)"]

    ui -->|"POST /assemble"| r --> asm
    asm --> tmpl
    asm --> rag --> chroma
    asm --> resp --> ui
```

**Endpoints:** `POST /assemble`. **SLA:** p95 < 10s. **Nota:** PetiBot em si **não usa LLM** (só templates + RAG);
o Defensor é quem adiciona LLM por cima. Degrada para `([],0)` se o RAG estiver fora.

---

## 19. Produto — ConciliaIA (viabilidade de acordo)

**Objetivo:** recomendar faixa de acordo a partir de prior histórico + sinais cross-service.

```mermaid
flowchart LR
    ui["UI /concilia"]
    r["router concilia"]
    rec["recommend_settlement<br/>prior por TipoAcao ±30%"]
    tax["_get_taxpredict (in-process)"]
    ls["_get_legalscore (Redis score:)"]
    resp["ConciliaResponse<br/>min/sugerido/max + fatores"]

    ui -->|"POST /recommend"| r --> rec
    rec -.->|"enriquece (degrada None)"| tax
    rec -.->|"enriquece (degrada None)"| ls
    rec --> resp --> ui
```

**Endpoints:** `POST /recommend`. **SLA:** p95 < 3s. **Nota:** chamadas cross-service são **in-process** e
graceful-degrade — se taxpredict/legalscore falham, segue com `None` e ajusta a recomendação (nunca 500).

---

## 20. Produto — Defensor (agente jurídico) ⭐

**Objetivo:** pipeline agêntico: classifica → consulta → RAG → redige (LLM) → protocola (gated).

```mermaid
flowchart TB
    ui["UI /defensor"]
    r["router defensor"]
    orch["run_agente (orquestrador)"]
    cls["_classificar"]
    hist["_consultar_historico"]
    peti["assemble_petition (RAG)"]
    red["_redigir_secoes (LLM→template)"]
    resp["_definir_responsavel<br/>(agente vs humano)"]
    prot["protocolar → get_driver"]
    subgraph DRIVERS["ProtocoloDriver (Strategy/Factory)"]
        sim["SimulacaoDriver (default)"]
        cg["ConsumidorGovDriver (Playwright)"]
        procon["ProconSPDriver (Playwright)"]
    end
    events["EventoAgente[] (timeline)"]

    ui -->|"POST /run"| r --> orch
    orch --> cls --> hist --> peti --> red --> resp
    orch --> events
    ui -->|"POST /protocolar"| r --> prot --> DRIVERS
    ui -->|"GET /reputacao/:termo"| r -->|"Redis consumidor:"| redis[("Redis")]
    resp --> ui
```

**Endpoints:** `POST /run`, `POST /protocolar`, `GET /reputacao/:termo`. **SLA:** p95 < 5s (DanoBot correlato).
**Nota:** handoff humano se `Canal.CONTENCIOSO` ou `valor ≥ R$ 50k`. Proveniência por seção (`llm/parcial/template`).
`get_driver` retorna `SimulacaoDriver` a menos que `PROTOCOLO_MODO=real` + credenciais (fail-safe).

---

## 21. Cluster Analítico — Serviços transversais (7)

**Objetivo:** serviços de leitura/estatística sobre o feature store gold (`jurimetria.indicador`) + grafo.

```mermaid
flowchart TB
    subgraph GW["Routers"]
        juri["/jurimetria"]
        kg["/knowledge-graph"]
        fc["/forecasting"]
        ew["/early-warning"]
        cp["/chamber-profiler"]
        so["/second-opinion"]
        opt["/settlement-optimizer"]
    end
    pg[("Postgres<br/>jurimetria.indicador")]
    neo[("Neo4j<br/>litigância")]
    lg["DecisionLedger"]

    juri -->|"get_indicators · market_intelligence"| pg
    juri --> lg
    fc -->|"forecast_series (tendência linear)"| pg
    ew -->|"detect_surges (z-score)"| pg
    cp -->|"build_profile (por tribunal)"| pg
    kg -->|"litigant_network → classify_relationship"| neo
    so -->|"synthesize_opinion (consenso)"| lg
    opt -->|"optimize_settlement (ZOPA/EV)"| lg
```

**Endpoints (por serviço):** jurimetria (`/indicators`, `/market-intelligence`, congestion/duration/litigiosity);
knowledge-graph (`/stats`, `/company/:cnpj/{processes,network}`); forecasting (`/demand`); early-warning
(`/evaluate`); chamber-profiler (`/tribunal/:t`); second-opinion (`/opinion`); settlement-optimizer (`/optimize`).
**Nota:** todos **heurísticos e agregados** (sem PII; CNPJ/tribunal apenas). jurimetria/second-opinion/
settlement-optimizer gravam Decision Ledger.

---
## 22. Frontend — Árvore de Rotas (App Router) → Produto → Endpoint

**Objetivo:** o mapa de navegação do app Next.js e a que backend cada rota chama.

```mermaid
flowchart TB
    root["/"] --> inicio["/inicio (dashboard)"]
    subgraph AUTH["grupo (auth)"]
        login["/login → /api/auth/login (BFF)"]
    end
    subgraph SHELL["grupo (shell) — ShellProvider"]
        inicio
        ent["/entidade/:cnpj"]
        ls["/legalscore"]
        ct["/contabilia"]
        cr["/compliance-radar"]
        tp["/taxpredict"]
        lw["/licita-watch"]
        pb["/petibot"]
        df["/defensor"]
        cc["/concilia"]
        db["/danobot (bloqueado)"]
        misc["/alertas · /auditoria · /conformidade · /tribuna · /configuracoes"]
    end
    gw["Gateway /api/v1"]

    ent -->|"GET /entidade/:cnpj"| gw
    ls -->|"/legalscore/*"| gw
    ct -->|"/contabilia/audit/upload"| gw
    cr -->|"/compliance/*"| gw
    tp -->|"/taxpredict/*"| gw
    lw -->|"/licitawatch/*"| gw
    pb -->|"/petibot/assemble"| gw
    df -->|"/defensor/*"| gw
    cc -->|"/concilia/recommend"| gw
    misc -.->|"demo/mock (sem API)"| mock["view-models locais"]
    login -->|"proxy"| gw
```

**Legenda:** rotas em `(shell)` compartilham Sidebar/Topbar + `ShellProvider`. Rotas `misc` são demo/mock.

**Notas:** as 4 apps `apps/{contabilia,legalscore,taxpredict,compliance-radar}` são **stubs vazios** —
todo o produto vive como rota dentro de `apps/platform` ("lentes"). `danobot` está bloqueado (501).

---

## 23. Frontend — Design System em Camadas & Fluxo de Dados React

**Objetivo:** as camadas do design system e como os dados fluem (Context + TanStack Query).

```mermaid
flowchart TB
    subgraph DS["Design System (@juridico)"]
        tokens["@juridico/tokens<br/>tipos-união · scoreToriskLevel"]
        prim["ui/primitives<br/>Button·Card·Table·Input·Tabs"]
        pat["ui/patterns<br/>ScoreGauge·MerklePanel·TrustHeader<br/>AgentLiveFeed·ProblemJsonError·RbacGate"]
        tokens --> prim --> pat
    end
    subgraph APP["apps/platform"]
        prov["Providers (QueryClient)"]
        shell["ShellProvider<br/>tenant · role · demoMode"]
        page["Página de produto"]
        apilib["lib/api/* (ApiError)"]
        prov --> shell --> page
        page --> apilib
        page --> pat
    end
    gw["Gateway"]
    apilib -->|"useMutation/useQuery<br/>credentials:include"| gw
    shell -.->|"authApi.me() (hidrata)"| gw
    page -->|"gate por role"| pat

    retrynote["retry: NÃO repete 429/501"]
    prov -.-> retrynote
```

**Legenda:** camadas unidirecionais `tokens → primitives → patterns → app`.

**Notas:** dois eixos globais de estado (`demoMode`, `role`) governam cada página (mock vs. real; RBAC).
DTOs TS espelham contratos Python à mão (`contract_version`). **Drift risk:** tokens Tailwind duplicados
entre `tokens/tailwind.preset.ts` e `apps/platform/tailwind.config.ts`.

---

## 24. Máquinas de Estado

**Objetivo:** os estados de vida dos principais artefatos runtime.

### 24.1. CircuitBreaker (ingest)

```mermaid
stateDiagram-v2
    [*] --> CLOSED
    CLOSED --> OPEN : failure_threshold (5) atingido
    OPEN --> HALF_OPEN : recovery_timeout (300s)
    HALF_OPEN --> CLOSED : record_success
    HALF_OPEN --> OPEN : record_failure
```

### 24.2. Job de batch (scoring/fiscal)

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> processing : worker pega
    processing --> processing : update_progress (a cada 100)
    processing --> done : completo
    processing --> failed : erro
    done --> [*] : TTL 24h
    failed --> [*] : TTL 24h
```

### 24.3. ProtocoloDriver / status (Defensor)

```mermaid
stateDiagram-v2
    [*] --> SIMULADO : modo simulacao (default)
    [*] --> AGUARDA_CREDENCIAIS : modo real sem creds
    AGUARDA_CREDENCIAIS --> ENVIADO : _submit_real ok
    AGUARDA_CREDENCIAIS --> FALHA : NotImplementedError/erro
    [*] --> CANAL_NAO_SUPORTADO : sem driver p/ canal
```

### 24.4. ScoreEngine — saúde e fallback (seam Rust)

```mermaid
stateDiagram-v2
    [*] --> Python : SCORING_BACKEND=python
    [*] --> Auto : SCORING_BACKEND=auto
    Auto --> RustFallback : rust.healthy()
    Auto --> Python : rust indisponível
    RustFallback --> Python : ScoringUnavailable em runtime
    [*] --> RustRequired : SCORING_BACKEND=rust
    RustRequired --> RustFallback : healthy
    RustRequired --> Erro : não saudável
```

**Legenda:** `[*]` = estado inicial/final; transições rotuladas com o gatilho.

**Notas:** todas essas máquinas de estado implementam **degradação graciosa** — nenhuma leva a 500 no caminho
feliz. O CircuitBreaker protege APIs gov; o fallback do engine protege a migração Rust.

---

## 25. Pipeline CI/CD (`.github/workflows/ci.yml`)

**Objetivo:** os 9 jobs de verificação (build/test/scan; sem deploy).

```mermaid
flowchart LR
    push["push main/claude·/feature· + PR"] --> ci{{"CI"}}
    ci --> unit["unit-tests<br/>pytest --cov-fail-under=80"]
    ci --> lint["lint (ruff)"]
    ci --> schema["schema-validation<br/>alert.v1.json"]
    ci --> dsec["docker-security<br/>sem porta DB · sem api.insecure"]
    ci --> anti["api-antipatterns<br/>sem truncar SHA · sem Merkle janelado"]
    ci --> integ["integration-tests<br/>RLS + SET LOCAL (app_user)"]
    ci --> fetest["frontend-tests (vitest)"]
    ci --> fbuild["frontend-build (tsc + next build)"]
    ci --> scan["container-scan (Trivy)"]
```

**Legenda:** cada nó é um job GitHub Actions (ubuntu-latest).

**Notas:** cobertura mínima **80%**. O job `integration-tests` sobe Postgres real, roda `migrate.py` duas vezes
(prova idempotência) e valida o **isolamento RLS** como `app_user`. **Não há job de deploy/CD** — só verificação.
`api-antipatterns` guarda decisões de segurança do código (sem truncar hash LGPD; sem Merkle janelado).

---

## 26. Grafo de Build & Dependências de Runtime (Compose)

**Objetivo:** a ordem de subida (build + `depends_on` + healthchecks).

```mermaid
flowchart TB
    subgraph BUILD["Build (Turbo — frontend)"]
        tok["@juridico/tokens"] --> uii["@juridico/ui"] --> plat["platform build"]
    end
    subgraph RUNTIME["Runtime (docker-compose depends_on)"]
        pg["postgres (healthy)"] --> pgb["pgbouncer"]
        pg --> mig["migrate (one-shot)"]
        mig -->|"service_completed_successfully"| gw["gateway"]
        pgb --> gw
        redis["redis (healthy)"] --> cw["celery-worker"]
        neo["neo4j (healthy)"] --> cw
        cw --> cb["celery-beat"]
        minio["minio (healthy)"] --> minit["minio-init (buckets)"]
        ollama["ollama"] --> oinit["ollama-init (pull models)"]
        traefik --> plat2["platform"]
        plat2 -->|"NEXT_PUBLIC_GATEWAY_URL"| gw
    end
```

**Legenda:** `-->` = dependência de build ou `depends_on`; anotações = condição de healthcheck.

**Notas:** `migrate` (one-shot, roda como owner) deve concluir **antes** do gateway. `minio-init` cria os buckets
`bronze/silver/gold/documents/backups`; `ollama-init` baixa `llama3:8b` + `bge-m3`. **Gap:** `fiscal-worker`
vive em `compose/fiscal.yml` (rede `external`) **fora** do include raiz — subir à parte.

---

> **Cobertura:** este documento traz **26 diagramas** (C4×3, dados×4, segurança×3, IA×1, produtos×10,
> frontend×2, estados×4, CI/build×2 — máquinas de estado contadas como um bloco de 4). Somado a
> `docs/arquitetura-uml.md` (18 diagramas), o repositório está mapeado em **44 diagramas** cobrindo todas as
> visões arquiteturais, todos os 9 produtos + transversais, e todas as fronteiras de linguagem.
