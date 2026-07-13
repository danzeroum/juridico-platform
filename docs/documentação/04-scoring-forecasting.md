# 04 — Scoring (SEAMS) + Forecasting

> Mapeamento linha a linha dos dados de `services/scoring/*` e `services/forecasting/*`.
> Foco: como um LegalScore nasce (features → engine → resultado), o estado de idempotência/batch em Redis,
> as métricas de validação, e a fronteira **Python↔Rust** (seam PyO3, sem código Rust hoje).
>
> **Legenda:** `→` (vira/transforma) · `⚙` (dado efêmero/descartado na própria função) · `🔒` (PII/segredo) ·
> `🌐` (cruza fronteira de linguagem/processo). ⇐ leitura · ⇒ escrita.

---

## `services/shared/contracts/scoring.py` — o contrato da fronteira (resumo; detalhe em `01`)

- **Entradas:** `ScoreRequest{cnpj:str ^\d{14}$ 🔒, cnae_2dig:str ^\d{2}$, features:dict[str,float]}` (frozen, extra=forbid).
- **Saídas:** `ScoreResult{score:int 0–1000, risk_level:RiskLevel, confidence_interval:tuple[int,int], breakdown:dict[str,float], engine:str, contract_version="scoring/v1"}` — validador `_check_ci` rejeita lo>hi.
- **Fronteiras:** 🌐 `ScoreEngine(Protocol, runtime_checkable){name; healthy()->bool; score(ScoreRequest)->ScoreResult}`
  é a **única "língua" da fronteira Python↔Rust**. Só primitivos serializáveis cruzam. `CONTRACT_VERSION="scoring/v1"`.
  Exceções `ScoringError`/`ScoringUnavailable` sinalizam fallback.

---

## `services/scoring/engine/engines.py`

- **Entradas:**
  - `PythonScoreEngine.__init__(coefficient_loader=None)` — injeção de função `cnae → dict de coeficientes`.
  - `PythonScoreEngine.score(request: ScoreRequest)` — lê `request.cnae_2dig`, `request.features` (7 chaves).
  - `_default_coefficients(cnae_2dig)` ⇐ placeholder (em produção viria do PostgreSQL: calibração por setor).
  - `RustScoreEngine.__init__` — tenta `import rust_scorer` 🌐 (crate PyO3); se ausente, `_native=None`.
- **Intermediário (⚙):**
  - `FEATURE_NAMES: tuple[str,...]` (7): `processos_ativos, processos_trabalhistas, divida_ativa_valor_log,
    divida_ativa_crescimento, saldo_emprego_12m, capital_social_log, processos_repetitivos` — ordem do contrato MLR.
  - `coef: dict` = `{feature→peso, intercept=300.0, sigma=40.0}` ⚙ (descartado após o cálculo).
  - `raw: float` = `intercept + Σ coef[name]·features[name]` ⚙ (acumulador do MLR).
  - `breakdown[name]: float` = `round(coef·feature, 4)` — contribuição por feature (vai para a saída).
  - `score: int` = `max(0, min(1000, round(raw)))` (clamp 0–1000).
  - `sigma: float` → intervalo de confiança `lo = max(0, round(score − 1.96σ))`, `hi = min(1000, round(score + 1.96σ))` ⚙.
  - `_classify(score)` → `RiskLevel`: ≥800 BAIXO · ≥600 MODERADO · ≥400 ALTO · else CRITICO.
  - `RustScoreEngine.healthy()` ⚙ — sonda `_native.score("00", {})`, checa `isinstance(dict) and "score" in probe`.
  - `RustScoreEngine.score()`: `out = _native.score(cnae_2dig, dict(features))` 🌐 → `{score, confidence_interval, breakdown}`.
- **Saídas:** `ScoreResult{score, risk_level, confidence_interval:(lo,hi), breakdown, engine="python"|"rust"}`.
- **Fronteiras (🌐):** `RustScoreEngine` converte `ScoreRequest → primitivos (str, dict[str,float])` na ida e
  `dict → ScoreResult` na volta pela FFI PyO3. **Panic do Rust → exceção Python → `ScoringUnavailable`**. Como
  `features` já são números, nada de objeto Python específico cruza a linha. **Rust não existe como código** — o
  adapter se reporta não-saudável até o crate `rust_scorer` ser compilado (maturin).

---

## `services/scoring/engine/factory.py`

- **Entradas:** `get_score_engine(backend="auto")` ⇐ env `SCORING_BACKEND` (`python|rust|auto`); `_FallbackEngine.__init__(primary, secondary)`.
- **Intermediário (⚙):**
  - `python = PythonScoreEngine()`, `rust = RustScoreEngine()` ⚙ (instâncias efêmeras).
  - `_FallbackEngine.name = f"{primary.name}->{secondary.name}"` (ex.: `"rust->python"`).
  - `_FallbackEngine.score()`: tenta `primary.score`; captura `ScoringUnavailable` → `secondary.score`.
  - `_FallbackEngine.healthy()` = `primary.healthy() OR secondary.healthy()`.
- **Saídas:** um objeto que satisfaz `ScoreEngine` (Python puro, ou `_FallbackEngine(rust, python)`).
- **Fronteiras (🌐):** decide se o dado será processado em Python ou cruzará para Rust — **por configuração, não por
  código**. `backend="rust"` sem crate saudável → `ScoringUnavailable`.

---

## `services/scoring/features.py` — montagem do feature vector (data enrichment)

- **Entradas:**
  - `assemble_features(cnpj: str 🔒, redis_client)` — parâmetros.
  - `_fetch_pgfn(cnpj, redis)` ⇐ **Redis `pgfn:{cnpj}`** (JSON bronze) → `pgfn_bronze_to_silver(data)` 🌐 (import de `services.ingest.pipeline.quality`).
  - `_fetch_receita(cnpj, redis)` ⇐ **Redis `receita:{cnpj}`** (JSON) → `receita_bronze_to_silver(data)` 🌐.
  - `_fetch_datajud(cnpj)` ⇐ **Neo4j** `count_processos_por_cnpj(cnpj)` 🌐 (arestas `PARTE_EM`).
- **Intermediário (⚙):**
  - `features: dict[str,float]` inicializado com as 7 `FEATURE_NAMES` = `0.0` (default de degradação).
  - `sources_used`/`sources_missing: list[str]` — acumuladores por fonte (PGFN/RECEITA/DATAJUD).
  - `pgfn.get("valor_divida_log")` → `features["divida_ativa_valor_log"]`.
  - `receita.get("capital_social_log")` → `features["capital_social_log"]`; `receita.get("ingested_at")[:10]` → `source_date`.
  - `cnae_raw = receita.get("cnae_fiscal") or "0000000"` ⚙ → `cnae_2dig = cnae_raw[:2]` (ou `"00"`).
  - `datajud["total"]/["trabalhistas"]/["repetitivos"]` → 3 features de processos (`float(...)`).
  - `is_partial = len(sources_missing) > 0`.
  - Exceções de parse ⚙ → `logger.warning` + `None` (nunca 500).
- **Saídas:** `FeatureVector{cnpj, features:dict[str,float], cnae_2dig:str, sources_used:list, sources_missing:list,
  source_date:str|None, lag_days:int|None (não preenchido aqui), is_partial:bool}` (`@dataclass`).
- **Fronteiras (🌐):** consome caches produzidos pela ingestão (bronze→silver) e o grafo Neo4j; **degradação graciosa**
  total (fonte ausente → feature 0.0 + `is_partial=True`).

---

## `services/scoring/idempotency.py` — estado Redis (idempotência + batch)

- **Entradas:** `redis`, `tenant_id 🔒`, `key`, `cnpjs:list[str] 🔒`, `job_id`, `processed`, `results:list[dict]`.
- **Intermediário (⚙):**
  - `_IDEMP_TTL = 86400` (24h), `_BATCH_TTL = 86400`.
  - `job_id = f"batch_{uuid.uuid4().hex[:16]}"` — id efêmero gerado.
  - `payload: dict` do batch = `{job_id, tenant_id, status, total, processed, results, created_at, completed_at}`.
  - `remaining = redis.ttl(...)` ⚙ — preserva TTL original ao atualizar progresso (não encurta o prazo).
- **Saídas (⇒ Redis):**
  - `idemp:{tenant_id}:{key}` = JSON do resultado (setex 24h) — segurança de retry.
  - `batch:{job_id}` = JSON de acompanhamento (setex 24h); `status ∈ {queued, processing, done}`.
- **Fronteiras:** estado compartilhado entre gateway (cria/consulta) e worker Celery (atualiza) via Redis.

---

## `services/scoring/tasks.py` — tarefa Celery de batch

- **Entradas:** `run_batch_score(self, job_id: str, cnpjs: list[str] 🔒)` 🌐 (args via broker Celery); `get_redis()` ⇐ `REDIS_URL`.
- **Intermediário (⚙):**
  - `_MAX_WORKERS = 20` — `ThreadPoolExecutor` (I/O-bound: gets no Redis).
  - `_score_single(cnpj, redis)`: `assemble_features` → `get_score_engine()` → `EngineScoreRequest(cnpj, features, cnae_2dig)` → `engine.score(req)`.
  - `futures: dict[Future→cnpj]` ⚙; `result: dict` por CNPJ = `{cnpj, score, risk_level, confidence_interval:list,
    breakdown, is_partial, sources_missing, source_date, engine, error}`.
  - `processed` (contador); atualiza progresso **a cada 100** CNPJs.
  - Exceção por CNPJ ⚙ → `{cnpj, score:None, risk_level:None, error:str}` (item degradado, não derruba o lote).
- **Saídas:**
  - ⇒ Redis `batch:{job_id}` (via `update_batch_progress`): status `processing`→`done`, `results[]`, `completed_at`.
  - `return {job_id, processed, total}` (resultado da task).
- **Fronteiras (🌐):** args serializados pelo broker Redis; resultado persistido em Redis (polling pelo gateway).

---

## `services/scoring/validation.py` — métricas do modelo

- **Entradas:** `compute_auc(y_true:list[int], scores:list[int])`, `compute_brier(y_true, probabilities:list[float])`,
  `score_to_probability(score:int)`. Dataset esperado (doc): `{cnpj, score_previsto, desfecho_real, data_desfecho, data_score}`.
- **Intermediário (⚙):**
  - `ModelMetrics{model_type="heuristica", auc=None, brier_score=None, calibration_r2=None, n_validation_samples=None,
    validation_status="pending", validation_note, last_calibrated=None, target_auc=0.70, target_brier=0.20}`.
  - `compute_auc`: `positives=sum(y_true)`, `negatives=n−positives`; `pairs = sorted(zip(scores,y_true), reverse=True)` ⚙;
    varredura `tp/fp/prev_fp` acumulando `auc += tp·(fp−prev_fp)`; normaliza por `positives·negatives` → `round(auc,4)` (O(n²)).
  - `compute_brier`: `mean((p−y)²)` → `round(,4)`.
  - `score_to_probability`: `1.0 − score/1000.0`.
- **Saídas:** `ModelMetrics` (para `GET /legalscore/model-metrics`); floats AUC/Brier/probabilidade.
- **Fronteiras:** nenhuma externa; dados de validação são estáticos/futuros (Fase 1d).

---

## `services/scoring/celery_app.py`

- **Entradas:** ⇐ env `REDIS_URL` (broker+backend, default `redis://localhost:6379/0`).
- **Intermediário (⚙):** `app = Celery('scoring')`; `timezone='America/Sao_Paulo'`; `task_default_queue='scoring'`;
  `include=['services.scoring.tasks']`.
- **Saídas:** app Celery registrando `run_batch_score`.
- **Fronteiras (🌐):** broker Redis (fila `scoring`).

---

## `services/scoring/tests/contract/test_score_engine_contract.py`

- **Entradas:** engines disponíveis (Python sempre; Rust se compilado) + `ScoreRequest` sintéticos.
- **Intermediário (⚙):** asserções de propriedade — determinismo (mesmo input → mesmo output), `0 ≤ score ≤ 1000`,
  coerência do IC (`lo ≤ score ≤ hi`), `breakdown ⊆ FEATURE_NAMES`, `contract_version`.
- **Saídas:** garantia de **equivalência comportamental Python↔Rust** (`test_equivalencia_python_vs_rust`) — pré-requisito da migração.
- **Fronteiras (🌐):** valida ambos os lados do seam PyO3 usando o mesmo contrato.

---

## `services/forecasting/forecast.py` — núcleo puro de previsão

- **Entradas:** `forecast_series(valores: list[float], horizonte=3)`; `_linear_fit(xs, ys)`.
- **Intermediário (⚙):**
  - `MIN_PERIODOS = 3`; `serie = [float(v) for v in valores if v is not None]` (filtra nulos).
  - `xs = [0..n-1]` (índices); `a, b = _linear_fit(xs, serie)` (OLS: `b = Σ(x−x̄)(y−ȳ)/Σ(x−x̄)²`, `a = ȳ − b·x̄`).
  - `resid = serie[i] − (a + b·xs[i])` ⚙ → `rmse = sqrt(mean(resid²))` (proxy de incerteza).
  - por passo `h`: `ponto = max(0, a + b·x)`; `margem = 1.96·rmse`; `intervalo = [ponto−margem, ponto+margem]` (≥0).
  - `tendencia = CRESCENTE|DECRESCENTE|ESTAVEL` (sinal de `b`).
- **Saídas:** `dict{status, tendencia, inclinacao:round(b,4), ultimo_valor, projecoes:[{passo,valor,intervalo}], disclaimer}`
  ou `{status:"insuficiente", min_periodos, n}`.
- **Fronteiras:** nenhuma (puro, sem I/O — testável isoladamente).

---

## `services/forecasting/queries.py` — camada I/O

- **Entradas:** `forecast_demand(tribunal, classe=None, assunto=None, horizonte=3)`; `_serie_historica(...)` ⇐ **Postgres
  `jurimetria.indicador`** (`get_engine()` global, sem tenant).
- **Intermediário (⚙):**
  - `where = ["tribunal = :tribunal", "periodo <> 'TODOS'"]` + filtros opcionais `classe_tpu`/`assunto_tpu` ⚙.
  - SQL: `SELECT periodo, SUM(n_processos) AS n ... GROUP BY periodo ORDER BY periodo ASC`.
  - `serie: list[dict{periodo, n}]`; `valores = [row["n"]]` → `forecast_series(valores, horizonte)`.
  - falha de banco ⚙ → `logger.warning` + `[]` (degradação graciosa).
- **Saídas:** `dict{tribunal, classe_tpu, assunto_tpu, periodos_historicos:[...], **forecast_series(...)}`.
- **Fronteiras (🌐):** lê o feature store gold (`jurimetria.indicador`) produzido por `ingest.tasks.jurimetria_aggregate`.

---

## Entidades globais desta fatia (para o dicionário mestre)

- **`FEATURE_NAMES` (7):** processos_ativos, processos_trabalhistas, divida_ativa_valor_log, divida_ativa_crescimento,
  saldo_emprego_12m, capital_social_log, processos_repetitivos.
- **Chaves Redis lidas:** `pgfn:{cnpj}`, `receita:{cnpj}` (features); `idemp:{tenant_id}:{key}` (24h), `batch:{job_id}` (24h).
- **Neo4j:** `count_processos_por_cnpj(cnpj)` → `{total, trabalhistas, repetitivos}` (arestas `PARTE_EM`).
- **Postgres lido:** `jurimetria.indicador(periodo, n_processos, tribunal, classe_tpu, assunto_tpu)` (forecasting).
- **Celery:** task `run_batch_score(job_id, cnpjs)` na fila `scoring` (app `services.scoring.celery_app`).
- **Fronteira Rust (PyO3, planejada):** o que cruzaria = `(cnae_2dig: str, features: dict[str,float])` na ida e
  `{score:int, confidence_interval:(int,int), breakdown:dict[str,float]}` na volta. Hoje **sem código Rust** —
  `RustScoreEngine.healthy()==False` e o factory cai para `PythonScoreEngine`.
- **env:** `SCORING_BACKEND` (python|rust|auto), `REDIS_URL`.
