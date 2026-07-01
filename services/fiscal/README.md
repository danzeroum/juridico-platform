# FiscalEngine (9º produto)

Triagem de **NCM** + resolução de **ICMS** (interno efetivo, interestadual, DIFAL) e
enriquecimento assíncrono de planilhas. Reusa a camada transversal da plataforma
(RLS multi-tenant, Decision Ledger Merkle, LGPD, Celery, ingestão resiliente).

## API (`/api/v1/fiscal`)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/ncm/triage` | Triagem síncrona de um item (determinística) → NCM + ICMS + `decision_proof` |
| GET | `/ncm/{codigo}?data=` | Descrição oficial vigente + IPI |
| GET | `/icms/{ncm}/{uf}?data=&importado=` | Interna efetiva (modal+FCP), interestadual, DIFAL |
| POST | `/spreadsheet/enrich` | Enriquecimento assíncrono (202 → polling) |
| GET | `/jobs/{job_id}` | Status do job |
| GET | `/audit/{request_id}` | Prova Merkle da triagem/lote |

Padrão P2: versionamento no path, `problem+json`, `Idempotency-Key`, rate limit por
tenant, OTel. Contratos em `services/shared/contracts/fiscal.py`.

## Motor de triagem (`triage/`)

1. **`ncm_hint` presente** → lookup exato (`fonte=TIPI`, confiança 1.0).
2. Sem hint → **fuzzy** léxico (`rapidfuzz`); se a confiança for baixa e houver
   `semantic_source`, usa **RAG semântico** (BGE-M3/Ollama + ChromaDB) como fallback.
3. Confiança abaixo do limiar → `conflito_detectado=True` (fila de revisão humana).
4. `icms_resolver`: interna efetiva = modal + FCP/FECP; interestadual pela Resolução
   do Senado (22/1989, 13/2012; 4% p/ importado >40%); DIFAL (EC 87/2015, LC 190/2022).

## Ledger (anti-O(N²))

- Triagem individual: 1 entrada no Decision Ledger (1:1).
- Lote: **1 raiz Merkle do lote → 1 entrada por job** (`batch/anchor.py`); o
  `decision_proof` de cada item é a prova de inclusão. `triage_item` gravado em bulk.

## Enriquecimento de planilhas

`spreadsheet/` preserva fórmulas (colunas novas à direita, `openpyxl`). O
`enrich_spreadsheet` dispara um **chord Celery** (chunks em paralelo → `finalize`
ancora uma vez). Limite de `50_000` linhas por request.

## Ingestão (roda no worker fiscal — tem Chromium/Tesseract)

| Fonte | Módulo puro (testado) | Task (fila `fiscal_ingest`) | Agendamento |
|---|---|---|---|
| RFB TIPI (NCM/IPI) | `ingestion/rfb_tipi` (contrato) | `rfb_tipi.run_ingest` | mensal |
| SEFAZ SP/RJ/MG | `ingestion/sefaz_parse` + `browser` | `sefaz_scraper.run_ingest` | semanal |
| CONFAZ (PDF/OCR) | `ingestion/confaz_parse` | `confaz_ocr.run_ingest` | sob demanda¹ |
| Histórico NCM | `ingestion/ncm_history` | `ncm_history.run_ingest` | sob demanda¹ |
| IBGE / Diário Oficial | `ingestion/ibge_parse` / `diario` | — | — |

¹ Precisam de descoberta de links (CONFAZ) / URL de fonte — a definir.

Padrão de resiliência herdado de `services/ingest/pipeline/base.py` (circuit breaker,
`reconcile`) + scorecard de qualidade (quarentena de outliers). CONFAZ usa parser LLM
(Ollama) com fallback heurístico determinístico e **validação humana** antes de persistir.

## Dados

Migração `scripts/migrations/003_fiscal_schema.sql` (schema `fiscal`): tabelas de
referência globais (NCM/TIPI/ICMS, `EXCLUDE` de vigência, FCP, campos IBS/CBS
reservados) e por tenant (`triage_job`/`triage_item`, RLS FORCED). Seed:
`scripts/seed_fiscal.py` (matriz interestadual 27×27 + SP/RJ/MG com FECP).

## Execução

```bash
# API: registrada no gateway (services/gateway/main.py)
# Worker + Beat (Chromium/Tesseract na imagem):
docker compose -f docker/compose/base.yml -f docker/compose/fiscal.yml up \
  --scale fiscal-worker=2 fiscal-worker fiscal-beat

# Migração + seed:
python scripts/migrate.py && python scripts/seed_fiscal.py
```

## Testes

`pytest tests/unit/test_fiscal_*.py` (105 testes; inclui navegador real via Playwright
e extração de PDF real via pdfplumber). OCR (tesseract), LLM/embedding (Ollama) e
ChromaDB são caminhos plugáveis validados em E2E.
