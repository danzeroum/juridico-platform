# Mapeamento Completo de Dados — `juridico-platform`

> **Objetivo:** catalogar **todos os dados que circulam no sistema inteiro** — entradas, saídas e
> processamento intermediário — em todas as linguagens (Python, TypeScript, HTML/JSX, SQL, YAML, JSON),
> a partir de uma **análise linha a linha de todos os scripts** do repositório. Inclui até dados efêmeros
> que se perdem na própria função/classe (variáveis locais, valores derivados descartados).
>
> Esta documentação complementa `docs/arquitetura-uml.md` e `docs/arquitetura-diagramas-completos.md`.
> Aqui o foco **não é a estrutura**, e sim o **dado**: de onde vem, o que vira e para onde vai.

## Escopo e contagem

| Linguagem | Arquivos | Situação |
|---|---|---|
| Python (`.py`) | 270 | backend completo (gateway, serviços, ingest, workers) |
| TypeScript/TSX (`.ts`/`.tsx`) | 97 | frontend (app Next.js + design system) |
| SQL (`.sql`) | migrações + bootstrap | schema do PostgreSQL |
| JSON Schema | `schemas/alert.v1.json` | contrato cross-linguagem |
| YAML/Config | docker-compose, CI, `.env.example` | infraestrutura e configuração |
| **Rust** | **0** | não há código — apenas *seam* planejado (`ScoreEngine` via PyO3); documentado em `07`/`04` |

## Organização (arquivos deste diretório)

| Arquivo | Escopo de dados |
|---|---|
| `01-contratos-e-schemas.md` | `services/shared/contracts/*` + `schemas/*` — os **tipos de dado** (DTOs) que trafegam nas fronteiras |
| `02-gateway.md` | `services/gateway/*` — dados de request/response, JWT, headers, estado de request, dispatch |
| `03-shared-infra.md` | `services/shared/*` (ledger, lgpd, crypto, ai, alerts, storage, tenant_db, config, audit_log, tpu) |
| `04-scoring-forecasting.md` | `services/scoring/*` + `services/forecasting/*` — features, score, batch, métricas |
| `05-fiscal.md` | `services/fiscal/*` — triagem NCM, ICMS/DIFAL, planilhas, ingestão fiscal (scraping/OCR) |
| `06-ingest.md` | `services/ingest/*` — contratos bronze/silver das 14 fontes, pipeline, tarefas Celery |
| `07-taxpredict-audit-compliance-concilia.md` | `taxpredict`, `audit` (ContabilIA), `compliance`, `concilia` |
| `08-defensor-petibot-analiticos.md` | `defensor`, `petibot`, `jurimetria`, `knowledge_graph`, `early_warning`, `chamber_profiler`, `second_opinion`, `settlement_optimizer` |
| `09-frontend.md` | `frontend/*` — DTOs TS, client HTTP, rotas API (BFF), estado React, props de componentes |
| `10-infra-config-scripts.md` | `docker/*`, `scripts/*` (migrações, bootstrap, seed), `.env.example`, CI, `infra/*` |
| `99-dicionario-global-de-dados.md` | **Dicionário mestre**: chaves Redis, tabelas/colunas, buckets MinIO, coleções Chroma, índices OpenSearch, nós/arestas Neo4j, variáveis de ambiente/segredos, nomes de tasks Celery, DTOs cross-linguagem |

## Metodologia

Para **cada arquivo**, os dados são classificados em quatro categorias:

- **Entradas** — parâmetros de função/método (`nome: tipo`), corpos/query/path/headers de request, variáveis de
  ambiente/segredos/settings lidos, leituras de banco (`schema.tabela.coluna`), Redis (padrão de chave), MinIO
  (`bucket/key`), OpenSearch/Neo4j/ChromaDB, respostas de APIs externas, uploads de arquivo, argumentos de CLI/Celery.
- **Intermediário** — variáveis locais relevantes, valores derivados/computados, transformações (bronze→silver,
  normalizações, hashes, encodings), acumuladores de laço, tabelas de lookup/constantes — com tipo e no que se tornam.
  **Inclui dados efêmeros** computados e descartados dentro da função/classe.
- **Saídas** — valores de retorno (tipo/forma), respostas HTTP (status + forma do corpo), escritas em banco
  (`tabela.colunas`), Redis/MinIO/OpenSearch/Neo4j/Chroma (chave/bucket/índice/coleção), dispatch de task Celery
  (nome + args), mensagens publicadas (`AlertEnvelope`), logs/eventos de auditoria, arquivos gravados.
- **Fronteiras/serialização** — quando o dado cruza uma fronteira de linguagem/processo (Pydantic↔JSON↔TS, FFI PyO3,
  broker Celery, HTTP) e qual contrato/versão governa a serialização.

## Legenda de notações

| Símbolo | Significado |
|---|---|
| `→` | fluxo/transformação do dado ("vira") |
| `⇒ DB` / `⇒ Redis` / `⇒ MinIO` | destino de escrita |
| `⇐ DB` / `⇐ Redis` / `⇐ API` | origem de leitura |
| `⚙` | dado efêmero/intermediário descartado na própria função |
| `🔒` | dado sensível (PII/segredo) — sujeito a pseudonimização/cifra |
| `🌐` | dado que cruza fronteira de linguagem/processo |

---

*Índice gerado como parte do mapeamento de dados linha a linha. Os arquivos numerados detalham cada módulo.*
