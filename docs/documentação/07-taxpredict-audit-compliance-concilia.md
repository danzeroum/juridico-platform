# 07 — TaxPredict · ContabilIA · ComplianceRadar · ConciliaIA

Catálogo de fluxo de dados linha a linha para os serviços `taxpredict`, `audit` (ContabilIA), `compliance` (ComplianceRadar) e `concilia` (ConciliaIA). Documentação gerada a partir da leitura integral do código-fonte.

**Legenda**
- ⚙ — valor **Intermediário** (escalar computado, valor descartado/derivado, não persistido diretamente)
- 🔒 — dado sensível: **CNPJ** ou **financeiro** (DRE, valor de causa, receita, etc.)
- 🌐 — **Fronteira**: MinIO (trace NetCDF), Celery, chamada cross-service in-process, AlertEnvelope (fila/webhook)

Cada seção classifica os dados em: **Entradas · Intermediário (⚙) · Saídas · Fronteiras (🌐)**.

---

## TaxPredict

### `services/taxpredict/model/bayesian.py` — `TaxPredictionModel`

Modelo hierárquico bayesiano (PyMC5). Níveis: prior nacional → matéria → caso. `fit()` roda MCMC (só em Celery Beat); `predict()` roda no path da request usando trace pré-carregado.

**Entradas**
- `materia: str` — construtor `__init__` (ex.: `"PIS/COFINS"`).
- `fit(data)` — DataFrame de treino com colunas: 🔒 `data["valor_log"]`, `data["recencia"]`, `data["indicador_economico"]`, `data["sucesso"]` (variável observada Bernoulli).
- `predict(case: dict[str, float])` — dict de caso com chaves `valor_log`, `recencia`, `indicador_economico` (default `0.0` cada via `case.get(...)`).
- `load_from_minio(minio_client, bucket, key)` / `save_to_minio(...)` — `bucket` (`"gold"`), `key` (`"taxpredict/pis_cofins.nc"`).

**Intermediário (⚙)**
- ⚙ `valor_log`, `recencia`, `indicador` — `pm.MutableData` (features condicionáveis, `dims="obs"`).
- ⚙ **Priors PyMC**: `mu_national ~ Normal(mu=0.3, sigma=0.15)`; `beta_valor ~ Normal(0, 0.1)`; `beta_recencia ~ Normal(0, 0.1)`; `beta_economico ~ Normal(0, 0.05)`.
- ⚙ `logit_p = mu_national + beta_valor*valor_log + beta_recencia*recencia + beta_economico*indicador`.
- ⚙ `p = pm.Deterministic("p", sigmoid(logit_p), dims="obs")`.
- ⚙ `pm.Bernoulli("obs", p=p, observed=data["sucesso"].values)`.
- ⚙ Parâmetros de amostragem `fit`: `draws=500, tune=500, chains=2, target_accept=0.9, random_seed=42, progressbar=False`.
- ⚙ `self._trace` (InferenceData ArviZ), `self._model`, `self._is_loaded` (estado interno).
- ⚙ `predict`: `ppc = sample_posterior_predictive(trace, var_names=["p"], random_seed=42)`; `draws = ppc.posterior_predictive["p"].values.flatten()`.
- ⚙ `prob = mean(draws)`; `ci_lower = percentile(draws, 2.5)`; `ci_upper = percentile(draws, 97.5)` (todos `float`, arredondados a 4 casas).
- ⚙ `is_ready` (property) = `_is_loaded and _trace is not None`.

**Saídas**
- `predict()` → `{"probability": round(prob,4), "ci_lower": round(ci_lower,4), "ci_upper": round(ci_upper,4)}`.
- `fit()` → `None` (efeito colateral: popula `_trace`, `_model`, `_is_loaded`).
- `RuntimeError` se trace/modelo não carregado; `ImportError` se `pymc`/`arviz`/`pandas` ausentes.

**Fronteiras (🌐)**
- 🌐 **MinIO** `save_to_minio`: serializa `_trace` → NetCDF via `az.to_netcdf(_trace, buf)`; `minio_client.put_object(bucket, key, buf, nbytes)`. Gold key: `minio://gold/taxpredict/pis_cofins.nc`.
- 🌐 **MinIO** `load_from_minio`: `minio_client.get_object(bucket, key).read()` → `az.from_netcdf(BytesIO(data))`. Chamado UMA VEZ no startup.

### `services/taxpredict/tasks.py` — `recalibrate_model` (Celery task)

**Entradas**
- Task arg `materia: str = "PIS_COFINS"` (`self` via `bind=True`).
- Env: `TAXPREDICT_BUCKET` (default `"gold"`) → `_MINIO_BUCKET`.
- Config `settings`: `MINIO_URL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`.

**Intermediário (⚙)**
- ⚙ `data_key = f"taxpredict/training/{materia.lower().replace('/', '_')}.parquet"`.
- ⚙ `model_key = f"taxpredict/{materia.lower().replace('/', '_')}.nc"`.
- ⚙ `df = pd.read_parquet(BytesIO(data_obj.read()))` — 🔒 DataFrame de treino.
- ⚙ `len(df)` → `n_samples`.
- ⚙ cliente `Minio(...)` construído a partir de `settings`.

**Saídas**
- Retorno `{"status": "ok", "materia": materia, "n_samples": len(df)}`.
- Em falha: `self.retry(exc=exc, countdown=300, max_retries=3)`.

**Fronteiras (🌐)**
- 🌐 **Celery task** `name="taxpredict.recalibrate"`, `queue="taxpredict"`, `bind=True`.
- 🌐 **MinIO** leitura: `minio.get_object(_MINIO_BUCKET, data_key)` — parquet `gold/taxpredict/training/{materia}.parquet`.
- 🌐 **MinIO** escrita via `model.save_to_minio(minio, _MINIO_BUCKET, model_key)` → `gold/taxpredict/{materia}.nc`.
- 🌐 In-process: `model.fit(df)` (MCMC).

### `services/taxpredict/celery_app.py` — app Celery

**Entradas / Intermediário / Fronteiras**
- Env `REDIS_URL` (default `redis://localhost:6379/0`) → broker **e** backend.
- 🌐 App `Celery("taxpredict")`; `timezone="America/Sao_Paulo"`; `task_default_queue="taxpredict"`.

### `services/taxpredict/__init__.py`
- Marcador de pacote (`# Package taxpredict`). Sem dados.

---

## ContabilIA (audit)

### `services/audit/crosscheck/engine.py` — `CrossCheckEngine` + `CrossCheckFinding`

Valida DRE/balanço (`financials`) contra dados públicos pré-buscados (`public_data`: CAGED, SICONFI, PNCP). Regras CC01–CC08.

**Entradas**
- `run_checks(financials: dict, public_data: dict)`.
- 🔒 `financials` (DRE): `headcount`, `receita_liquida`, `receita_servicos_publicos`, `importacoes`, `variacao_estoque`, `ativo_circulante`, `passivo_circulante`, `ebitda`, `serie_receitas_mensais`, `serie_despesas_mensais`.
- `public_data`: `caged_saldo_12m`, `siconfi_receita_total`, `pncp_contratos_total`.

**Intermediário (⚙) — por regra**
- ⚙ **CC01** (headcount vs CAGED): guarda `headcount is None or caged_saldo is None or headcount == 0` → `[]`; `delta = abs(headcount - caged_saldo)/abs(headcount)`; dispara se `delta > 0.20`. `detail.delta_pct = round(delta*100,1)`.
- ⚙ **CC02** (receita vs SICONFI): guarda `siconfi_receita == 0`; `delta = abs(receita_dre - siconfi_receita)/abs(siconfi_receita)`; dispara se `delta > 0.30`.
- ⚙ **CC03** (contratos vs PNCP): dispara se `pncp_total == 0 and receita_publica > 0` (sem delta numérico).
- ⚙ **CC04** (importações vs estoque): guarda `importacoes == 0`; `ratio = variacao_estoque / importacoes`; dispara se `ratio > 3.0`. `detail.ratio = round(ratio,2)`.
- ⚙ **CC05** (Benford receitas): guarda `len(series) < 30`; `result = analyze_benford(series, column="receitas_mensais")`; dispara se `result.status in ("MARGINAL","SUSPEITO")`; `ValueError` → `[]`.
- ⚙ **CC06** (Z-score despesas): guarda `len(series) < 2`; `result = compute_zscore(series, column="despesas_mensais", threshold=3.0)`; dispara se `result.outliers`; `ValueError` → `[]`.
- ⚙ **CC07** (liquidez): guarda `passivo <= 0`; `liquidez = ativo/passivo`; dispara se `liquidez < 0.5`. `detail.liquidez = round(liquidez,4)`.
- ⚙ **CC08** (margem EBITDA): guarda `receita == 0`; `margem = ebitda/receita`; dispara se `margem < -0.30 or margem > 0.60`. `detail.margem_pct = round(margem*100,1)`.

**Saídas**
- `run_checks` → `list[CrossCheckFinding]`.
- `CrossCheckFinding{rule, severity, description, detail: dict}`.
- Severidades por regra: CC01=`ALTO`, CC02=`CRITICO`, CC03=`MEDIO`, CC04=`MEDIO`, CC05=`ALTO` se `SUSPEITO` senão `MEDIO`, CC06=`ALTO`, CC07=`CRITICO`, CC08=`ALTO`.
- `detail` por regra: CC01 `{dre, caged, delta_pct}`; CC02 `{dre, siconfi, delta_pct}`; CC03 `{receita_dre, pncp_contratos}`; CC04 `{importacoes, variacao_estoque, ratio}`; CC05 `{mad, status, digitos_desviantes}`; CC06 `{outliers, media, desvio_padrao}`; CC07 `{ativo_circulante, passivo_circulante, liquidez}`; CC08 `{ebitda, receita_liquida, margem_pct}`. 🔒 (valores financeiros).

**Fronteiras (🌐)**
- 🌐 In-process: `analyze_benford()` (benford.py), `compute_zscore()` (zscore.py).
- `public_data` é pré-buscado externamente (CAGED/SICONFI/PNCP) — consumido, não buscado aqui.

### `services/audit/benford.py` — `analyze_benford` + `BenfordResult`

**Entradas**
- `analyze_benford(values: list[float], column: str = "")` — 🔒 série financeira mensal.
- Constantes: `BENFORD_EXPECTED[d] = log10(1 + 1/d)` para `d ∈ {1..9}`; `MAD_CONFORME=0.006`; `MAD_SUSPEITO=0.012`; `DESVIO_DIGITO_THRESHOLD=0.015`; `MIN_VALORES=30`.

**Intermediário (⚙)**
- ⚙ `_first_significant_digit(value)` — normaliza `abs(value)` para `[1,10)`; retorna `None` para 0/NaN/Inf (**valores descartados**).
- ⚙ `digits` — lista de primeiros dígitos (None filtrados, 2 passes).
- ⚙ `n = len(digits)`; `ValueError` se `n < 30`.
- ⚙ `counts: dict[int,int]` (1–9).
- ⚙ `observed[d] = counts[d]/n`.
- ⚙ `mad = sum(abs(observed[d]-BENFORD_EXPECTED[d]) for d in 1..9)/9`.
- ⚙ `status`: `mad < 0.006` → `CONFORME`; `< 0.012` → `MARGINAL`; senão `SUSPEITO`.
- ⚙ `deviating` — dígitos com `abs(observed[d]-expected[d]) > 0.015`.

**Saídas**
- `BenfordResult{n_values, observed (round 6), expected (round 6), mad (round 6), status, deviating_digits, column}`.

**Fronteiras (🌐)** — nenhuma (cálculo em memória).

### `services/audit/zscore.py` — `compute_zscore` + `ZScoreResult`

**Entradas**
- `compute_zscore(values: list[float|None], column="", threshold=3.0)` — 🔒 série financeira.

**Intermediário (⚙)**
- ⚙ `indexed = [(i,v) ...]` — filtra `None` e `NaN` (**descartados**).
- ⚙ `n = len(indexed)`; `ValueError` se `n < 2`.
- ⚙ `mean = sum(vals)/n`.
- ⚙ `variance = sum((v-mean)**2)/n` (populacional); `std = sqrt(variance)`.
- ⚙ `z = (v-mean)/std` por entrada; outlier se `abs(z) > threshold`. Se `std == 0`, nenhum outlier.

**Saídas**
- `ZScoreResult{column, n_values, mean (round 4), std (round 4), outliers, threshold}`.
- `outliers`: lista de `{"index": idx, "value": v, "zscore": round(z,4)}`. 🔒 (`value`).

**Fronteiras (🌐)** — nenhuma.

### `services/audit/anomaly/detector.py` — `AnomalyDetector`

**Entradas**
- `__init__(contamination=0.05, n_clusters=8)`.
- `fit(X_train: np.ndarray)` — 🔒 matriz histórica de features contábeis.
- `detect(features: np.ndarray)` — vetor de features de um caso.

**Intermediário (⚙)**
- ⚙ `iso_forest = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)`.
- ⚙ `fallback = MiniBatchKMeans(n_clusters=n_clusters, random_state=42)`.
- ⚙ `train_distances = fallback.transform(X_train).min(axis=1)`.
- ⚙ `percentile = (1.0 - contamination) * 100`.
- ⚙ `_fallback_threshold = percentile(train_distances, percentile)` (float).
- ⚙ `_is_fitted` (bool); `RuntimeError` em `detect()` sem `fit()`.
- ⚙ `x = features.reshape(1, -1)`.
- ⚙ Path primário: `score = iso_forest.decision_function(x)[0]`; `is_anomaly = iso_forest.predict(x)[0] == -1`; `method = "isolation_forest"`.
- ⚙ Path fallback (exceção): `dist = fallback.transform(x).min(axis=1)[0]`; `is_anomaly = dist > _fallback_threshold`; `score = _fallback_threshold - dist`; `method = "kmeans_fallback"`.

**Saídas**
- `detect()` → `{"anomaly_score": score, "is_anomaly": is_anomaly, "method": method}`.
- `fit()` → `self` (encadeável).

**Fronteiras (🌐)** — nenhuma direta; `fit()` deve rodar em Celery Beat (não por request).

### `services/audit/__init__.py`
- Marcador de pacote. Sem dados.

> **Nota de origem (DRE)** — `financials`/séries consumidos por `CrossCheckEngine` são produzidos por `_parse_dre_csv` em `services/gateway/routers/contabilia.py`: `FINANCIAL_FIELDS = {receita_liquida, headcount, ativo_circulante, passivo_circulante, ebitda, importacoes, variacao_estoque, receita_servicos_publicos}`; linhas `conta` iniciando com `receita_mensal` → `serie_receitas_mensais`; `despesa_mensal` → `serie_despesas_mensais`. Linhas com `valor` não-numérico são ignoradas silenciosamente. 🔒 `MAX_FILE_SIZE = 5 MB`.

---

## ComplianceRadar (compliance)

### `services/compliance/monitor.py` — `MunicipioIndicadores`, `evaluate_municipio`, `build_indicadores_from_cache`

**Entradas**
- `MunicipioIndicadores` (dataclass): `cod_ibge: str`, `referencia: str` (`"YYYY-MM"`), `delta_arrecadacao_yoy: float|None`, `delta_emprego_yoy: float|None`, `cobertura_agua_pct: float|None`, `cobertura_esgoto_pct: float|None`, `idhm: float|None`, `pib_per_capita: float|None`, `source_lag_days: int = -1`, `source_date: str|None`, `sources_missing: list[str]|None`.
- `build_indicadores_from_cache(cod_ibge, referencia, siconfi_atual, siconfi_anterior, caged_atual, caged_anterior, snis)` — dicts vindos de cache Redis (todos podem ser `None`).

**Intermediário (⚙)**
- ⚙ `_map_severity(raw)` → `Severity` (default `MEDIUM`).
- ⚙ `_map_channels(raw)` → `list[Channel]` (filtra desconhecidos).
- ⚙ **Regra `arrecadacao_critica`** (`_eval_arrecadacao_critica`): `delta_arrecadacao_yoy < -0.20 AND delta_emprego_yoy < -0.10` (False se algum `None`).
- ⚙ **Regra `saneamento_baixo`** (`_eval_saneamento_baixo`): `cobertura_agua_pct < 50.0 AND cobertura_esgoto_pct < 30.0`.
- ⚙ `_RULE_EVALUATORS` = mapa `rule_id → função`.
- ⚙ `occurred_at = datetime.now(UTC)`.
- ⚙ `dedup_key = f"{rule_id}:{cod_ibge}:{referencia}"`.
- ⚙ `alert_id = str(uuid.uuid5(uuid.NAMESPACE_OID, dedup_key))` — **determinístico** (idempotência ON CONFLICT DO NOTHING).
- ⚙ `payload` montado condicionalmente: sempre `cod_ibge`, `referencia`, `source_lag_days`; opcionalmente `delta_arrecadacao_yoy` (round 4), `delta_emprego_yoy` (round 4), `cobertura_agua_pct` (round 2), `cobertura_esgoto_pct` (round 2), `sources_missing`.
- ⚙ `build_indicadores_from_cache`: `delta_arr = (v_atual - v_ant)/abs(v_ant)` de `siconfi.get("valor")` (só se `v_ant != 0`); `delta_emp = (s_atual - s_ant)/base` de `caged.get("saldo_admissoes_desligamentos")`, `base = abs(s_ant) or 1`; `cob_agua/cob_esgoto` de `snis`; `lag = snis.get("lag_days", -1)`; `source_date = snis.get("source_date")`; `sources_missing` acumula `"SICONFI"/"CAGED"/"SNIS"` ausentes.

**Saídas**
- `evaluate_municipio(ind)` → `list[AlertEnvelope]`.
- `AlertEnvelope{schema_version="alerts/v1", alert_id, dedup_key, rule_id, severity, subject_ref={"municipio_ibge": cod_ibge}, payload, channels, occurred_at, enrichment}`.
- `build_indicadores_from_cache` → `MunicipioIndicadores`.

**Fronteiras (🌐)**
- 🌐 **AlertEnvelope** produzido aqui → publicado via `AlertPublisher` (Python↔Elixir, fila/webhook). `subject_ref` sem PII (usa `municipio_ibge`).
- 🌐 **Redis** (leitura upstream): dicts `siconfi_*`, `caged_*`, `snis` originam de cache com prefixos `siconfi:`, `caged:`/`ibge:`, `snis:` (consumidos por `build_indicadores_from_cache`).

### `services/compliance/rules.py` — `ALERT_RULES`

**Entradas / Saídas (constante de configuração)**
- `ALERT_RULES` (lista de 2 regras):
  - `arrecadacao_critica`: `name="Queda critica de arrecadacao"`, `condition="delta_arrecadacao_yoy < -0.20 AND delta_emprego_yoy < -0.10"`, `severity="CRITICAL"`, `cooldown_hours=24`, `enrichment=True`, `channels=["webhook","email","slack"]`.
  - `saneamento_baixo`: `name="Cobertura de saneamento critica"`, `condition="cobertura_agua < 50 AND cobertura_esgoto < 30"`, `severity="HIGH"`, `cooldown_hours=720`, `enrichment=False`, `channels=["webhook"]`.

### `services/compliance/__init__.py`
- Marcador de pacote. Sem dados.

---

## ConciliaIA (concilia)

### `services/concilia/recommender.py` — `recommend_settlement`

**Entradas**
- `recommend_settlement(request: ConciliaRequest, probability_favorable: float|None = None, risk_score_reu: int|None = None)`.
- 🔒 `ConciliaRequest{descricao (20–2000), valor_causa (>0), tipo_acao: TipoAcao, cnpj_reu (^\d{14}$), cnpj_autor (^\d{14}$)}`.
- `probability_favorable` — P(procedência) TaxPredict (0.0–1.0).
- `risk_score_reu` — LegalScore do réu (0–1000).
- Constantes/priors: `_BASE_PCT = {TRABALHISTA 0.55, CIVEL 0.45, TRIBUTARIO 0.35, PREVIDENCIARIO 0.65, ADMINISTRATIVO 0.40, CONSUMERISTA 0.50}`; `_PCT_NEUTRO=0.45`; `_CI_SPREAD=0.30`; `_PCT_MIN=0.05`; `_PCT_MAX=0.95`.

**Intermediário (⚙)**
- ⚙ `tipo = request.tipo_acao.value`; `base_pct = _BASE_PCT.get(tipo, _PCT_NEUTRO)`.
- ⚙ Fator prior: `impacto = round(base_pct - _PCT_NEUTRO, 3)`.
- ⚙ `pct = base_pct` (acumulador).
- ⚙ Ajuste TaxPredict: `delta = (probability_favorable - base_pct) * 0.5`; `pct += delta`; fator `impacto=round(delta,3)`.
- ⚙ Ajuste LegalScore: `risk_norm = risk_score_reu/1000.0`; `risk_delta = (risk_norm - 0.5) * 0.10` (±5%); `pct += risk_delta`; fator `impacto=round(risk_delta,3)`.
- ⚙ Clamp: `pct = max(_PCT_MIN, min(_PCT_MAX, pct))`.
- ⚙ 🔒 `valor_sugerido = request.valor_causa * pct`.
- ⚙ 🔒 `valor_minimo = valor_sugerido * (1 - 0.30)` (0.70×).
- ⚙ 🔒 `valor_maximo = min(request.valor_causa, valor_sugerido * (1 + 0.30))` (1.30×, teto = valor da causa).
- ⚙ `computed_at = datetime.now(UTC).isoformat()`.

**Saídas**
- `ConciliaResponse{valor_minimo (round 2), valor_sugerido (round 2), valor_maximo (round 2), percentual_causa (round 4), fatores: list[ConciliaFator], risco_reu, probabilidade_procedencia, computed_at, contract_version="concilia/v1"}`. 🔒 valores.
- `ConciliaFator{nome, impacto (−1.0..1.0), descricao}` — até 3 fatores: `"Prior histórico"`, `"Probabilidade de procedência"`, `"Risco do réu (LegalScore)"`.

**Fronteiras (🌐)**
- 🌐 **Cross-service in-process (TaxPredict)**: no router `services/gateway/routers/concilia.py`, `_get_taxpredict()` importa `_get_model` do router taxpredict, chama `model.predict(features)` (via `extract_features`) e extrai `result.get("probability")` → alimenta `probability_favorable`. Degradação graciosa (retorna `None` se offline). Modelo é o trace MinIO `gold/taxpredict/*.nc`.
- 🌐 **Redis (LegalScore)**: `_get_legalscore(cnpj)` lê 🔒 chave `score:{cnpj}` via `get_redis()`, `json.loads(raw).get("score")` → `risk_score_reu`. Degradação graciosa.

### `services/concilia/__init__.py`
- Marcador de pacote. Sem dados.

---

*Contratos de referência lidos: `services/shared/contracts/concilia.py` (ConciliaRequest/Fator/Response), `services/shared/contracts/alerts.py` (AlertEnvelope, Severity, Channel, PublishReceipt, AlertPublisher).*
