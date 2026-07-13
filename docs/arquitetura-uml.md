# Documentação UML — Plataforma Jurídico-Contábil (`juridico-platform`)

> Análise de arquitetura multi-linguagem para estudo aprofundado e planejamento de refatoramentos.
> Gerada a partir da inspeção estática de **270 arquivos Python**, **97 arquivos TypeScript/TSX** e de toda a
> configuração de infraestrutura (Docker Compose, CI, migrações SQL, contratos).

---

## 0. Sumário executivo

`juridico-platform` é uma plataforma **Docker-first** de IA aplicada ao direito e à contabilidade brasileira,
composta por **9 produtos** expostos sobre um **gateway FastAPI único** (monólito modular) e um **frontend
Next.js 14** (monorepo pnpm/Turbo). O backend é orquestrado por **Celery** para ingestão de dados públicos
(medalhão bronze→silver→gold) e trabalhos assíncronos, e persiste em uma malha poliglota de armazenamento
(PostgreSQL+RLS, Neo4j, OpenSearch, Redis, MinIO, ChromaDB, Ollama).

### 0.1. Nota sobre "multi-linguagem" (Python, Rust, TypeScript)

O prompt pede análise de **Python, Rust e TypeScript**. A realidade do repositório é:

| Linguagem | Situação no código | Evidência |
|---|---|---|
| **Python** | ✅ Presente — todo o backend (gateway, 20+ serviços, ingest, workers Celery). 270 arquivos `.py`. | `services/**` |
| **TypeScript** | ✅ Presente — todo o frontend (app Next.js + design system). 31 `.ts` + 66 `.tsx`. | `frontend/**` |
| **Rust** | ⚠️ **Ausente como código.** Existe apenas como **contrato/seam planejado**: o `Protocol` estrutural `ScoreEngine` foi desenhado para que, no futuro, um *crate* Rust via **PyO3** (`rust_scorer`) implemente exatamente a mesma interface e entre por **troca de configuração** (`SCORING_BACKEND=rust`). Hoje `RustScoreEngine` é um *adapter* que se auto-reporta como **não saudável**, e o `factory` cai para `PythonScoreEngine`. | `services/scoring/engine/engines.py:90`, `services/shared/contracts/scoring.py:82` |
| **Elixir** | ⚠️ Mencionado como **consumidor externo planejado** do contrato `alerts/v1` (fila Oban). Não há código Elixir no repositório; há o *publisher* Python (`HttpAlertPublisher`) que POSTa para um endpoint Elixir. | `services/shared/alerts/publishers.py`, `schemas/alert.v1.json` |

**Conclusão:** o sistema é hoje **Python + TypeScript**. As "fronteiras multi-linguagem" (Rust e Elixir)
são **seams arquiteturais** — `Protocol`s serializáveis e imutáveis — desenhados como pontos de extensão.
Essa é, na verdade, uma das decisões de arquitetura mais interessantes do projeto e é modelada
explicitamente nos diagramas de classes e componentes abaixo (estereótipo `«seam»`).

### 0.2. Como ler este documento

Cada diagrama traz: **Objetivo**, **Escopo**, o **código-fonte do diagrama** (Mermaid — renderiza nativamente
no GitHub), uma **Legenda** de notações/estereótipos e **Notas de design** (coesão, acoplamento, pontos de
refatoramento). Diagramas grandes foram quebrados em partes com referência cruzada.

---

## 1. Passo 1 — Mapeamento estrutural (top-down)

### 1.1. Mapa de diretórios × linguagens

```
juridico-platform/
├── services/                      [PYTHON] — backend (monólito modular + workers)
│   ├── gateway/                   FastAPI: main, middleware, auth/, routers/ (20 routers)
│   ├── shared/                    bibliotecas transversais
│   │   ├── contracts/             DTOs Pydantic versionados (fronteira de tipos)
│   │   ├── ledger/                Decision Ledger (Merkle tree)
│   │   ├── ai/                    LLM/RAG (generate, rag, router, cache)
│   │   ├── alerts/                publishers (outbox / HTTP→Elixir)
│   │   ├── storage/               clients MinIO / Neo4j / OpenSearch
│   │   ├── lgpd.py lgpd_crypto.py pseudonimização (HMAC) + crypto-shredding (AES-GCM)
│   │   ├── tenant_db.py db.py     isolamento de tenant (RLS + PgBouncer)
│   │   └── config.py redis_client.py audit_log.py tpu.py
│   ├── scoring/                   LegalScore — engine SEAMS + Celery
│   ├── fiscal/                    FiscalEngine — NCM/ICMS/DIFAL + ingestão fiscal
│   ├── ingest/                    pipeline medalhão + 14 coletores Celery
│   ├── taxpredict/                modelo Bayesiano hierárquico (PyMC)
│   ├── audit/                     ContabilIA — 8 cross-checks + Benford/Z-score
│   ├── defensor/                  agente jurídico (orquestrador + drivers de protocolo)
│   ├── petibot/ concilia/ compliance/ licitawatch/ jurimetria/
│   ├── knowledge_graph/ forecasting/ early_warning/ chamber_profiler/
│   ├── second_opinion/ settlement_optimizer/
│   └── ai-engine/                 (placeholder vazio — a IA real está em shared/ai)
├── frontend/                      [TYPESCRIPT] — monorepo pnpm + Turborepo
│   ├── apps/platform/             app Next.js 14 (App Router) — a única app real
│   │   ├── app/(auth)/ (shell)/   rotas de produto ("lentes")
│   │   ├── app/api/auth/          BFF: login/logout/me (proxy p/ gateway)
│   │   ├── lib/api/               client + módulos por produto (DTOs espelhando Python)
│   │   ├── components/ context/   Sidebar/Topbar + ShellProvider (demoMode, role)
│   ├── apps/{contabilia,legalscore,taxpredict,compliance-radar}/  (stubs vazios)
│   └── packages/
│       ├── ui/                    @juridico/ui — primitives + patterns + hooks
│       └── tokens/                @juridico/tokens — design tokens + tipos-união
├── docker/                        compose fragments + config + Dockerfiles
├── scripts/                       migrate.py + migrations/*.sql + bootstrap-db.sql
├── schemas/                       alert.v1.json (contrato cross-linguagem Python↔Elixir)
├── infra/                         terraform/ (placeholder) + scripts/
└── .github/workflows/ci.yml       pipeline CI (9 jobs)
```

### 1.2. Fronteiras de sistema e mecanismos de comunicação

```mermaid
flowchart LR
    subgraph browser["Navegador (usuário)"]
        UI["Next.js UI [TS]"]
    end
    subgraph edge["Borda"]
        TR["Traefik v3<br/>TLS 1.3"]
    end
    subgraph front["Frontend [TypeScript]"]
        NX["Next.js server<br/>app/api/auth (BFF)"]
    end
    subgraph back["Backend [Python]"]
        GW["Gateway FastAPI<br/>(monólito modular)"]
        CW["Celery workers<br/>(ingest + fiscal + scoring)"]
    end
    subgraph data["Malha de dados"]
        PG[("PostgreSQL 16<br/>+ PgBouncer / RLS")]
        NEO[("Neo4j 5")]
        OS[("OpenSearch")]
        RD[("Redis 7")]
        MIN[("MinIO S3")]
        CH[("ChromaDB")]
        OL[("Ollama<br/>Llama3 + BGE-M3")]
    end
    EXT["Elixir/Oban<br/>(consumidor de alertas — planejado)"]

    UI -->|"HTTPS product APIs<br/>credentials: include (cookie JWT)"| TR
    UI -->|"login/logout/me<br/>(same-origin)"| NX
    TR --> GW
    NX -->|"POST /api/v1/auth/token<br/>Bearer JWT"| GW
    GW -->|"import in-process<br/>(NÃO é HTTP)"| GW
    GW -->|"send_task (broker Redis)"| CW
    GW --> PG & RD & NEO & OS & MIN & CH & OL
    CW --> PG & RD & NEO & OS & MIN & CH & OL
    GW -->|"alerts/v1 (outbox / HTTP)"| EXT
    CW -->|"APIs gov: DATAJUD, Receita, PGFN,<br/>PNCP, IBGE, BCB, SEFAZ, CONFAZ"| INET["Internet<br/>(fontes públicas)"]
```

**Mecanismos de comunicação identificados:**

1. **Browser → Gateway (HTTP/REST direto)** — as chamadas de produto (`lib/api/*`) vão direto ao gateway
   com `credentials:'include'` (cookie `jwt` httpOnly). Erros seguem **RFC 9457 `application/problem+json`**.
2. **Browser → Next.js (BFF same-origin)** — apenas `login`/`logout`/`me` passam por *route handlers*
   Next (`app/api/auth/*`) que fazem proxy ao gateway e gerenciam o cookie httpOnly (mantém o JWT fora do JS).
3. **Gateway → serviços de produto (in-process import)** — **não há HTTP interno**; os routers importam os
   pacotes de domínio Python diretamente. É um **monólito modular**, não microserviços de rede.
4. **Gateway/serviços → workers (Celery via broker Redis)** — trabalhos assíncronos: `scoring.tasks.run_batch_score`,
   `fiscal.tasks.enrich_spreadsheet`, e todos os coletores de ingestão.
5. **Persistência poliglota** — Postgres (RLS por tenant), Neo4j (grafo de litigância), OpenSearch (busca full-text
   silver), Redis (cache/idempotência/rate-limit/broker), MinIO (bronze JSONL + traces de modelo), ChromaDB+Ollama (RAG).
6. **Seam Python↔Rust** (`ScoreEngine` via PyO3) e **seam Python↔Elixir** (`AlertPublisher` / `alerts/v1`) —
   fronteiras de linguagem por contrato serializável.

### 1.3. Dependências externas por linguagem (dos arquivos de gerência de pacotes)

**Python** (`pyproject.toml`, `services/*/requirements.txt`, CI): `fastapi`, `uvicorn`, `pydantic 2.9.2`,
`sqlalchemy`, `psycopg2-binary`, `PyJWT` (RS256), `cryptography`, `redis`, `celery` + `django_celery_beat`,
`scikit-learn` (IsolationForest/KMeans), `pymc` + `arviz` (Bayesiano), `rapidfuzz` (NCM fuzzy),
`openpyxl` (planilhas), `playwright` (scraping SEFAZ), `pdfplumber`/`pymupdf`/`pytesseract` (OCR CONFAZ),
`neo4j`, `opensearch-py`, `minio`, `chromadb`, `prometheus-fastapi-instrumentator`, `opentelemetry-*`. Lint `ruff`.

**TypeScript** (`frontend/**/package.json`): `next@14.2.18`, `react@18.3`, `@tanstack/react-query@5.62`,
`recharts`, `lucide-react`, `clsx`, `tailwind-merge`; design system `@juridico/ui` + `@juridico/tokens`
(via `workspace:*`); testes `vitest` + `@testing-library`. Gerência: `pnpm@9.12.3` + `turbo`.

**Infra:** Postgres 16, PgBouncer 1.20, Neo4j 5, OpenSearch 2.12, Redis 7, MinIO, ChromaDB, Ollama,
Traefik v3, Prometheus/Grafana/Loki/Promtail/Alertmanager, Flower.

---

## 2. Passo 2 — Resultado da análise estática (inventário condensado)

Contagem de entidades relevantes extraídas (nomes exatos preservados nos diagramas):

| Camada | Principais entidades | Arquivo(s) de origem |
|---|---|---|
| **Contratos/DTO (Python)** | `ScoreRequest`, `ScoreResult`, `RiskLevel`, `ScoreEngine`(Protocol); `NcmTriageRequest/Result`, `IcmsResolution`, `UF`, `FonteRegra`; `AlertEnvelope`, `AlertPublisher`(Protocol); `TaxPredictRequest/Response`; `PetiRequest/Section/Response`, `TipoAcao`; `ConciliaRequest/Fator/Response`; `DefensorRequest/Response`, `EventoAgente`, `Canal`; `ProtocoloRequest/Resultado` | `services/shared/contracts/*.py` |
| **Gateway** | `app`(FastAPI), `JWTAuthMiddleware`, `RateLimitMiddleware`, `SecurityHeadersMiddleware`; 20 `APIRouter`; `AuthenticatedUser` | `services/gateway/**` |
| **Segurança/LGPD** | `DecisionLedger`, `PostgresDecisionLedger`; `hash_user_id`, `pseudonymize_process_record`; `encrypt_for_ledger`/`erase_titular` (crypto-shredding); `tenant_transaction` | `services/shared/{ledger,lgpd,lgpd_crypto,tenant_db}` |
| **Scoring** | `PythonScoreEngine`, `RustScoreEngine`, `_FallbackEngine`, `get_score_engine`; `FeatureVector`, `assemble_features`; `ModelMetrics` | `services/scoring/**` |
| **Fiscal** | `classify`, `match_exact/fuzzy`, `resolve_icms`, `RagNcmSource`; `DbNcmSource/IcmsSource/CategorySource`; `build_batch_anchor`; tasks `enrich_spreadsheet`/`classify_chunk`/`finalize_enrichment` | `services/fiscal/**` |
| **Ingest** | `CircuitBreaker`, `persist_silver`, `add_linage`; `*Bronze`/`*Silver` (12 fontes); coletores Celery | `services/ingest/**` |
| **ContabilIA** | `CrossCheckEngine`, `CrossCheckFinding`, `analyze_benford`, `compute_zscore`, `AnomalyDetector` | `services/audit/**` |
| **Defensor (agente)** | `run_agente`, `ProtocoloDriver`(ABC), `SimulacaoDriver`, `ConsumidorGovDriver`, `ProconSPDriver`, `get_driver` | `services/defensor/**` |
| **IA/RAG** | `RAGEngine`, `generate_text`, `LLMRouter`, `LLMMemoizer` | `services/shared/ai/**` |
| **Frontend — design system** | tokens (`RiskLevel`, `FreshnessBand`, `scoreToriskLevel`…); primitives (`Button`, `Card`, `Table`…); patterns (`ScoreGauge`, `MerklePanel`, `TrustHeader`, `AgentLiveFeed`, `ProblemJsonError`, `RbacGate`…) | `frontend/packages/**` |
| **Frontend — app** | `ApiError`, `api` (client); módulos `legalscoreApi`, `contabiliaApi`…; `ShellProvider`/`useShell`; route handlers auth | `frontend/apps/platform/**` |

---

## 3. Passo 3 — Padrões arquiteturais detectados

| Padrão | Onde aparece | Observação |
|---|---|---|
| **API Gateway / Facade** | `services/gateway` | Um único FastAPI agrega 20 routers; roteia para pacotes de domínio por import. |
| **Monólito modular** | gateway ↔ serviços | Fronteiras lógicas fortes (contratos), mas deploy único; sem HTTP interno. |
| **Anti-Corruption Layer / Seam por `Protocol`** | `ScoreEngine`, `AlertPublisher`, `NcmSource`/`IcmsSource`, `RuleParser`, `SemanticNcmSource` | `Protocol`s estruturais serializáveis — pontos de troca de implementação (Rust, Elixir, DB, LLM). |
| **Strategy + Factory + Fallback (decorator)** | `get_score_engine`→`_FallbackEngine`; `get_driver`→drivers de protocolo; `get_alert_publisher` | Seleção por configuração + degradação graciosa. |
| **Repository / DAO** | `AuthenticatedUser`+`authenticate`; `DbNcmSource`; `queries.py` de vários serviços | Isola SQL/Cypher do núcleo puro. |
| **Medalhão (bronze→silver→gold)** | `services/ingest/pipeline` | `persist_silver` como sink DRY de 3 lojas. |
| **Circuit Breaker** | `services/ingest/pipeline/base.py` | Por fonte externa; CLOSED/OPEN/HALF_OPEN. |
| **Transactional Outbox** | `OutboxAlertPublisher` + `alerts_outbox` | Entrega de alertas idempotente (consumida por Elixir/Oban). |
| **Núcleo puro + casca de I/O** | quase todos os serviços | `engine.py`/`forecast.py`/`detect.py` puros; `queries.py`/`tasks.py` com I/O. |
| **Decision Ledger (Merkle + crypto-shredding)** | `ledger/merkle.py` + `lgpd_crypto.py` | Trilha auditável imutável; PII apagável sem quebrar a prova. |
| **BFF (Backend-for-Frontend)** | `frontend/app/api/auth/*` | Proxy same-origin que guarda o JWT em cookie httpOnly. |
| **Design System em camadas** | `tokens → ui/primitives → ui/patterns → app` | Tipos-união canônicos em `@juridico/tokens`. |
| **CQRS-lite / feature store** | `jurimetria.indicador` (gold) lido por forecasting/chamber/early_warning | Escrita por agregação Celery; leitura por vários produtos. |

---

## 4. Diagrama de Casos de Uso

**Objetivo:** mostrar quem usa o sistema e as funcionalidades de negócio principais, com relações `«include»`/`«extend»`.

**Escopo:** atores humanos e sistemas externos; os 9 produtos + funções transversais (auth, auditoria/ledger, alertas).

```mermaid
flowchart TB
    %% Atores
    analista(["👤 Analista jurídico/contábil"])
    admin(["👤 Admin do tenant"])
    auditor(["👤 Auditor / DPO"])
    gov{{"🌐 Fontes gov (DATAJUD, Receita,<br/>PGFN, PNCP, IBGE, BCB, SEFAZ)"}}
    elixir{{"🌐 Serviço de alertas (Elixir/Oban)"}}
    beat{{"⏱️ Celery Beat (scheduler)"}}

    subgraph SUT["Plataforma juridico-platform"]
        UC_login(("Autenticar / obter JWT"))
        UC_score(("Calcular LegalScore de PJ"))
        UC_batch(("Score em lote (até 1.000 CNPJs)"))
        UC_audit_c(("Auditar demonstrações contábeis"))
        UC_tax(("Prever desfecho tributário"))
        UC_fiscal(("Triagem NCM + ICMS/DIFAL"))
        UC_sheet(("Enriquecer planilha fiscal"))
        UC_comp(("Monitorar município / gerar alertas"))
        UC_licita(("Monitorar licitações (PNCP)"))
        UC_peti(("Gerar peça processual"))
        UC_defensor(("Executar agente Defensor"))
        UC_protocolar(("Protocolar em PROCON/Consumidor.gov"))
        UC_concilia(("Recomendar acordo"))
        UC_kg(("Consultar grafo de litigância"))
        UC_juri(("Consultar jurimetria / market-intel"))
        UC_ledger(("Verificar trilha auditável (Merkle)"))
        UC_erase(("Apagar titular (crypto-shredding)"))
        UC_rbac(("Gerir tenant / papéis (RBAC)"))
        UC_ingest(("Ingerir dados públicos"))
        UC_rag(("Recuperar jurisprudência (RAG)"))
        UC_llm(("Redigir texto (LLM)"))
    end

    analista --> UC_score & UC_audit_c & UC_tax & UC_fiscal & UC_sheet
    analista --> UC_comp & UC_licita & UC_peti & UC_defensor & UC_concilia
    analista --> UC_kg & UC_juri & UC_ledger
    admin --> UC_rbac
    auditor --> UC_ledger & UC_erase
    beat --> UC_ingest
    gov --> UC_ingest
    UC_defensor --> elixir
    UC_comp --> elixir
    UC_defensor -.->|"«include»"| UC_protocolar
    UC_ingest --> gov

    %% include / extend
    UC_score -.->|"«include»"| UC_login
    UC_fiscal -.->|"«include»"| UC_login
    UC_score -.->|"«include»"| UC_ledger
    UC_fiscal -.->|"«include»"| UC_ledger
    UC_batch -.->|"«extend»"| UC_score
    UC_sheet -.->|"«extend»"| UC_fiscal
    UC_peti -.->|"«include»"| UC_rag
    UC_defensor -.->|"«include»"| UC_peti
    UC_defensor -.->|"«include»"| UC_llm
    UC_concilia -.->|"«include»"| UC_tax
    UC_concilia -.->|"«extend»"| UC_score
    UC_erase -.->|"«extend»"| UC_ledger
    UC_score -.->|"«include»"| UC_ingest
```

**Legenda:** `(( ))` = caso de uso; `([ ])` = ator humano; `{{ }}` = ator/sistema externo; setas cheias = associação
ator↔caso; setas tracejadas rotuladas `«include»`/`«extend»` = dependências entre casos.

**Notas de design:**
- **`«include» UC_login`** reflete o `JWTAuthMiddleware`: todo caso (exceto rotas públicas) exige JWT válido.
- **`«include» UC_ledger`** só aparece nos produtos que gravam Decision Ledger (LegalScore, Fiscal, jurimetria,
  second-opinion, settlement-optimizer) — os demais são consultas puras.
- **DanoBot** foi omitido: seu endpoint responde `501` (bloqueado pelo DPO, PD-06, por depender de dados sensíveis
  de saúde do DATASUS). É um caso de uso **planejado, não habilitado** — vale registrar no backlog de conformidade.
- `UC_protocolar` só efetiva submissão real quando `PROTOCOLO_MODO=real` + credenciais; senão é **simulação**.

---

## 5. Diagrama de Pacotes

**Objetivo:** organização lógica do código e dependências direcionadas entre pacotes Python e módulos TypeScript.

**Escopo:** pacotes de backend (`services/*`), o núcleo transversal (`services/shared/*`) e os pacotes do frontend.

```mermaid
flowchart TB
    subgraph FE["Frontend [TypeScript]"]
        direction TB
        tokens["@juridico/tokens<br/>(design tokens + tipos-união)"]
        ui["@juridico/ui<br/>(primitives + patterns + hooks)"]
        platform["@juridico/platform<br/>(Next.js app + lib/api + BFF)"]
        ui --> tokens
        platform --> ui
        platform --> tokens
    end

    subgraph GW["services/gateway [Python]"]
        gw_main["main + middleware + auth"]
        gw_routers["routers/* (20)"]
        gw_main --> gw_routers
    end

    subgraph SH["services/shared [Python]"]
        contracts["contracts/* (DTOs Pydantic)"]
        ledger["ledger (Merkle)"]
        lgpd["lgpd + lgpd_crypto"]
        tdb["tenant_db + db + redis_client"]
        ai["ai (RAG/LLM)"]
        alerts["alerts (publishers)"]
        storage["storage (MinIO/Neo4j/OpenSearch)"]
        cfg["config + audit_log + tpu"]
    end

    subgraph PROD["services/* (produtos) [Python]"]
        scoring["scoring"]
        fiscal["fiscal"]
        ingest["ingest"]
        taxpredict["taxpredict"]
        audit["audit (ContabilIA)"]
        defensor["defensor"]
        petibot["petibot"]
        concilia["concilia"]
        others["compliance · licitawatch · jurimetria ·<br/>knowledge_graph · forecasting ·<br/>early_warning · chamber_profiler ·<br/>second_opinion · settlement_optimizer"]
    end

    %% dependências principais
    platform -. "HTTP /api/v1 (problem+json)" .-> gw_routers
    gw_routers --> contracts
    gw_routers --> ledger & lgpd & tdb
    gw_routers --> PROD

    scoring --> contracts
    scoring --> ingest
    scoring --> storage
    fiscal --> contracts
    fiscal --> ledger
    fiscal --> ai
    fiscal --> storage
    ingest --> contracts
    ingest --> storage
    ingest --> lgpd
    taxpredict --> contracts
    taxpredict --> ai
    taxpredict --> storage
    defensor --> petibot
    defensor --> ai
    defensor --> contracts
    petibot --> ai
    petibot --> contracts
    concilia --> contracts
    concilia --> taxpredict
    others --> contracts
    others --> ledger
    others --> storage
    alerts --> contracts

    PROD --> cfg
    SH --> cfg
```

**Legenda:** caixa = pacote; seta cheia = dependência de compilação/import (`import`); seta tracejada rotulada =
dependência de runtime por rede (HTTP). `contracts` é o **hub de tipos** — quase tudo depende dele, nada depende de ninguém a partir dele (dependência estável, alinhada ao *Stable Dependencies Principle*).

**Notas de design:**
- **`services/shared/contracts` é o núcleo estável** — imutável, `frozen`, `extra=forbid`. Excelente coesão de
  contrato. Ponto de atenção: há **acoplamento entre contratos** (`concilia` importa `TipoAcao` de `petibot`;
  `defensor` importa `PetiSection` de `petibot`; `protocolo` importa `Canal` de `defensor`). Cadeias assim
  dificultam versionar um contrato isoladamente — considerar um pacote `contracts/common` para enums compartilhados.
- **Placeholders vazios** que a estrutura sugere existir mas não têm código: `services/ai-engine`,
  `services/shared/{consensus,http_client,vector_store,db(pacote)}`. A funcionalidade implícita vive noutro lugar
  (RAG em `ai/rag`, consenso em `second_opinion`/`concilia`). Vale **remover ou preencher** para evitar confusão.
- **`scoring` importa `ingest`** (`scoring/features.py` → `ingest.pipeline.quality`): um produto depende do pipeline
  de dados. É pragmático, mas cria acoplamento produto→ingest; um pacote `shared/enrichment` reduziria isso.

---

## 6. Diagrama de Componentes

**Objetivo:** mapear componentes de software executáveis, suas interfaces de comunicação e as **fronteiras de linguagem** (seams).

**Escopo:** frontend, gateway, workers, seams Rust/Elixir e a malha de dados/IA.

```mermaid
flowchart TB
    subgraph FE["Frontend (Next.js) [TS]"]
        spa["SPA / App Router"]
        bff["BFF /api/auth"]
        apilib["lib/api client<br/>(problem+json)"]
        spa --> apilib
        spa --> bff
    end

    subgraph GWC["Gateway FastAPI [Python] — monólito modular"]
        mw["Middlewares<br/>JWT · RateLimit · SecurityHeaders"]
        routers["20 Routers<br/>/api/v1/*"]
        mw --> routers
        subgraph DOM["Pacotes de domínio (in-process)"]
            c_score["scoring (SEAMS)"]
            c_fiscal["fiscal"]
            c_tax["taxpredict"]
            c_audit["ContabilIA"]
            c_def["defensor (agente)"]
            c_peti["petibot"]
            c_other["compliance · concilia · licitawatch ·<br/>jurimetria · knowledge_graph · …"]
        end
        routers --> DOM
    end

    subgraph WK["Workers Celery [Python]"]
        w_ingest["ingest worker<br/>(daily/weekly/…)"]
        w_fiscal["fiscal worker<br/>(Playwright + Tesseract)"]
        w_score["scoring worker<br/>(batch, ThreadPool)"]
        beat["Celery Beat"]
    end

    subgraph SEAM["Fronteiras de linguagem (seams)"]
        rust["«seam» rust_scorer<br/>(PyO3 — planejado)<br/>Protocol ScoreEngine"]
        elixir["«seam» Alertas Elixir/Oban<br/>contrato alerts/v1"]
    end

    subgraph DATA["Malha de dados & IA"]
        pg[("PostgreSQL/PgBouncer<br/>RLS + ledger")]
        neo[("Neo4j<br/>grafo litigância")]
        os[("OpenSearch<br/>silver")]
        rd[("Redis<br/>cache/broker/idemp")]
        minio[("MinIO<br/>bronze/gold")]
        chroma[("ChromaDB")]
        ollama[("Ollama<br/>LLM + BGE-M3")]
    end

    gov{{"APIs governamentais"}}

    %% interfaces
    apilib -->|"HTTPS REST"| routers
    bff -->|"HTTPS"| routers
    routers -->|"send_task (AMQP/Redis)"| w_score
    c_fiscal -->|"send_task"| w_fiscal
    beat -->|"schedule"| w_ingest
    beat -->|"schedule"| w_fiscal

    c_score -.->|"PyO3 FFI (futuro)"| rust
    c_score -->|"score() Python (hoje)"| c_score
    c_other -->|"AlertEnvelope"| elixir

    routers --> pg & rd
    c_score --> rd & neo
    c_fiscal --> pg & minio
    c_tax --> minio & chroma & ollama
    c_def --> chroma & ollama & rd
    c_peti --> chroma & ollama
    c_other --> pg & neo & rd

    w_ingest -->|"HTTP"| gov
    w_ingest --> minio & os & neo & rd & pg
    w_fiscal -->|"scraping/OCR"| gov
    w_fiscal --> pg & minio
    w_score --> rd & neo
    elixir -->|"lê outbox"| pg
```

**Legenda:** retângulo = componente; cilindro = data store; `{{ }}` = sistema externo; `«seam»` = fronteira de
linguagem por contrato; seta cheia = chamada síncrona/import; seta tracejada = chamada por FFI/rede planejada;
rótulos de aresta = protocolo/interface.

**Notas de design:**
- **O gateway é um monólito modular**, não uma malha de microserviços. Vantagem: latência baixa (sem hop HTTP
  interno), transações simples. Custo: **não é possível escalar/deployar produtos independentemente** — todos sobem
  no mesmo processo `gateway`. Se um produto (ex.: taxpredict com PyMC) exigir isolamento de recursos, será preciso
  extrair para um serviço de rede — os `Protocol`s de contrato já facilitam esse recorte.
- **Dois seams de linguagem** bem desenhados: `ScoreEngine` (Rust/PyO3) e `AlertPublisher`/`alerts/v1` (Elixir).
  Ambos passam apenas dados serializáveis imutáveis — pré-requisito para cruzar FFI/rede com segurança.
- **Workers fiscais são "gordos"** (Chromium + Tesseract na imagem) e rodam em fila própria (`fiscal`, `fiscal_ingest`),
  separados do ingest geral — bom isolamento de dependências pesadas.
- **Ponto de atenção (segurança):** `compose/fiscal.yml` usa `juridico-net` como `external: true` e **não** é incluído
  pelo `docker-compose.yml` raiz — o worker fiscal precisa ser subido separadamente. Documentar ou consolidar.

---

## 7. Diagrama de Classes — Parte A: Contratos & Seams (fronteira de tipos)

**Objetivo:** o coração do sistema — os DTOs versionados e os `Protocol`s que definem as fronteiras (inclusive Rust/Elixir).

**Escopo:** `services/shared/contracts/*` + os *engines* que satisfazem os Protocols.

```mermaid
classDiagram
    direction LR

    class ScoreEngine {
        <<interface Protocol>>
        +str name
        +healthy() bool
        +score(ScoreRequest) ScoreResult
    }
    class ScoreRequest {
        <<dto · frozen>>
        +str cnpj
        +str cnae_2dig
        +dict features
    }
    class ScoreResult {
        <<dto · frozen>>
        +int score
        +RiskLevel risk_level
        +tuple confidence_interval
        +dict breakdown
        +str engine
        +str contract_version
    }
    class RiskLevel {
        <<enum>>
        BAIXO
        MODERADO
        ALTO
        CRITICO
    }
    class PythonScoreEngine {
        <<service>>
        +name = "python"
        +score(ScoreRequest) ScoreResult
    }
    class RustScoreEngine {
        <<adapter · seam PyO3>>
        +name = "rust"
        -_native rust_scorer
        +score(ScoreRequest) ScoreResult
    }
    class _FallbackEngine {
        <<decorator>>
        -primary ScoreEngine
        -secondary ScoreEngine
    }

    ScoreEngine <|.. PythonScoreEngine
    ScoreEngine <|.. RustScoreEngine
    ScoreEngine <|.. _FallbackEngine
    _FallbackEngine o--> ScoreEngine : primary/secondary
    PythonScoreEngine ..> ScoreRequest
    PythonScoreEngine ..> ScoreResult
    ScoreResult --> RiskLevel

    class AlertPublisher {
        <<interface Protocol>>
        +str name
        +publish(AlertEnvelope) PublishReceipt
    }
    class AlertEnvelope {
        <<dto · frozen · alerts/v1>>
        +str alert_id
        +str dedup_key
        +Severity severity
        +str subject_ref
        +list~Channel~ channels
    }
    class OutboxAlertPublisher {
        <<outbox>>
    }
    class HttpAlertPublisher {
        <<seam Elixir>>
    }
    AlertPublisher <|.. OutboxAlertPublisher
    AlertPublisher <|.. HttpAlertPublisher
    OutboxAlertPublisher ..> AlertEnvelope
    HttpAlertPublisher ..> AlertEnvelope

    class NcmTriageRequest {
        <<dto · frozen · fiscal/v1>>
        +str descricao
        +UF uf_origem
        +UF uf_destino
        +bool importado
    }
    class NcmTriageResult {
        <<dto · frozen>>
        +NcmCandidate suggested_ncm
        +IcmsResolution icms
        +str decision_proof
    }
    class IcmsResolution {
        <<value-object>>
        +float interna_efetiva_pct
        +float interestadual_pct
        +float difal_pct
        +str fundamento_legal
    }
    NcmTriageResult *--> IcmsResolution
    NcmTriageResult o--> NcmCandidate
```

**Legenda:** `«interface Protocol»` = `typing.Protocol` estrutural (não requer herança nominal); `«dto·frozen»` =
Pydantic imutável (`ConfigDict(frozen=True, extra="forbid")`); `<|..` = realização/implementação; `o-->` = agregação;
`*-->` = composição; `..>` = dependência (uso). Anotações `alerts/v1`/`fiscal/v1` = `contract_version`.

**Notas de design:**
- **`ScoreEngine` é o exemplo canônico de seam**: um `Protocol` estrutural + `runtime_checkable`. Um crate Rust não
  precisa importar Python — basta expor `name`, `healthy()`, `score()`. O campo `engine` no `ScoreResult` torna
  **auditável qual implementação** produziu o resultado (gravado no Decision Ledger). Excelente para migração segura.
- **`_FallbackEngine` (decorator)** encapsula a resiliência: tenta o primário, cai para o secundário em
  `ScoringUnavailable`. Bem desenhado — mas a nota no código alerta que um *segfault* real do Rust derruba o processo;
  o fallback cobre erro recuperável, não *panic* nativo (exige supervisor + health check).
- **Determinismo por contrato**: `NcmTriageRequest`→`classify`→`NcmTriageResult` é puro; a ancoragem no Ledger é etapa
  separada — separação limpa de "cálculo" vs. "auditoria".

---

## 8. Diagrama de Classes — Parte B: Auditoria, LGPD & Isolamento de Tenant

**Objetivo:** o subsistema de conformidade — Decision Ledger (Merkle), crypto-shredding e RLS por tenant.

**Escopo:** `services/shared/{ledger,lgpd,lgpd_crypto,tenant_db,audit_log}`.

```mermaid
classDiagram
    direction TB

    class DecisionLedger {
        <<domain-service · in-memory>>
        -list _entries
        -list _leaf_hashes
        +str merkle_root
        +add_entry(request_id, product, inputs, outputs, sources, subject_token) dict
        +get_proof(entry_id) dict
        +verify_integrity(entry_id, proof) bool
    }
    class PostgresDecisionLedger {
        <<domain-service · Postgres/RLS>>
        -str _tenant_id
        +add_entry(...) dict
        +get_proof(entry_id) dict
        +verify_integrity(entry_id, proof) bool
    }
    note for PostgresDecisionLedger "Serializa escritas por tenant<br/>com pg_advisory_xact_lock;<br/>checkpoint a cada 1024 (ledger.anchors)"

    class tenant_transaction {
        <<context-manager>>
        +BEGIN; set_config('app.tenant_id', tid, true); COMMIT
    }
    class lgpd {
        <<privacy-util>>
        +hash_user_id(id) hex64
        +pseudonymize_process_record(rec) dict
        +k_anonymize(records, qi, k)
    }
    class lgpd_crypto {
        <<privacy-service · AES-256-GCM>>
        +encrypt_for_ledger(pseudonym, tenant) token
        +decrypt_from_ledger(token, pseudonym, tenant) str
        +erase_titular(pseudonym, tenant) bool
    }
    class audit_log {
        <<observability>>
        +log_ledger_write(...)
        +log_pii_decrypt(...)
        +log_pii_erase(...)
    }

    DecisionLedger <|.. PostgresDecisionLedger : mesma assinatura (polimórfico por DATABASE_URL)
    PostgresDecisionLedger ..> tenant_transaction : usa (RLS)
    PostgresDecisionLedger ..> audit_log
    lgpd_crypto ..> audit_log
    lgpd ..> lgpd_crypto : pseudônimo → cifra
```

**Legenda:** `<|..` aqui indica **polimorfismo estrutural** (ambos os ledgers têm a mesma interface; o router escolhe a
implementação em runtime conforme `DATABASE_URL`). `note` = anotação de comportamento. `«...»` = estereótipo de camada.

**Notas de design:**
- **Crypto-shredding** é a decisão de conformidade mais elegante: o `subject_token` no ledger é PII cifrada
  (AES-256-GCM por titular+tenant). Apagar a chave (`erase_titular`) torna a PII irrecuperável **sem quebrar a prova
  de integridade Merkle** — resolve o conflito entre "trilha imutável" e "direito ao esquecimento (LGPD)".
- **Isolamento de tenant** depende de 3 camadas que precisam funcionar juntas: `SET LOCAL app.tenant_id` (via
  `set_config(..., is_local=true)`), pool `transaction` do PgBouncer, e RLS `FORCE` no Postgres com a app conectando
  como `app_user` (não-superusuário). O CI tem um job dedicado provando isso (`integration-tests`).
- **Ponto de atenção (escala):** `PostgresDecisionLedger.add_entry` é **O(N)** por inserção (relê todos os `leaf_hashes`
  do tenant para recomputar a raiz). Documentado como dívida técnica (QT-08): migrar para MMR (Merkle Mountain Range)
  para O(log N). O `advisory_xact_lock` serializa escritas por tenant — throughput de escrita limitado por tenant.

---

## 9. Diagrama de Classes — Parte C: Scoring (SEAMS) & Enriquecimento de Features

**Objetivo:** detalhar a montagem de features (a partir das lojas de ingestão) e o cálculo do score.

**Escopo:** `services/scoring/*`.

```mermaid
classDiagram
    direction LR

    class FeatureVector {
        <<value-object>>
        +str cnpj
        +dict features
        +str cnae_2dig
        +list sources_used
        +list sources_missing
        +bool is_partial
    }
    class assemble_features {
        <<function>>
        +assemble_features(cnpj, redis) FeatureVector
        -_fetch_pgfn(cnpj, redis)
        -_fetch_receita(cnpj, redis)
        -_fetch_datajud(cnpj)
    }
    class PythonScoreEngine {
        <<service>>
        +score(ScoreRequest) ScoreResult
    }
    class ModelMetrics {
        <<value-object>>
        +str model_type
        +float auc
        +float brier_score
        +str validation_status
    }
    class run_batch_score {
        <<celery-task>>
        +run_batch_score(job_id, cnpjs) dict
        -ThreadPoolExecutor(20)
    }
    class idempotency {
        <<redis-store>>
        +create_batch_job(...)
        +get_batch_status(...)
        +get_idempotency_result(...)
    }

    assemble_features ..> FeatureVector : cria
    assemble_features ..> neo4j_client : count_processos_por_cnpj
    assemble_features ..> quality : bronze→silver
    run_batch_score ..> assemble_features
    run_batch_score ..> PythonScoreEngine
    run_batch_score ..> idempotency
    PythonScoreEngine ..> ModelMetrics : validação (heurística)
```

**Legenda:** `«function»` = módulo de funções puras; `«celery-task»` = tarefa assíncrona; `«redis-store»` = estado em Redis.

**Notas de design:**
- **Degradação parcial explícita:** se uma fonte (PGFN/Receita/DATAJUD) está ausente no cache, a feature recebe `0.0`
  e `is_partial=True`, com `sources_missing` propagado ao *disclaimer* da resposta. O usuário sabe que o score é parcial.
- **Batch usa `ThreadPoolExecutor(20)`**, não Celery-fan-out, porque as tarefas são I/O-bound (gets no Redis) — pragmático
  para o SLA de 1k CNPJs < 30s. Contrasta com o fiscal, que usa *chord* Celery (CPU/IO distribuído entre réplicas).
- **Score é rotulado "heurística"** (`ModelMetrics.validation_status = "pending"`, sem AUC/Brier) — honestidade de produto;
  a validação formal é Fase 1d. Bom para conformidade (não vende como preditivo validado).

---

## 10. Diagrama de Classes — Parte D: Defensor (camada agêntica) & Drivers de Protocolo

**Objetivo:** o serviço mais rico — orquestração agêntica + Strategy/Factory de drivers de protocolo (com scaffolding Playwright).

**Escopo:** `services/defensor/*` + contratos `defensor`/`protocolo`.

```mermaid
classDiagram
    direction TB

    class run_agente {
        <<orchestrator>>
        +run_agente(DefensorRequest) DefensorResponse
        -_classificar()
        -_consultar_historico()
        -_definir_responsavel()
        -_redigir_secoes()
    }
    class ProtocoloDriver {
        <<abstract>>
        +str canal
        +submit(ProtocoloRequest)* ProtocoloResultado
    }
    class SimulacaoDriver {
        +canal = "*"
    }
    class _PlaywrightPortalDriver {
        <<abstract>>
        +str portal_url
        -_submit_real()
        -_credenciais()
    }
    class ConsumidorGovDriver
    class ProconSPDriver
    class get_driver {
        <<factory>>
        +get_driver(canal, modo) ProtocoloDriver
    }
    class RAGEngine {
        <<vector-store>>
        +search(query, n) list
    }
    class generate_text {
        <<llm-gateway>>
        +generate_text(prompt, system) str
    }
    class assemble_petition {
        <<function>>
        +assemble_petition(PetiRequest) PetiResponse
    }

    ProtocoloDriver <|-- SimulacaoDriver
    ProtocoloDriver <|-- _PlaywrightPortalDriver
    _PlaywrightPortalDriver <|-- ConsumidorGovDriver
    _PlaywrightPortalDriver <|-- ProconSPDriver
    get_driver ..> ProtocoloDriver : instancia
    run_agente ..> assemble_petition : monta seções + RAG
    run_agente ..> generate_text : redige (fallback template)
    assemble_petition ..> RAGEngine : precedentes
    run_agente ..> get_driver : protocolar
```

**Legenda:** `<|--` = herança (generalização); `«abstract»` = ABC (`ProtocoloDriver` tem `@abstractmethod submit`);
`«orchestrator»` = coordena o pipeline; `«llm-gateway»`/`«vector-store»` = camada de IA compartilhada.

**Notas de design:**
- **Strategy + Factory + Template Method**: `ProtocoloDriver` (ABC) → `SimulacaoDriver` (default seguro) e
  `_PlaywrightPortalDriver` (Template Method: `submit` gera nº simulado, `_submit_real` é o gancho). `get_driver`
  devolve `SimulacaoDriver` a menos que `modo="real"` **e** exista driver real — *fail-safe* por padrão.
- **Degradação em cascata no `_redigir_secoes`**: cada seção tenta LLM; a primeira falha de LLM comuta todo o resto
  para template (`via ∈ {llm, parcial, template}`), com proveniência registrada por seção. Ótimo para transparência
  ("isto foi gerado por IA / parcial / template").
- **`_submit_real` ainda é scaffolding** (`NotImplementedError`→status `FALHA`). O agente é production-ready para
  simulação/handoff; a submissão real em portais é trabalho futuro gated por credenciais.
- **Regra de handoff humano**: `Canal.CONTENCIOSO` ou `valor ≥ R$ 50.000` → responsável humano. Boa fronteira
  agente↔humano codificada como política.

---

## 11. Diagrama de Classes — Parte E: ContabilIA (cross-checks) & Ingest (medalhão)

**Objetivo:** o motor de auditoria contábil e a infraestrutura de pipeline com circuit breaker.

**Escopo:** `services/audit/*` + `services/ingest/pipeline/*`.

```mermaid
classDiagram
    direction LR

    class CrossCheckEngine {
        <<service>>
        +run_checks(financials, public_data) list~CrossCheckFinding~
        -_cc01_headcount()
        -_cc05_benford()
        -_cc06_zscore()
    }
    class CrossCheckFinding {
        <<value-object>>
        +str rule
        +str severity
        +str description
        +dict detail
    }
    class analyze_benford {
        <<function>>
        +analyze_benford(values) BenfordResult
    }
    class compute_zscore {
        <<function>>
        +compute_zscore(values) ZScoreResult
    }
    class AnomalyDetector {
        <<ml · não-integrado>>
        +fit(X) self
        +detect(features) dict
    }

    class CircuitBreaker {
        <<resilience>>
        +CircuitState state
        +record_success()
        +record_failure()
        +is_open() bool
    }
    class persist_silver {
        <<sink>>
        +persist_silver(source, date, bronze, silver, graph_writer) dict
    }
    class CircuitState {
        <<enum>>
        CLOSED
        OPEN
        HALF_OPEN
    }

    CrossCheckEngine *--> CrossCheckFinding : produz
    CrossCheckEngine ..> analyze_benford
    CrossCheckEngine ..> compute_zscore
    CircuitBreaker --> CircuitState
    persist_silver ..> minio_client : bronze JSONL
    persist_silver ..> opensearch_client : silver bulk
    persist_silver ..> neo4j_client : graph_writer (DATAJUD)
```

**Legenda:** `list~CrossCheckFinding~` = retorno tipado; `«ml·não-integrado»` = componente disponível mas ainda não
plugado num router; `«sink»` = escritor DRY multi-loja.

**Notas de design:**
- **8 cross-checks (CC01–CC08)** cruzam a DRE enviada com dados públicos (CAGED, SICONFI, PNCP) + testes estatísticos
  (Benford CC05, Z-score CC06, liquidez CC07, EBITDA CC08). Hoje `public_data={}` no router, então CC01–CC04 são pulados —
  a integração com o feature store público é o próximo passo.
- **`AnomalyDetector` (IsolationForest + KMeans)** existe e é treinável, mas **não está plugado** em nenhum router —
  componente órfão. Decidir: integrar (CC estatístico ML) ou remover.
- **`persist_silver` é um bom ponto DRY**: um único sink escreve nas 3 lojas (MinIO/OpenSearch/Neo4j) com isolamento
  de falha por loja. `CircuitBreaker` por fonte evita martelar APIs governamentais instáveis.

---

## 12. Diagrama de Classes — Parte F: Frontend (Design System + Camada de API)

**Objetivo:** as camadas do frontend TypeScript e como os tipos espelham os contratos Python.

**Escopo:** `frontend/packages/*` + `frontend/apps/platform/lib/api/*` + contexto.

```mermaid
classDiagram
    direction TB

    class ApiError {
        <<error>>
        +number status
        +ProblemJson problem
    }
    class api {
        <<http-client>>
        +get(path)
        +post(path, body)
        +postForm(path, form)
    }
    class LegalScoreResult {
        <<ts-dto · espelha ScoreResponse>>
        +number score
        +string risk_level
        +number[] confidence_interval
        +string engine
        +string leaf_hash
        +string merkle_root
    }
    class legalscoreApi {
        <<api-module>>
        +score(cnpj)
        +batchScore(cnpjs)
        +audit(requestId)
    }
    class ShellProvider {
        <<react-context>>
        +tenant
        +RbacRole role
        +boolean demoMode
    }
    class RbacGate {
        <<pattern>>
        +role
        +requires
    }
    class MerklePanel {
        <<pattern>>
        +requestId
        +merkleRoot
        +MerkleProof[] proof
    }
    class tokens {
        <<design-tokens>>
        +RiskLevel
        +FreshnessBand
        +scoreToriskLevel(score)
    }

    api ..> ApiError : lança (problem+json)
    legalscoreApi ..> api
    legalscoreApi ..> LegalScoreResult : retorna
    ShellProvider ..> tokens : RbacRole
    RbacGate ..> ShellProvider : lê role
    MerklePanel ..> tokens
    LegalScoreResult ..> tokens : RiskLevel (união)
```

**Legenda:** `«ts-dto·espelha X»` = interface TypeScript **escrita à mão** que espelha um contrato Pydantic (não há
code-gen — sincronização manual via `contract_version`); `«pattern»`/`«design-tokens»` = camadas do design system.

**Notas de design:**
- **Espelhamento de contrato sem code-gen**: `LegalScoreResult` (TS) reflete `ScoreResponse` (Python), inclusive o campo
  `engine: 'python' | 'rust'` — a fronteira Rust "vaza" até o tipo do frontend. É o **contrato cross-linguagem mais
  visível** do sistema. Risco: *drift* silencioso; mitigado por `contract_version` e testes de contrato no CI, mas um
  gerador (openapi-typescript a partir do `/openapi.json` do gateway) eliminaria a duplicação manual.
- **Camadas do design system** (`tokens → primitives → patterns → app`) são limpas e unidirecionais. **Ponto de atenção:**
  os valores de cor/fonte estão **duplicados** entre `packages/tokens/tailwind.preset.ts` e
  `apps/platform/tailwind.config.ts` (a app não importa o preset) — risco de *drift* visual.
- **Dois eixos globais de estado** (`demoMode` e `role` no `ShellProvider`) governam quase toda página — central para
  entender a UI: cada página escolhe entre view-model mock (demo) e query real (gateway), e gateia ações por RBAC.

---

## 13. Diagrama de Sequência — Fluxo 1: Autenticação (login → JWT → cookie)

**Objetivo:** o fluxo BFF de autenticação e emissão do JWT RS256.

**Escopo:** página de login (TS) → route handler Next (BFF) → gateway `auth` → Postgres.

```mermaid
sequenceDiagram
    actor U as Usuário
    participant L as Login Page (Next)
    participant BFF as /api/auth/login (Next route)
    participant GW as Gateway /auth/token
    participant AU as auth.users.authenticate
    participant DB as Postgres (tenant.users)
    participant JWT as auth.jwt.issue_token

    U->>L: preenche email/senha/tenant
    L->>BFF: POST (JSON ou form)
    Note over BFF: mapeia email→username, tenant→tenant_slug
    BFF->>GW: POST /api/v1/auth/token {username,password,tenant_slug}
    GW->>AU: authenticate(email, password, tenant_slug)
    AU->>DB: SELECT join tenant.users ⨝ tenant.tenants (ativos)
    DB-->>AU: linha (password_hash, role, tenant_id)
    Note over AU: verify_password (PBKDF2-SHA256, compare_digest)
    alt credenciais válidas
        AU-->>GW: AuthenticatedUser
        GW->>JWT: issue_token(user_id, tenant_id, role)
        JWT-->>GW: JWT RS256 {sub,tenant_id,role,exp,iss}
        GW-->>BFF: 200 {access_token} (+ Set-Cookie?)
        Note over BFF: seta cookie httpOnly `jwt` (sameSite strict, 24h)
        BFF-->>U: 303 → /inicio (ou {ok:true})
    else inválidas
        AU-->>GW: None
        GW-->>BFF: 401 problem+json
        BFF-->>U: /login?erro=1
    end
```

**Legenda:** `alt/else` = fluxo alternativo; `Note` = nota de processamento; `-->>` = retorno; `->>` = chamada síncrona.

**Notas de design:**
- **BFF mantém o JWT fora do JavaScript** (cookie httpOnly) — mitiga XSS. As chamadas de produto reusam esse cookie
  via `credentials:'include'`.
- **Falha de banco → 503** (produção) via `AuthBackendError`, distinguindo "infra fora" de "credenciais inválidas (401)".
  Em dev/test há usuário-fallback e chaves RS256 efêmeras (o gateway **falha fechado** em produção se as chaves faltarem).
- **`tenant.users`/`tenant.tenants` NÃO estão sob RLS** (é o ponto de entrada pré-tenant) — usam engine não-tenant.

---

## 14. Diagrama de Sequência — Fluxo 2: LegalScore (endpoint de referência P2)

**Objetivo:** o fluxo canônico com idempotência, feature assembly, engine SEAMS e Decision Ledger.

**Escopo:** gateway `legalscore` → scoring → Redis/Neo4j → ledger.

```mermaid
sequenceDiagram
    actor FE as Frontend
    participant MW as Middlewares (JWT+RateLimit)
    participant R as router legalscore.score_company
    participant RD as Redis
    participant FA as assemble_features
    participant NEO as Neo4j
    participant EN as get_score_engine → PythonScoreEngine
    participant LG as DecisionLedger / PostgresDecisionLedger
    participant CR as lgpd_crypto

    FE->>MW: POST /api/v1/legalscore/score (Bearer JWT, Idempotency-Key)
    Note over MW: valida JWT RS256 → tenant_id/role · INCR ratelimit por tenant
    MW->>R: request autenticado
    opt Idempotency-Key presente
        R->>RD: get_idempotency_result(tenant, key)
        RD-->>R: cache hit? → retorna ScoreResponse
    end
    R->>FA: assemble_features(cnpj, redis)
    FA->>RD: get pgfn:{cnpj}, receita:{cnpj}
    FA->>NEO: count_processos_por_cnpj(cnpj)
    FA-->>R: FeatureVector (is_partial?)
    R->>EN: score(ScoreRequest{cnpj,cnae_2dig,features})
    Note over EN: MLR por CNAE — intercept + Σ coef·feature · IC = ±1.96σ
    EN-->>R: ScoreResult {score, risk_level, engine="python"}
    R->>CR: encrypt_for_ledger(hash_user_id(cnpj), tenant)
    CR-->>R: subject_token (AES-256-GCM)
    R->>LG: add_entry(request_id, "legalscore", inputs_hash, outputs_hash, subject_token)
    Note over LG: recomputa raiz Merkle · log_ledger_write (audit)
    LG-->>R: entry {leaf_hash, merkle_root}
    opt Idempotency-Key presente
        R->>RD: set_idempotency_result (TTL 24h)
    end
    R-->>FE: 200 ScoreResponse (disclaimer heurística)
```

**Legenda:** `opt` = trecho opcional; `Note over` = processamento interno.

**Notas de design:**
- **Este router é o template P2** replicado pelos demais: JWT + rate-limit + idempotência + problem+json + OTel span +
  Decision Ledger. Alta consistência arquitetural.
- **PII nunca entra no ledger em claro**: só `inputs_hash`/`outputs_hash` (SHA-256) + `subject_token` (AES-GCM). O CNPJ é
  parcialmente mascarado em spans/logs (`cnpj[:6]+"****"`).
- **Escolha de ledger em runtime**: `PostgresDecisionLedger(tenant)` se `DATABASE_URL` setado; senão singleton em memória
  (dev/test). Mesma interface — polimorfismo estrutural.

---

## 15. Diagrama de Sequência — Fluxo 3: Enriquecimento de planilha fiscal (chord Celery + Merkle de lote)

**Objetivo:** o fluxo assíncrono mais elaborado — upload → fan-out → ancoragem Merkle de lote → persistência RLS.

**Escopo:** gateway `fiscal` → MinIO → chord Celery (`classify_chunk` × N → `finalize_enrichment`) → ledger + Postgres.

```mermaid
sequenceDiagram
    actor FE as Frontend
    participant R as router fiscal.spreadsheet.enrich
    participant MIN as MinIO (documents)
    participant BRK as Celery broker (Redis)
    participant EW as enrich_spreadsheet (worker)
    participant CC as classify_chunk × N (group)
    participant CO as classify_one → classify()
    participant DB as Postgres (fiscal.ncm/icms_interno)
    participant FIN as finalize_enrichment (chord callback)
    participant AN as build_batch_anchor
    participant LG as PostgresDecisionLedger

    FE->>R: POST /ncm/triage/spreadsheet (xlsx, uf_origem)
    R->>MIN: upload_spreadsheet(key, bytes)
    R->>BRK: send_task enrich_spreadsheet(job_id, tenant, key)
    R-->>FE: 202 SpreadsheetJobResponse {job_id, status_url}
    BRK->>EW: dispatch
    EW->>MIN: download_spreadsheet(key)
    Note over EW: load_items → chunks de 500 → chord(group(classify_chunk))(finalize)
    EW->>CC: group classify_chunk.s(chunk, uf)
    loop cada linha do chunk
        CC->>CO: classify_one(NcmTriageRequest)
        CO->>DB: DbNcmSource/DbIcmsSource (match_exact/fuzzy + resolve_icms)
        DB-->>CO: NCM + ICMS/DIFAL
        CO-->>CC: NcmTriageResult
    end
    CC-->>FIN: chunk_results (chord aguarda todos)
    FIN->>AN: build_batch_anchor(results)
    AN-->>FIN: merkle_root + leaf_hashes
    FIN->>LG: add_entry(request_id=job_id, product=fiscal, outputs=batch_merkle_root)
    Note over FIN,LG: UMA entrada por lote (não N) · cada item ganha decision_proof O(log N)
    FIN->>DB: bulk_insert_triage_items (executemany, tenant_transaction/RLS)
    FE->>R: GET /jobs/{job_id} (poll)
    R-->>FE: status + resultados
```

**Legenda:** `loop` = iteração; `group`/`chord` = primitivas Celery (fan-out + barreira de junção).

**Notas de design:**
- **Fan-out horizontal real** (chord entre réplicas do `fiscal-worker`), diferente do batch de scoring (threads). Preserva
  `SET LOCAL app.tenant_id` porque cada task roda em sua própria transação — RLS intacto.
- **Ancoragem Merkle de lote**: **1 entrada de Ledger por job** (não por item), com raiz do lote; cada item recebe uma
  **prova de inclusão O(log N)** (`decision_proof`). Evita o custo O(N²) de N inserções no ledger append-only.
- **Só a *chave* MinIO trafega pelo broker** (não os bytes) — evita payloads gigantes no Redis.

---

## 16. Diagrama de Sequência — Fluxo 4: Ingestão DATAJUD (medalhão + LGPD)

**Objetivo:** o pipeline de ingestão mais completo (bronze→silver→grafo) com circuit breaker e pseudonimização.

**Escopo:** Celery Beat → `datajud.run_daily_ingest` → 3 lojas.

```mermaid
sequenceDiagram
    participant BEAT as Celery Beat
    participant T as datajud.run_daily_ingest (worker)
    participant CB as CircuitBreaker(datajud)
    participant API as DATAJUD API (CNJ)
    participant PS as pseudonymize_process_record
    participant Q as datajud_bronze_to_silver (+TPU)
    participant SINK as persist_silver
    participant MIN as MinIO (bronze)
    participant OS as OpenSearch (silver)
    participant NEO as Neo4j (grafo)

    BEAT->>T: schedule diário
    T->>CB: is_open()?
    alt circuito fechado
        T->>API: GET processos (data)
        API-->>T: bronze records
        CB->>CB: record_success()
        T->>PS: pseudonimiza CPF/nome (HMAC-SHA256)
        PS-->>T: bronze sem PII em claro
        T->>Q: bronze→silver (quality + TPU normalize)
        Q-->>T: silver records
        T->>SINK: persist_silver(bronze, silver, graph_writer)
        SINK->>MIN: put_jsonl (bronze-datajud, Hive partition)
        SINK->>OS: bulk_index (datajud-silver-YYYY-MM)
        SINK->>NEO: upsert_process_edges (:Empresa)-[:PARTE_EM]->(:Processo)
        SINK-->>T: reconcile {records_in, records_out, loss_pct}
    else circuito aberto
        CB-->>T: is_open()=true → pula (usa cache Redis 48h)
    end
```

**Legenda:** `alt` sobre estado do circuit breaker.

**Notas de design:**
- **LGPD by design**: a pseudonimização (HMAC) ocorre **antes** de qualquer persistência; nenhuma das 3 lojas recebe PII
  em claro. O grafo Neo4j alimentado aqui é o que o LegalScore lê em `count_processos_por_cnpj`.
- **`reconcile`** mede perda entre entrada e saída (contrato de qualidade), registrada em `ingest.runs`.
- **Circuit breaker por fonte** com fallback a cache Redis de 48h — resiliência a instabilidade das APIs governamentais.

---

## 17. Diagrama de Sequência — Fluxo 5: Defensor agêntico + enriquecimento cross-service (Concilia)

**Objetivo:** ilustrar orquestração agêntica (RAG+LLM) e chamadas cross-service in-process com degradação.

**Escopo:** `defensor.run` (RAG+LLM) e, à parte, `concilia.recommend` consumindo taxpredict+legalscore.

```mermaid
sequenceDiagram
    actor FE as Frontend
    participant D as defensor.run_agente
    participant P as assemble_petition
    participant RAG as RAGEngine (ChromaDB+BGE-M3)
    participant LLM as generate_text (Ollama/OpenAI)
    participant DRV as get_driver → SimulacaoDriver

    FE->>D: POST /defensor/run (DefensorRequest)
    D->>D: _classificar / _consultar_historico
    D->>P: assemble_petition(PetiRequest)
    P->>RAG: search(descricao, n=5)
    RAG-->>P: precedentes (ou [] se offline)
    P-->>D: PetiResponse (seções + precedentes)
    loop cada seção
        D->>LLM: generate_text(prompt, system)
        alt LLM disponível
            LLM-->>D: texto (via="llm")
        else falha (primeira)
            LLM-->>D: None → via="template" (curto-circuita restante)
        end
    end
    D->>DRV: (opcional) protocolar → status SIMULADO
    D-->>FE: DefensorResponse (timeline EventoAgente + seções + handoff)
```

**Legenda:** `loop`+`alt` mostram a degradação por seção; retorno `None` do LLM comuta para template.

**Notas de design:**
- **Chamadas cross-service são in-process e graceful-degrade**: `concilia.recommend` importa o modelo taxpredict e lê
  `score:{cnpj}` do Redis; se qualquer um falha, segue com `None` e ajusta a recomendação — nunca 500.
- **Proveniência por seção** (`llm`/`parcial`/`template`) é exposta ao usuário (`ProvenanceTag` no frontend) — anti-alucinação.

---

## 18. Diagrama de Atividades — Fluxo 1: Seleção de engine de scoring com fallback (seam Rust)

**Objetivo:** o algoritmo de seleção/degradação do `factory` — o coração do seam Python↔Rust.

**Escopo:** `services/scoring/engine/factory.py` + runtime de `_FallbackEngine`.

```mermaid
flowchart TD
    ini(["get_score_engine backend"]) --> cfg{"SCORING_BACKEND?"}
    cfg -->|python| py["PythonScoreEngine"]
    cfg -->|rust| rh{"RustScoreEngine.healthy?"}
    cfg -->|auto| ah{"RustScoreEngine.healthy?"}
    rh -->|não| err[["raise ScoringUnavailable"]]
    rh -->|sim| fb1["_FallbackEngine rust→python"]
    ah -->|sim| fb2["_FallbackEngine rust→python"]
    ah -->|não| py
    py --> ready(["engine pronto"])
    fb1 --> ready
    fb2 --> ready

    ready --> invoke[["score(request)"]]
    invoke --> att{"primary.score"}
    att -->|ok| ret(["ScoreResult engine=rust/python"])
    att -->|ScoringUnavailable| sec["secondary.score = Python"]
    sec --> ret
    att -->|panic Rust real| crash[["processo derrubado — exige supervisor + healthcheck"]]
```

**Legenda:** `([ ])` = início/fim; `{ }` = decisão; `[[ ]]` = ação especial/exceção; `[ ]` = ação.

**Notas de design:**
- **Troca Python→Rust é configuração, não código** — nenhum chamador muda. O `_FallbackEngine` protege erros
  *recuperáveis* em runtime, mas um *segfault* nativo é fora do alcance do try/except (ramo `panic Rust real`): exige a
  outra camada de defesa (supervisor que reinicia o worker + health check antes de aceitar tráfego).
- **Equivalência comportamental** entre engines é garantida pela suíte `test_score_engine_contract.py` (determinismo,
  faixa 0–1000, coerência do IC) — pré-requisito para a migração ser segura.

---

## 19. Diagrama de Atividades — Fluxo 2: Triagem NCM + resolução ICMS/DIFAL (determinística)

**Objetivo:** a lógica de decisão fiscal (com fundamentos legais embutidos).

**Escopo:** `services/fiscal/triage/{engine,ncm_matcher,icms_resolver}.py`.

```mermaid
flowchart TD
    s([classify request]) --> hint{ncm_hint presente?}
    hint -->|sim| exact[match_exact TIPI conf=1.0]
    exact --> found{encontrado?}
    found -->|não| conflito[conflito_detectado=true]
    found -->|sim| icms
    hint -->|não| fuzzy[match_fuzzy rapidfuzz vs catálogo]
    fuzzy --> weak{confidence < threshold 0.82?}
    weak -->|sim| sem{semantic_source?}
    sem -->|sim| rag[RAG suggest fonte=RAG]
    sem -->|não| icms
    rag --> icms
    weak -->|não| icms
    conflito --> icms

    icms[/resolve_icms/] --> same{uf_origem == uf_destino?}
    same -->|sim| interna[interna_efetiva = modal + FCP; sem inter/DIFAL]
    same -->|não| inter[aliquota_interestadual: Res. SF 22/1989 7%/12% ou 13/2012 4%]
    inter --> difal[DIFAL = max 0, interna_efetiva_destino − interestadual EC 87/2015]
    interna --> cat
    difal --> cat
    cat{category_source?} -->|sim| addcat[anexa categoria]
    cat -->|não| result
    addcat --> result([NcmTriageResult])
```

**Legenda:** `[/ /]` = subprocesso; ramos rotulados = condições de negócio com base legal citada.

**Notas de design:**
- **100% determinístico** (auditabilidade > sofisticação): dado o mesmo input e a mesma base vigente, a saída é idêntica.
  `classify()` é puro (não toca o Ledger) — a ancoragem é etapa separada.
- **Fundamentos legais embutidos no código** (Res. SF 22/1989 e 13/2012, EC 87/2015, LC 190/2022) e propagados em
  `fundamento_legal` — rastreabilidade jurídica na própria resposta.
- **Escalonamento de confiança** TIPI(1.0) → FUZZY(0.82) → RAG — bom design de *fallback* de classificação.

---

## 20. Diagrama de Implantação (Deployment)

**Objetivo:** a topologia de execução Docker Compose — nós, containers, redes, volumes e protocolos.

**Escopo:** todos os fragmentos de `docker/compose/*` (mesclados via `include`) + o worker fiscal standalone.

```mermaid
flowchart TB
    subgraph host["Nó único — Docker host (rede juridico-net 172.20.0.0/16)"]
        direction TB
        subgraph proxy["Borda"]
            traefik["traefik:v3<br/>:80/:443 TLS Let's Encrypt"]
        end
        subgraph appt["Aplicação"]
            platform["platform (Next.js)<br/>:3000"]
            gateway["gateway (FastAPI/Uvicorn)<br/>:8000 /metrics /docs"]
        end
        subgraph workers["Workers Celery"]
            cw["celery-worker<br/>-Q daily,weekly,monthly,hourly,batch"]
            cb["celery-beat"]
            fw["fiscal-worker*<br/>-Q fiscal,batch,fiscal_ingest<br/>(Chromium+Tesseract)"]
            fb["fiscal-beat*"]
            flower["flower :5555"]
        end
        subgraph stores["Data stores"]
            postgres[("postgres:16<br/>(sem porta externa)")]
            pgbouncer[("pgbouncer:6432<br/>pool transaction")]
            neo4j[("neo4j:5 :7687")]
            opensearch[("opensearch:9200")]
            redis[("redis:7 :6379")]
            minio[("minio :9000/:9001<br/>buckets bronze/silver/gold/documents")]
            chromadb[("chromadb :8000")]
        end
        subgraph llm["LLM"]
            ollama["ollama :11434<br/>llama3:8b + bge-m3"]
        end
        subgraph obs["Observabilidade"]
            prometheus["prometheus :9090"]
            grafana["grafana :3001"]
            loki["loki :3100"]
            promtail["promtail"]
            alertmanager["alertmanager :9093"]
        end
        migrate[["migrate (one-shot)<br/>scripts/migrate.py como owner"]]
    end
    inet{{"Internet — APIs gov + Let's Encrypt"}}
    elixir{{"Elixir/Oban (alertas — externo/planejado)"}}

    inet -->|HTTPS| traefik
    traefik -->|Host DOMAIN| platform
    traefik --> gateway
    platform -->|"NEXT_PUBLIC_GATEWAY_URL http"| gateway
    gateway --> pgbouncer & redis & neo4j & opensearch & minio & chromadb & ollama
    cw --> pgbouncer & redis & neo4j & opensearch & minio
    fw --> pgbouncer & redis & minio
    cb --> redis
    fb --> redis
    flower --> redis
    pgbouncer --> postgres
    migrate --> postgres
    cw -->|HTTP| inet
    fw -->|scraping/OCR| inet
    gateway -->|alerts/v1 outbox| postgres
    elixir -->|lê alerts_outbox| postgres
    promtail --> loki
    prometheus --> gateway
    grafana --> prometheus & loki
    prometheus --> alertmanager
```

**Legenda:** `subgraph` = agrupamento lógico de nós; cilindro = data store; `[[ ]]` = container efêmero (one-shot);
`{{ }}` = sistema externo; `*` = o `fiscal-worker`/`fiscal-beat` vivem em `docker/compose/fiscal.yml` **não incluído** no
compose raiz (rede `external`), subidos à parte.

**Notas de design:**
- **Nó único, sem portas de banco expostas** — Postgres/Neo4j/OpenSearch/Redis/Chroma não publicam porta no host
  (acesso só interno/túnel SSH). Bom hardening; um job de CI (`docker-security`) verifica que `base.yml` não expõe DB.
- **PgBouncer em `pool_mode=transaction`** é pré-requisito do isolamento RLS via `SET LOCAL` — a topologia sustenta a
  decisão de segurança do código.
- **Segredos via Docker Secrets** (`/run/secrets/*`, `load_secret()`), preferidos a variáveis de ambiente.
- **Lacunas vs. README:** o README cita Redis **Sentinel** e Neo4j **Enterprise**, mas o compose entrega Redis single +
  Neo4j **Community**. `postgres-exporter`/`redis-exporter`/`node-exporter` são alvos de scrape do Prometheus mas **não
  há containers** definidos para eles. `infra/terraform` é apenas placeholder (o backup real está no Makefile). Kubernetes/Helm
  é roadmap (Fase 4), não presente. Registrar como gaps de infraestrutura.

---

## 21. Análise crítica — coesão, acoplamento e oportunidades de refatoramento

### 21.1. Pontos fortes (alta coesão, bom desacoplamento)

1. **Fronteira de tipos estável e explícita** (`services/shared/contracts`): DTOs imutáveis, versionados, `extra=forbid`.
   Os `Protocol`s (`ScoreEngine`, `AlertPublisher`, `NcmSource`, `RuleParser`) são *seams* de primeira classe — o sistema
   foi desenhado para trocar implementações (Rust, Elixir, DB, LLM) sem tocar chamadores.
2. **Núcleo puro + casca de I/O** repetido em quase todo serviço (`engine.py`/`detect.py`/`forecast.py` puros;
   `queries.py`/`tasks.py` com I/O). Facilita testes unitários determinísticos (o CI exige cobertura ≥ 80%).
3. **Conformidade projetada, não remendada**: Decision Ledger (Merkle) + crypto-shredding + RLS + audit_log formam um
   subsistema coeso que resolve o trade-off "imutabilidade × LGPD".
4. **Consistência de API**: o router LegalScore é um template P2 fielmente replicado (problem+json, idempotência, OTel,
   rate-limit por tenant).

### 21.2. Acoplamentos e riscos (oportunidades de refatoramento)

| # | Observação | Impacto | Sugestão |
|---|---|---|---|
| R1 | **Monólito modular**: todos os produtos no mesmo processo `gateway`. | Não escala/deploya por produto; um produto pesado (PyMC) afeta todos. | Extrair produtos de recurso-intensivo para serviços de rede reusando os `Protocol`s já existentes. |
| R2 | **Espelhamento manual de DTOs Python↔TS** (sem code-gen). | *Drift* silencioso entre backend e frontend. | Gerar tipos TS a partir do `/openapi.json` do gateway (openapi-typescript) no CI. |
| R3 | **Cadeia de imports entre contratos** (`concilia`→`petibot`, `protocolo`→`defensor`). | Dificulta versionar um contrato isoladamente. | Extrair enums compartilhados (`TipoAcao`, `Canal`, `PetiSection`) para `contracts/common`. |
| R4 | **Ledger O(N) por inserção** + advisory lock por tenant. | Throughput de escrita limitado por tenant; custo cresce com o histórico. | Migrar para MMR (Merkle Mountain Range) — já rastreado como QT-08. |
| R5 | **Pacotes placeholder vazios** (`ai-engine`, `shared/{consensus,http_client,vector_store,db}`). | Confundem o leitor sobre onde vive a lógica. | Remover ou preencher; documentar que RAG está em `ai/rag`, consenso em `second_opinion`. |
| R6 | **Componentes órfãos** (`AnomalyDetector`, `LLMRouter`, `LLMMemoizer` não plugados). | Código morto aparente / intenção ambígua. | Integrar num router ou marcar explicitamente como experimental. |
| R7 | **Duplicação de tokens Tailwind** (preset vs. `apps/platform/tailwind.config.ts`). | *Drift* visual entre design system e app. | App deve importar `@juridico/tokens/tailwind` em vez de reinlinar. |
| R8 | **`scoring` importa `ingest`** (produto→pipeline). | Acoplamento produto↔ingest. | Extrair enriquecimento para `shared/enrichment`. |
| R9 | **`compose/fiscal.yml` fora do include raiz** (rede `external`). | Worker fiscal esquecido em `make up`. | Consolidar no compose principal ou documentar o passo extra. |
| R10 | **Gaps README × compose** (Sentinel/Enterprise/exporters/terraform). | Expectativa de operação divergente do entregue. | Alinhar README ao estado real ou fechar os gaps de infra. |

### 21.3. Métricas qualitativas de acoplamento

- **`services/shared/contracts`** — *fan-in* altíssimo, *fan-out* ~zero → **dependência estável** (correto para um núcleo de contratos).
- **`gateway/routers`** — *fan-out* alto (dependem de todos os produtos), *fan-in* só do `main` → camada de fronteira fina (correto).
- **`services/shared/ai`** — reusado por petibot/defensor/fiscal/taxpredict → bom candidato a serviço isolado se a carga LLM crescer.

---

## 22. Observações específicas por linguagem

| Linguagem | Achados relevantes para a arquitetura |
|---|---|
| **Python** | `@dataclass(frozen=True)` (DTOs/value-objects como `AuthenticatedUser`, `FeatureVector`, `CrossCheckFinding`); Pydantic v2 `ConfigDict(frozen=True, extra="forbid")` nos contratos; `typing.Protocol` + `@runtime_checkable` como *seams* estruturais (o ponto arquitetural central); `@abstractmethod` em `ProtocoloDriver`; `StrEnum` onipresente (RiskLevel, UF, Canal…); decorators Celery `@app.task`; `@asynccontextmanager` (lifespan) e `@contextmanager` (`tenant_transaction`, `span`); imports dinâmicos/lazy para degradação graciosa (OTel, Redis, engines nativos). |
| **Rust** | **Não há código Rust.** Presente apenas como *seam* planejado: `RustScoreEngine` (adapter PyO3 sobre o crate `rust_scorer`), satisfazendo o `Protocol` `ScoreEngine` por estrutura (o crate não importaria Python). Migração por `SCORING_BACKEND=rust`, com `_FallbackEngine` e suíte de equivalência garantindo troca segura. *Ownership/lifetimes/traits* não se aplicam ainda; o contrato só troca dados primitivos serializáveis pela fronteira FFI. |
| **TypeScript** | Interfaces/`type` unions espelham contratos Pydantic (`LegalScoreResult`↔`ScoreResponse`, inclusive `engine:'python'\|'rust'`); tipos-união canônicos centralizados em `@juridico/tokens` (`RiskLevel`, `FreshnessBand`, `RbacRole`…); genéricos no client (`request<T>`, `api.get<T>`); React Context (`ShellProvider`) + TanStack Query (retry custom que **não** repete 429/501); design system em camadas com `workspace:*`. Sem decorators (não é NestJS — é Next.js App Router). |
| **Elixir** | **Não há código Elixir.** Consumidor externo planejado do contrato `alerts/v1` (fila Oban), alimentado pelo `HttpAlertPublisher` (Python→HTTP) ou pela tabela `alerts_outbox` (padrão outbox). O JSON Schema `schemas/alert.v1.json` é a fonte de verdade cross-linguagem, validada no CI. |

---

## 23. Justificativa de diagramas não incluídos / limitações

- **Diagrama de Estados (State Machine)** não foi destacado à parte, mas os estados relevantes estão modelados nos
  diagramas de atividade (circuit breaker `CLOSED/OPEN/HALF_OPEN`; status de job `queued/processing/done/failed`;
  status de protocolo `SIMULADO/ENVIADO/FALHA/AGUARDA_CREDENCIAIS`). Podem ser extraídos como `stateDiagram` se necessário.
- **Concorrência/paralelismo** aparece de forma pontual (ThreadPoolExecutor no batch de scoring; chord Celery no fiscal;
  advisory lock por tenant no ledger) — cobertos nos diagramas de sequência 15 e de atividade 18. Não há o modelo de
  concorrência rico de Rust (Arc/Mutex/RwLock) porque **não há Rust**; logo, o "diagrama de atividades de concorrência
  Rust" pedido no prompt **não se aplica** (justificativa registrada).
- **Diagramas parciais**: o diagrama de classes foi deliberadamente quebrado em 6 partes (A–F) por camada para não
  sobrecarregar; use as referências cruzadas (§7–§12) para navegar.

---

## 24. Checklist de cobertura

- [x] Mapeou todos os arquivos `.py` (270), `.ts` (31), `.tsx` (66) e a configuração de infra.
- [x] Extraiu dependências dos arquivos de configuração (`pyproject.toml`, `requirements.txt`, `package.json`, `tsconfig.json`, compose).
- [x] Identificou fronteiras entre linguagens e mecanismos de comunicação (REST, BFF, in-process, Celery/broker, seams PyO3/Elixir).
- [x] Gerou **7 tipos** de diagramas UML (casos de uso, pacotes, componentes, classes [6 partes], sequência [5 fluxos], atividades [2], implantação) — acima do mínimo de 5.
- [x] Usou **Mermaid** para todos os diagramas (renderizável no GitHub).
- [x] Incluiu notas de design e pontos de atenção para refatoramento (§21, R1–R10).
- [x] Quebrou diagramas complexos em partes menores (classes A–F; sequência em 5 fluxos separados).
- [x] Manteve nomes e estruturas fiéis ao código-fonte (case-sensitive) com rastreabilidade de arquivo.
- [x] Registrou a ausência de Rust/Elixir como *seams* planejados, com justificativa (§0.1, §22, §23).

---

> **Rastreabilidade:** todos os identificadores e caminhos citados referem-se ao estado do repositório em
> `claude/uml-analysis-multilang-pbjmkn`. Entidades-chave e seus arquivos estão listados no inventário do §2 e
> anotados diretamente nos diagramas de classes (§7–§12).
