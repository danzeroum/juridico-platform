# 06 — Ingest (medalhão bronze/silver, 14 fontes)

Catálogo exaustivo de fluxo de dados de `services/ingest/`. Arquitetura **medalhão**:
`Entradas` (API gov / args da task) → **bronze** (dict cru + linage, validado por
contrato Pydantic) → **silver** (transform + features) → `Saídas` (Redis / OpenSearch
/ Neo4j / MinIO / Postgres). LGPD: pseudonimização HMAC-SHA256 **antes** de qualquer
persistência.

**Legenda:** ⚙ = intermediário (dict bronze cru, linhas descartadas, valores em
quarentena) · 🔒 = PII (cpf/nome) · 🌐 = fronteira (API gov HTTP, broker Celery,
serialização medalhão).

---

## Índice de contratos (14 fontes) e tasks

| # | Contrato | Bronze / Silver models | Task(s) |
|---|----------|------------------------|---------|
| 1 | datajud | `DatajudProcessoBronze` / `DatajudProcessoSilver` | `tasks/datajud.py` |
| 2 | caged | `CagedEstabelecimentoBronze` / `CagedEstabelecimentoSilver` | `tasks/caged.py` |
| 3 | ibge | `IbgeMunicipioBronze` / `IbgeMunicipioSilver` | `tasks/ibge.py` |
| 4 | pncp | `PncpContratoBronze` / `PncpContratoSilver` | `tasks/pncp.py` |
| 5 | receita | `ReceitaCnpjBronze` / `ReceitaCnpjSilver` | `tasks/receita.py`, `tasks/receita_cnpj.py` |
| 6 | pgfn | `PgfnDevedorBronze` / `PgfnDevedorSilver` | `tasks/pgfn.py` |
| 7 | siconfi | `SiconfiContaBronze` / `SiconfiContaSilver` | `tasks/siconfi.py` |
| 8 | snis | `SnisMunicipioBronze` / `SnisMunicipioSilver` | (sem task no escopo) |
| 9 | abj | `AbjIndicadorBronze` / `AbjIndicadorSilver` | `tasks/abj.py` |
| 10 | confaz | `ConfazRegraBronze` (só bronze) | `tasks/confaz_ocr.py`, `tasks/confaz_discovery.py` |
| 11 | sefaz | `SefazAliquotaBronze` (só bronze) | `tasks/sefaz_scraper.py` |
| 12 | tipi | `TipiBronze` (só bronze) | `tasks/rfb_tipi.py` |
| — | (bcb) | sem contrato Pydantic (dict cru) | `tasks/bcb.py` |
| — | (consumidor_gov) | sem contrato Pydantic (agregação) | `tasks/consumidor_gov.py` |
| — | (transparencia) | stub | `tasks/transparencia.py` |
| — | (jurimetria_agg) | consome DATAJUD+ABJ silver | `tasks/jurimetria_aggregate.py` |
| — | (ncm_history) | dict cru → fiscal.ncm_migracao | `tasks/ncm_history.py` |

---

## pipeline/base.py — helpers de linhagem, circuit breaker, sink 3-store

### Funções de linhagem / reconciliação
- **`add_linage(record, source, transform_version="1.0.0")`** → adiciona 3 campos:
  `source=<source>`, `ingested_at=datetime.now(UTC).isoformat()`, `transform_version`.
  Chamado ANTES do bronze por todas as tasks.
- **`compute_lag_days(data_source_date)`** → `(date.today() - source_date).days`;
  `-1` se data inválida. Indicador de staleness.
- **`reconcile(source, records_in, records_out, date_str)`** → dict de saída:
  `{source, date, records_in, records_out, loss_pct, reconciled_at}` onde
  `loss_pct = round((1 - records_out/records_in)*100, 2)` (0.0 se `records_in==0`).
- **`safe_log1p(value)`** → `math.log1p(value)`; `0.0` se `None` ou `< 0`.

### CircuitState / CircuitBreaker
- **`CircuitState`** (StrEnum): `CLOSED` (deixa passar) · `OPEN` (bloqueia por
  `recovery_timeout`) · `HALF_OPEN` (testando recuperação).
- **`CircuitBreaker(name, failure_threshold=5, recovery_timeout=300.0)`**; estado interno
  `_state`, `_failure_count`, `_opened_at`.
  - `state` (property): se `OPEN` e `time.monotonic()-_opened_at >= recovery_timeout` → transiciona `OPEN→HALF_OPEN`.
  - `record_success()` → zera contador, `→CLOSED`, `_opened_at=None`.
  - `record_failure()` → `_failure_count += 1`; se `HALF_OPEN` ou `>=failure_threshold` → `OPEN`, `_opened_at=time.monotonic()`.
  - `is_open()` → `state == OPEN`.
- **`get_circuit_breaker(source)`** → singleton por processo Celery via dict `_breakers`.

### persist_silver — sink DRY de 3 stores 🌐
`persist_silver(source, date_str, bronze_records, silver_records, *, opensearch_index=None, graph_writer=None, id_field="id_processo")` → retorna
`counts = {source, date, bronze, opensearch, graph, errors[]}`.
- **1. Bronze → MinIO** 🌐: `put_jsonl(source, date_str, bronze_records)`.
- **2. Silver → OpenSearch** 🌐: `bulk_index(opensearch_index, silver_records, id_field=id_field)` (só se `opensearch_index`).
- **3. Grafo → Neo4j** 🌐: `graph_writer(silver_records)` (só DATAJUD passa `upsert_process_edges`; demais passam `None`).
- **Degradação graciosa:** cada store isolado em `try/except`; falha é logada + anexada a `errors[]` (`minio:…` / `opensearch:…` / `graph:…`), nunca aborta os demais.
- 🔒 **LGPD:** `silver_records`/`bronze_records` devem chegar **já pseudonimizados**; o sink não toca PII, só grava.

**Detalhe dos sinks subjacentes (services/shared/storage):**
- `put_jsonl` → bucket `bronze-<source.lower()>`, key `dt=<YYYY-MM-DD>/part-<uuid.hex>.jsonl`, JSONL (`application/x-ndjson`); retorna `"{bucket}/{key}"`, `None` se vazio.
- `bulk_index` → API `_bulk`; `_id = str(doc[id_field])`; erros parciais logados, sem exceção; retorna `len(docs)`.
- `upsert_process_edges` → Cypher `UNWIND $rows … MERGE (:Processo {id}) SET tribunal,classe=classe_tpu,assunto=assunto_tpu,ramo,data_julgamento,valor_log; WHERE cnpj_parte NOT NULL MERGE (:Empresa {cnpj})-[:PARTE_EM]->(p)`.

---

## pipeline/quality.py — transforms bronze→silver de qualidade

Etapas: validação (Pydantic, no contrato) → faltantes → outliers de higiene →
normalização de strings → derivação de features (log1p, idade, recência).

Funções unitárias:
- **`treat_missing_valor_causa`** → `valor_causa=None` vira `0.0` + flag `valor_causa_imputado=True/False`.
- **`remove_outliers_valor(max_valor=1e12)`** → `valor_causa > 1e12` → `None` + `valor_causa_outlier=True` (>1 trilhão = erro de dado). ⚙ valor em quarentena.
- **`add_valor_log`** → `valor_log = safe_log1p(valor_causa)`.
- **`add_recencia(date_field="data_julgamento")`** → `recencia_dias = (hoje - source_date).days`; `recencia = -lag/365.0` (mais recente = valor maior); `None/0.0` se ausente/inválido.
- **`normalize_cnpj_part`** → campos `cnpj`,`cnpj_parte`: só dígitos, `None` se `len != 14`.

### datajud_bronze_to_silver(bronze, pseudonymized)
`silver = dict(pseudonymized)` → `remove_outliers_valor` → `treat_missing_valor_causa`
→ `add_valor_log` → `add_recencia(data_julgamento)`. Normalização TPU:
- `classe_tpu, classe_label = normalize_classe(bronze.classe)` (código canônico + label).
- `assunto_tpu, assunto_label = normalize_assunto(bronze.assunto)`.
- `ramo = assunto_ramo(bronze.assunto)` (TRABALHISTA|TRIBUTARIO|CONSUMIDOR|CIVEL|EMPRESARIAL|OUTRO).
- Preserva `ingested_at`, `transform_version` do bronze.

### pgfn_bronze_to_silver(bronze)
- `valor = valor_total_divida or 0.0`; `valor_divida_log = safe_log1p(valor)`;
  `tem_divida_ativa = valor > 0`; `quantidade_debitos = … or 0`; `tipo_devedor = (… or "PJ").upper()`.

### receita_bronze_to_silver(bronze)
- `capital = capital_social or 0.0`; `capital_social_log = safe_log1p(capital)`;
  `esta_ativa = situacao_cadastral == "ATIVA"`; `porte = (… or "DESCONHECIDO").upper()`;
  `idade_empresa_anos = round((hoje - data_abertura).days / 365.25, 1)` (None se ausente/inválido).

---

## Contrato 1 — datajud (`contracts/datajud.py`) 🔒

**Entradas:** dict cru do CNJ (`items[]`), campo `data_source_lag_days` injetado pela task.

### `DatajudProcessoBronze` (bronze)
Obrigatórios: `id_processo:str(min_len1)`, `numero_processo:str(min_len1)`,
`data_julgamento:str` (validator `date.fromisoformat`), `tribunal:str(min_len2)` (validator `.upper().strip()`).
Opcionais: `materia`, `resultado`, `valor_causa:float`, `classe`, `assunto` (código TPU CNJ).
🔒 **PII (pseudonimizado antes de storage):** `parte_cpf`, `cpf_autor`, `cpf_reu`, `parte_nome`, `nome_autor`, `nome_reu`.
Público: `cnpj_parte` (validator: só dígitos, exige 14 → senão `ValueError`).
Linage: `source="DATAJUD"`, `ingested_at`, `transform_version="1.0.0"`, `data_source_lag_days:int|None`.

### `DatajudProcessoSilver` (silver)
`id_processo`, `numero_processo`, `data_julgamento:date`, `tribunal`, `materia`,
`resultado_normalizado` (validator `mode=before`: contém PROVIM/DADO PROVIM→`PROVIMENTO`; NEGAD/IMPROVID→`NEGADO`; PARCIAL→`PARCIAL`; senão `OUTRO`),
`valor_causa`, `valor_log=log1p(valor_causa)`, `cnpj_parte`.
TPU: `classe_tpu`, `classe_label`, `assunto_tpu`, `assunto_label`, `ramo`.
🔒 **PII → hashes HMAC:** `parte_cpf_hash`, `cpf_autor_hash`, `cpf_reu_hash`, `parte_nome_hash`, `nome_autor_hash`, `nome_reu_hash`.
Linage: `source`, `ingested_at`, `transform_version`, `data_source_lag_days`.

- **⚙ Intermediário:** dict `with_linage`, registros rejeitados por schema.
- **Saídas:** ver task datajud.

---

## Contrato 2 — caged (`contracts/caged.py`)

**Entradas:** dict cru MTE por estabelecimento.

### `CagedEstabelecimentoBronze`
`competencia:str` (validator `strptime("%Y-%m")`), `cnpj_estabelecimento:str(14)` (validator `isdigit`),
`uf:str(2)` (validator `.upper()`), `municipio:str(min1)`, `secao_cnae:str(1)` (validator ∈ `ABCDEFGHIJKLMNOPQRSTU` → senão `ValueError`),
`saldo_admissoes_desligamentos:int`, opcionais `admissoes`, `desligamentos`, `salario_medio:float`, `grau_instrucao`, `categoria`.
Linage: `source="CAGED"`, `ingested_at` (ISO UTC), `transform_version`.

### `CagedEstabelecimentoSilver`
`competencia`, `cnpj_estabelecimento`, `uf`, `municipio`, `secao_cnae`,
`saldo_admissoes_desligamentos`, `admissoes` (bronze or 0), `desligamentos` (or 0),
`salario_medio_normalizado` (=`salario_medio or 0.0`), **`is_crescendo = saldo > 0`**.
Transform inline em `tasks/caged.py::_bronze_to_silver`.

---

## Contrato 3 — ibge (`contracts/ibge.py`)

**Entradas:** indicadores socioeconômicos por município (SIDRA/IBGE Cidades).

### `IbgeMunicipioBronze`
`cod_ibge:str(7)` (validator `isdigit`), `municipio:str(min1)`, `uf:str(2)` (`.upper()`),
`ano:int (2000..2100)`, `populacao:int(≥0)`, opcionais `pib_per_capita:float`,
`idhm:float(0..1)`, `taxa_desemprego:float(0..100)`, `area_km2:float(≥0)`, `source_date:str`.
Linage: `source="IBGE"`, `ingested_at`, `transform_version`.

### `IbgeMunicipioSilver` (via `ibge_bronze_to_silver`)
`cod_ibge`, `municipio`, `uf`, `ano`, `populacao`, `pib_per_capita` (or 0.0),
`idhm` (or 0.0), `taxa_desemprego` (or 0.0),
**`densidade_demografica = round(populacao / area_km2, 2)`** (0.0 se área ausente/0),
`source_date`, **`lag_days = (now - source_date).days`** (-1 se inválido). Linage preservada.

---

## Contrato 4 — pncp (`contracts/pncp.py`)

**Entradas:** contrato bruto por órgão/exercício da API PNCP.

`Modalidade` (StrEnum): PREGAO_ELETRONICO/PRESENCIAL, CONCORRENCIA, TOMADA_PRECOS,
CONVITE, DISPENSA, INEXIGIBILIDADE, LEILAO, OUTRA. `_MODALIDADES_DISPENSA = {DISPENSA, INEXIGIBILIDADE}`.

### `PncpContratoBronze`
`numero_controle:str(min1)`, `cnpj_orgao:str` (pattern `^\d{14}$`), `cnpj_fornecedor:str|None` (validator `isdigit`),
`objeto:str(min1)`, `modalidade:Modalidade`, `valor_contrato:float(≥0)`,
`data_publicacao:str`, `data_abertura:str|None`, `num_propostas:int|None(≥0)`. Linage `source="PNCP"`.

### `PncpContratoSilver` (via `pncp_bronze_to_silver`)
`numero_controle`, `cnpj_orgao`, `cnpj_fornecedor`, `objeto`, `modalidade` (`.value`),
`valor_contrato`, **`valor_log = round(log10(valor_contrato + 1), 4)`**,
`data_publicacao`, **`prazo_abertura_dias = (data_abertura - data_publicacao).days`** (None se inválido),
**`is_dispensa = modalidade ∈ {DISPENSA, INEXIGIBILIDADE}`**, **`is_unico_proponente = num_propostas == 1`**. Linage.

---

## Contrato 5 — receita (`contracts/receita.py`)

**Entradas:** CNPJ público da Receita (API `publica.cnpj.ws`). Sem PII individual (CNPJ PJ é público, LGPD art. 7º IV).
`SITUACOES_VALIDAS = {ATIVA, BAIXADA, INAPTA, SUSPENSA, NULA}`.

### `ReceitaCnpjBronze`
`cnpj:str` (validator: só dígitos, 14), `razao_social:str(min1)`,
`situacao_cadastral` (validator `.upper().strip()` ∈ SITUACOES_VALIDAS → senão `ValueError`),
`data_situacao_cadastral`, `porte`, `natureza_juridica`, `capital_social:float(≥0)`,
`data_abertura` (validator `date.fromisoformat`), `municipio`, `uf` (validator `.upper().strip()`),
`cnaes_secundarios:list[str]`, `cnae_fiscal`. Linage `source="RECEITA"`.

### `ReceitaCnpjSilver`
`cnpj`, `razao_social`, `situacao_cadastral`, `data_situacao_cadastral:date`, `porte="DESCONHECIDO"`,
`natureza_juridica`, `capital_social=0.0`, **`capital_social_log=log1p(capital_social)`**,
`data_abertura:date`, **`idade_empresa_anos`** (feature), `municipio`, `uf`, `cnae_fiscal`,
**`esta_ativa`** (=situacao=="ATIVA"). Transform em `pipeline/quality.py::receita_bronze_to_silver`.

---

## Contrato 6 — pgfn (`contracts/pgfn.py`)

**Entradas:** Dívida Ativa da União por CNPJ. CNPJ público; valores = risco, não PII.

### `PgfnDevedorBronze`
`cnpj:str` (validator só dígitos 14), `situacao:str` (validator `.upper().strip()`),
`valor_total_divida:float|None(≥0)`, `quantidade_debitos:int|None(≥0)`,
`data_inscricao` (validator `date.fromisoformat`), `tipo_devedor:str|None` (PJ|PF). Linage `source="PGFN"`.

### `PgfnDevedorSilver` (via `pgfn_bronze_to_silver`)
`cnpj`, `situacao`, `valor_total_divida=0.0`, **`valor_divida_log=log1p(valor_total_divida)`**,
`quantidade_debitos=0`, `data_inscricao:date`, `tipo_devedor="PJ"`, **`tem_divida_ativa = valor > 0`**.

---

## Contrato 7 — siconfi (`contracts/siconfi.py`)

**Entradas:** entrada contábil municipal (API STN Tesouro).

### `SiconfiContaBronze`
`cod_ibge:str(7)` (validator `isdigit`), `uf:str(2)` (`.upper()`), `municipio:str(min1)`,
`exercicio:int(2000..2100)`, `conta:str(min1)` (validator `.strip()`), `valor:float`,
`descricao_conta`, `periodicidade`, `periodo`. Linage `source="SICONFI"`.

### `SiconfiContaSilver` (via `siconfi_bronze_to_silver`)
`cod_ibge`, `uf`, `municipio`, `exercicio`, `conta`, `descricao_conta` (or ""), `valor`,
**`valor_log = round(log1p(abs(valor)), 6)`**, **`is_despesa = conta.startswith(("3","4"))`**,
`periodicidade` (or "ANUAL"), `periodo` (or "A").

---

## Contrato 8 — snis (`contracts/snis.py`) — sem task no escopo

**Entradas:** indicadores de saneamento por município. Lag médio ~548 dias.

### `SnisMunicipioBronze`
`cod_ibge:str(7)` (validator `isdigit`), `municipio:str(min1)`, `uf:str(2)` (`.upper()`),
`exercicio:int(2000..2100)`, `populacao_total:int(≥0)`, `populacao_atendida_agua:int(≥0)`,
`populacao_atendida_esgoto:int(≥0)`, `volume_agua_produzido:float`, `volume_esgoto_coletado:float`,
`source_date`. Linage `source="SNIS"`.

### `SnisMunicipioSilver` (via `snis_bronze_to_silver`)
`cod_ibge`, `municipio`, `uf`, `exercicio`, `populacao_total`,
**`cobertura_agua_pct = round(min(pop_agua/pop*100, 100.0), 2)`** (0.0 se pop≤0),
**`cobertura_esgoto_pct = round(min(pop_esgoto/pop*100, 100.0), 2)`**,
`source_date`, **`lag_days = (now - source_date).days`** (-1 inválido).

---

## Contrato 9 — abj (`contracts/abj.py`)

**Entradas:** linha CSV de dataset abjData/observatório. Ingestão DESLIGADA por padrão (`ABJ_ENABLED=false`).

### `AbjIndicadorBronze`
`tribunal:str(min2)` (validator `.upper().strip()`), `periodo:str(min4)` (YYYY|YYYY-Qn|YYYY-MM),
`classe_cnj`, `assunto_cnj`, `tempo_medio_dias:float`,
`taxa_congestionamento:float` (validator: deve estar em `[0,1]` → senão `ValueError`),
`casos_novos:int`, `casos_baixados:int`, `casos_pendentes:int`. Linage `source="ABJ"`.

### `AbjIndicadorSilver` (via `abj_bronze_to_silver`)
Passa todos os campos; deriva **`taxa_congestionamento`** quando ausente pela fórmula Justiça em Números:
`round(casos_pendentes / (casos_baixados + casos_pendentes), 4)` (None se denom≤0).

---

## Contrato 10 — confaz (`contracts/confaz.py`)

**Entradas:** regra fiscal candidata extraída de PDF CONFAZ por OCR/LLM. Só bronze — **nunca persiste alíquota direto** (`needs_review=True` → validação humana).

### `ConfazRegraBronze`
`ncm:str` (validator: `re.sub(\D)`, pattern `^\d{8}$` → senão `ValueError`),
`aliquota_pct:float|None(0..35)`, `uf_origem`/`uf_destino` (validator `.strip().upper()`),
`vigencia_inicio:str` (DD/MM/AAAA cru), `ato_ref`, `needs_review=True`. Linage `source="CONFAZ"`.

---

## Contrato 11 — sefaz (`contracts/sefaz.py`)

**Entradas:** alíquota interna ICMS raspada de portal SEFAZ estadual. Só bronze.
`_UFS` = 27 UFs válidas.

### `SefazAliquotaBronze`
`uf:str` (validator ∈ `_UFS` → senão `ValueError`), `produto:str(min1)`, `ncm_prefix:str|None` (validator: só dígitos ou None),
`aliquota_pct:float(0..35)` (**fora da faixa → quarentena via ValidationError**), `fcp_pct:float|None(0..10)`, `fundamento_legal`. Linage `source="SEFAZ"`.

---

## Contrato 12 — tipi (`contracts/tipi.py`)

**Entradas:** linha do CSV oficial TIPI (RFB). Sem PII.

### `TipiBronze`
`ncm_codigo:str` (validator: dígitos, pattern `^\d{8}$` → senão `ValueError`),
`descricao:str(min1)`, `aliquota_ipi:float|None(0..400)`, `excecao:str|None` (campo EX),
`capitulo:str|None`. `model_validator(after)`: **`capitulo = ncm_codigo[:2]`** se ausente. Linage `source="TIPI"`.

---

# TASKS

## Task datajud (`tasks/datajud.py`) — `run_daily_ingest` — queue `daily` 🔒

- **Entradas:** arg `date:str|None` (default = ontem UTC). CB `DATAJUD` (`failure_threshold=5`).
- **🌐 API:** `GET {DATAJUD_API_URL}/processos?data_julgamento=<date>`, `timeout=30`, header `Authorization: APIKey {DATAJUD_TOKEN}`. Resposta JSON `{items:[…]}`. Contrato: `DatajudProcessoBronze`.
- **Fluxo por item:** `add_linage(source="DATAJUD")` + `data_source_lag_days=compute_lag_days(date)` → `_validate_bronze` (rejeita None) → 🔒 `pseudonymize_process_record(bronze.model_dump())` (HMAC ANTES de storage) → `datajud_bronze_to_silver(bronze, pseudo)` → acumula `bronze_batch`(=pseudo) + `silver_batch`.
- **⚙ Intermediário:** `data` cru; `items[]`; `bronze_batch`/`silver_batch`; `rejected` (schema).
- **Saídas:**
  - Redis `setex datajud:{date}` TTL **48h** (`48*3600`) = cache da resposta bruta (fallback).
  - `persist_silver(source="DATAJUD", opensearch_index="datajud-silver-{date[:7]}", graph_writer=upsert_process_edges, id_field="id_processo")`:
    - 🌐 MinIO `bronze-datajud/dt={date}/part-*.jsonl` (registros pseudonimizados).
    - 🌐 OpenSearch índice `datajud-silver-YYYY-MM`, `_id=id_processo`.
    - 🌐 Neo4j `(:Empresa{cnpj})-[:PARTE_EM]->(:Processo{id})`.
  - Retorna `{...reconcile, rejected, persist}`.
- **Fallback:** `DatajudUnreachable` → lê cache Redis `datajud:{date}`; se sem cache → `self.retry(countdown=3600)` (máx 5). CB OPEN levanta `DatajudUnreachable`.
- **🌐 Fronteiras:** API CNJ HTTP; broker Celery (`daily`); serialização medalhão (JSONL/bulk/Cypher).

## Task receita (`tasks/receita.py`) — `run_weekly_ingest` / `_single` — queue `weekly`

- **Entradas:** arg `cnpjs:list[str]|None` (vazio → `{status:"no_cnpjs"}`). CB `RECEITA`.
- **🌐 API:** `GET {RECEITA_API_URL}/{cnpj}` (`publica.cnpj.ws/cnpj`), `timeout=30`, `Accept: application/json`. `_normalize_receita_response` mapeia razao_social/nome, `descricao_situacao_cadastral`→`_map_situacao` (default ATIVA), `descricao_porte`/porte, `capital_social`, `data_inicio_atividade`, `natureza_juridica.descricao`, `municipio.descricao`, `cnae_fiscal_principal.codigo`, `cnaes_secundarios[].codigo`. Contrato `ReceitaCnpjBronze`.
- **Fluxo:** valida 14 dígitos (senão `rejected`) → cache Redis `receita:{digits}` → se ausente busca e `setex` TTL **7 dias** → `add_linage(source="RECEITA")` → `_validate_bronze` → `receita_bronze_to_silver`.
- **⚙ Intermediário:** `raw` normalizado; silver descartado (`_ = silver` — TODO Fase 1b: OpenSearch `receita-silver-YYYY-MM` + nó CNPJ Neo4j).
- **Saídas:** Redis `receita:{cnpj14}` TTL **604800s (7d)** = resposta bruta. `reconcile("RECEITA", …)`. **Sem** persist durável ainda.

## Task receita_cnpj (`tasks/receita_cnpj.py`) — `fetch_cnpj` (função pura, sem Celery/Redis)

- **Entradas:** arg `cnpj:str`. CB `RECEITA` (mesma chave do batch).
- **🌐 API:** `GET {RECEITA_API_URL}/{digits}`, `timeout=30`. `_normalize` (inclui `cnae_descricao`; `_map_situacao` **NÃO** assume ATIVA → `DESCONHECIDA`).
- **Saídas:** retorna dict cadastral normalizado ao gateway, ou `{}` em falha/CNPJ inválido/CB aberto (degradação graciosa). Sem sink.

## Task pgfn (`tasks/pgfn.py`) — `run_weekly_ingest` / `_single` — queue `weekly`

- **Entradas:** arg `cnpjs:list[str]|None` (vazio → `no_cnpjs`). CB `PGFN`.
- **🌐 API:** `GET {PGFN_API_URL}/situacao/{cnpj}` (`regularize.pgfn.gov.br/api`), `timeout=30`, `Accept: application/json`. Contrato `PgfnDevedorBronze`.
- **Fluxo:** cache Redis `pgfn:{cnpj}` → se ausente busca e `setex` TTL **7 dias** → `add_linage(source="PGFN")` → `_validate_bronze` → `pgfn_bronze_to_silver`.
- **⚙ Intermediário:** silver descartado (`_ = silver` — TODO Fase 1b: OpenSearch `pgfn-silver-YYYY-MM` + flag `tem_divida_ativa` no Neo4j).
- **Saídas:** Redis `pgfn:{cnpj}` TTL **604800s (7d)** = resposta bruta. `reconcile("PGFN", …)`.

## Task pncp (`tasks/pncp.py`) — `run_daily_ingest(cnpj_orgao, ano)` — Celery (bind, max_retries=3, delay=300)

- **Entradas:** args `cnpj_orgao:str`, `ano:int|None` (default ano atual). CB `pncp`. Paginação `tamanhoPagina=500`, máx 100 páginas.
- **🌐 API:** `PNCP_BASE_URL = https://pncp.gov.br/api/pncp/v1`; `GET /orgaos/{cnpj}/contratos?dataInicial={ano}-01-01&dataFinal={ano}-12-31&pagina=&tamanhoPagina=500`, `timeout=30`. Resposta `{data:[…], totalPaginas}`. `_raw_to_bronze_dict` mapeia `numeroControlePNCP/numeroPCE/numeroControle`, `niFornecedor`, `objetoContrato/objeto`, `modalidadeContratacao.nome`→`_map_modalidade`, `valorGlobal/valorContrato`, `dataPublicacaoPncp`, `dataAberturaPropostas`, `quantidadePropostasRecebidas`. Contrato `PncpContratoBronze` → `pncp_bronze_to_silver`.
- **⚙ Intermediário:** `items[]` por página; `bronze_dict` (None → rejected); `rejected` (ValidationError).
- **Saídas:** Redis `setex pncp:{cnpj_orgao}:{ano}:{numero_controle}` TTL **24h** (`60*60*24`) = **silver** `model_dump_json()`. `reconcile("PNCP", …) + {rejected, cnpj_orgao}`.

## Task caged (`tasks/caged.py`) — `run_monthly_ingest(competencia, cnpjs)` / `_single` — Celery (max_retries=3, delay=120)

- **Entradas:** args `competencia:str("YYYY-MM")`, `cnpjs:list[str]`. CB `caged`.
- **🌐 API:** `CAGED_BASE_URL = https://api.dados.gov.br/v1/conjuntos-dados/novo-caged`; `GET /estabelecimento?cnpj=&competencia=`, `timeout=30`. Resposta list ou `{data:[…]}`. Contrato `CagedEstabelecimentoBronze` → `_bronze_to_silver` (`is_crescendo=saldo>0`).
- **⚙ Intermediário:** `raw_list`; `rejected` (ValidationError/TypeError).
- **Saídas:** Redis `setex caged:{cnpj}:{competencia}` TTL **30 dias** (`60*60*24*30`) = **silver** `json.dumps(model_dump())`. Cache-hit conta como `records_out`. `reconcile("CAGED", …) + {rejected}`.

## Task siconfi (`tasks/siconfi.py`) — `run_monthly_ingest(cod_ibge, exercicio)` — Celery (max_retries=3, delay=120)

- **Entradas:** args `cod_ibge:str`, `exercicio:int`. CB `siconfi`.
- **🌐 API:** `SICONFI_BASE_URL = https://apidatalake.tesouro.gov.br/ords/siconfi/tt`; `GET /rreo?id_ente={cod_ibge}&an_exercicio={exercicio}&nr_periodo=6`, `timeout=30`. Resposta `{items:[…]}`. Injeta `cod_ibge`/`exercicio` em cada raw. Contrato `SiconfiContaBronze` → `siconfi_bronze_to_silver`.
- **⚙ Intermediário:** `raw_list`; `silver_list`; `rejected`.
- **Saídas:** Redis `setex siconfi:{cod_ibge}:{exercicio}` TTL **7 dias** (`60*60*24*7`) = **lista de silver** `json.dumps(silver_list)`. Cache-hit → `{status:"cached"}`. `reconcile("SICONFI", …) + {rejected}`.

## Task ibge (`tasks/ibge.py`) — funções puras + `run_ingest(uf)` — Celery (max_retries=3, delay=300)

- **Entradas:** arg `uf:str` (sigla 2 letras). CB `ibge`.
- **🌐 APIs IBGE** (`timeout=30`, sem auth):
  - `IBGE_LOCALIDADES = https://servicodados.ibge.gov.br/api/v1` — `GET /localidades/estados/{UF}/municipios` → `fetch_municipios` (`{cod_ibge, municipio, uf}`, ordenado).
  - `IBGE_AGREGADOS = https://servicodados.ibge.gov.br/api/v3` — `_fetch_n6_latest(agregado, variavel)` via `GET /agregados/{ag}/periodos/-1/variaveis/{var}?localidades=N6[{cod}]`.
  - `fetch_populacao` (ag 6579 / var 9324), `fetch_pib` (ag 5938 / var 37, mil reais), `fetch_area` (ag 1301 / var 615, km²), `fetch_cempre` (ag 1685 / vars 367|707|708 → empresas/pessoal_ocupado/pessoal_assalariado), `fetch_ipca` (ag 1737: var 2265 acumulado 12m / var 63 mensal, nível N1[all]).
  - Contrato `IbgeMunicipioBronze` → `ibge_bronze_to_silver`.
- **⚙ Intermediário:** `municipios[]`; `rejected` (ValidationError). `fetch_*` retornam `[]`/`{}`/`(None,None)` em falha (degradação graciosa).
- **Saídas:** Redis `setex ibge:{cod_ibge}` TTL **30 dias** (`60*60*24*30`) = **silver** `model_dump_json()`. `reconcile("IBGE", …) + {rejected, uf}`. `fetch_*` puras alimentam o gateway ao vivo.

## Task abj (`tasks/abj.py`) — `run_monthly_ingest(date)` — queue `monthly` (max_retries=3, delay=300)

- **Entradas:** arg `date:str|None`. No-op se `ABJ_ENABLED=false` (`{status:"disabled"}`). CB `ABJ`.
- **🌐 API:** `GET settings.ABJ_DATA_URL` (CSV, `timeout=60`) → `csv.DictReader`. Contrato `AbjIndicadorBronze` → `abj_bronze_to_silver`.
- **⚙ Intermediário:** `raw_list`; `silver_rows`; `rejected`.
- **Saídas:**
  - `persist_silver(source="ABJ", opensearch_index="abj-silver", graph_writer=None, id_field="tribunal")` → MinIO `bronze-abj/dt=…` + OpenSearch `abj-silver`.
  - **Postgres** `_upsert_landing` → `jurimetria.abj_indicador_raw` (colunas: `tribunal, classe_cnj, assunto_cnj, periodo, tempo_medio_dias, taxa_congestionamento, casos_novos, casos_baixados, casos_pendentes, source, transform_version`), `ON CONFLICT (tribunal, COALESCE(classe_cnj,''), COALESCE(assunto_cnj,''), periodo) DO UPDATE`. Engine global `get_engine()` (sem tenant).
  - `reconcile("ABJ", …) + {rejected, landed, persist}`.

## Task jurimetria_aggregate (`tasks/jurimetria_aggregate.py`) — `run_aggregation` — queue `monthly`

- **Entradas:** nenhuma (recomputa). Núcleo puro `build_indicador_rows(datajud_buckets, abj_rows)`.
- **🌐 Fronteiras/leitura:**
  - OpenSearch `_query_datajud_buckets("datajud-silver-*")` — agg aninhada por `tribunal → classe_tpu → assunto_tpu` + filtro `resultado_normalizado="PROVIMENTO"`; bucket = `{tribunal, classe_tpu, assunto_tpu, periodo="TODOS", n_processos, pct_provimento=round(prov/n,4)}`.
  - Postgres `_load_abj_rows` — `SELECT … FROM jurimetria.abj_indicador_raw`.
- **Merge:** DATAJUD bucket → linha `fonte="DATAJUD"`; match ABJ → linha `fonte="BLEND"` (duração/congestionamento da ABJ + volume DATAJUD); ABJ órfão → `fonte="ABJ"`.
- **Saídas:** Postgres upsert `jurimetria.indicador` (colunas: `tribunal, classe_tpu, assunto_tpu, periodo, fonte, n_processos, duracao_mediana_dias, duracao_p25_dias, duracao_p75_dias, taxa_congestionamento, taxa_litigiosidade, pct_provimento, source`), `ON CONFLICT (tribunal, classe_tpu, assunto_tpu, periodo, fonte) DO UPDATE`. Tabela GLOBAL (sem RLS). `reconcile("JURIMETRIA_AGG", …)`.

## Task consumidor_gov (`tasks/consumidor_gov.py`) — `run_ingest(url)` — Celery (max_retries=3, delay=300)

- **Entradas:** arg `url:str` (CSV dados abertos). CB `consumidor_gov`. Sem contrato Pydantic.
- **🌐 API:** `GET url` (`timeout=60`) → `parse_csv` (delimitador `;`, remove BOM) → `aggregate_reclamacoes` por `Nome Fantasia`.
- **Agregação por empresa:** `{empresa, total, respondidas, resolvidas, pct_resposta=round(respondidas/total,4), pct_resolucao=round(resolvidas/total,4), nota_media=round(mean,2)}`. `slugify` (NFKD ascii, minúsculo, alfanum).
- **⚙ Intermediário:** `agg` dict por slug.
- **Saídas:** Redis `setex consumidor:{slug}` TTL **30 dias** (`60*60*24*30`) = `json.dumps(data)`. `reconcile("CONSUMIDOR_GOV", …) + {empresas}`.

## Task bcb (`tasks/bcb.py`) — `fetch_serie` / `fetch_macro` (funções puras, sem Celery/Redis)

- **Entradas:** `codigo:int`, `n:int`. CB `bcb`. Sem contrato.
- **🌐 API:** `BCB_SGS = https://api.bcb.gov.br/dados/serie`; `GET /bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json`, `timeout=30`. Séries: `432`=Selic meta % a.a., `1`=câmbio USD venda. Resposta `[{data:"DD/MM/AAAA", valor:"X.XX"}]`.
- **Saídas:** `fetch_macro` retorna `{selic, selic_data, cambio_usd, cambio_data}` ao gateway (só campos disponíveis), `{}`/`[]` em falha. Sem sink durável.

## Task transparencia (`tasks/transparencia.py`) — `run_hourly_check` — Celery

- **Stub:** `{source:"TRANSPARENCIA", status:"pending_implementation"}`. TODO: check horário com cache Redis. Sem API/sink implementados.

---

# TASKS FISCAIS (worker `services.fiscal.celery_app`, queue `fiscal_ingest`)

Import guardado: `from services.fiscal.celery_app import app` (None sem broker → funções `_run` testáveis).

## Task rfb_tipi (`tasks/rfb_tipi.py`) — `run_ingest(url)` — name `fiscal.ingestion.rfb_tipi.run_ingest`, queue `fiscal_ingest` (autoretry RequestException, max_retries=5)

- **Entradas:** arg `url` (default env `TIPI_CSV_URL` = `https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/tipi/tipi.csv`). CB `TIPI`.
- **🌐 API:** `GET url` UA Chrome, `timeout=60`, encoding `latin1`. `_parse_rows` (`;`). `_to_bronze` mapeia `CODIGO/ncm`, `DESCRICAO`, `ALIQUOTA_IPI` (`,`→`.`, "NT"→None), `EX`; `add_linage(source="TIPI")`. Contrato `TipiBronze`.
- **⚙ Intermediário / quarentena:** `_quality_ok` — alíquota fora de `[0.0, 400.0]` → **quarentena** (`quarantined++`, não persiste). Linhas inválidas descartadas.
- **Saídas (Postgres):** `_upsert`:
  - `fiscal.ncm` (`ncm_codigo, descricao, capitulo, source='TIPI', transform_version`) — insere vigência atual se `NOT EXISTS … vigencia @> CURRENT_DATE` (idempotente).
  - `fiscal.ipi_aliquota` (`ncm_codigo, excecao, aliquota_pct, source='TIPI', transform_version`), `ON CONFLICT (ncm_codigo, excecao) DO UPDATE`.
  - `reconcile("TIPI", …) + {quarantined}`.

## Task sefaz_scraper (`tasks/sefaz_scraper.py`) — `run_ingest(uf, url)` — name `fiscal.ingestion.sefaz_scraper.run_ingest`, queue `fiscal_ingest`

- **Entradas:** args `uf`, `url:str|None`. CB `SEFAZ-{uf}`. `PORTAIS` (SP/RJ/MG).
- **🌐 Fronteira:** `fetch_html(target, wait_selector="table")` (Playwright, `services.fiscal.ingestion.browser`). `parse_aliquota_table(html, uf)` (bs4, lógica pura em `sefaz_parse.py`). Contrato `SefazAliquotaBronze` → outlier/inválido = **quarentena** (`_to_bronze` retorna None).
- **⚙ Intermediário:** `raw[]`; `valid[]`; linhas em quarentena.
- **Saídas (Postgres):** `_upsert` → `fiscal.icms_interno` (`uf, ncm_prefix, aliquota_pct, fcp_pct, fundamento_legal, source='SEFAZ', transform_version`) — insere vigência atual se `NOT EXISTS … (uf, COALESCE(ncm_prefix,'')) … vigencia @> CURRENT_DATE`. `reconcile("SEFAZ-{uf}", …)`.

## Task confaz_ocr (`tasks/confaz_ocr.py`) — `run_ingest(pdf_url)` — name `fiscal.ingestion.confaz_ocr.run_ingest`, queue `fiscal_ingest` (autoretry, max_retries=3)

- **Entradas:** arg `pdf_url`. CB `CONFAZ`.
- **🌐 API:** `GET pdf_url` UA TaxDataBot, `timeout=60`. `extract_text` (nativo/OCR) → `_parse_with_fallback` (LLM `LlmRuleParser` primário; fallback `HeuristicRuleParser`). Contrato `ConfazRegraBronze`.
- **⚙ Intermediário / dedup:** `file_sha256(pdf_bytes)`; `_already_processed` consulta/insere `fiscal.doc_hash (fonte='CONFAZ', file_hash)` — PDF repetido retorna `[]`. Regras inválidas descartadas.
- **Saídas:** regras candidatas para **fila de validação humana** (`needs_review=True`) — **NÃO** persiste alíquota. Retorna `{source:"CONFAZ", regras_para_revisao:N}`. Escreve `fiscal.doc_hash` (dedup).

## Task confaz_discovery (`tasks/confaz_discovery.py`) — `run_ingest(index_url)` — name `fiscal.ingestion.confaz_discovery.run_ingest`, queue `fiscal_ingest` (autoretry, max_retries=3)

- **Entradas:** arg `index_url` (default env `CONFAZ_INDEX_URL` = `https://www.confaz.fazenda.gov.br/legislacao/convenios`). CB `CONFAZ-INDEX`.
- **🌐 API:** `GET index_url` UA TaxDataBot, `timeout=60`. `parse_convenio_links` (bs4).
- **🌐 Saída (broker):** `app.send_task("fiscal.ingestion.confaz_ocr.run_ingest", args=[url], queue="fiscal_ingest")` por link descoberto (fan-out). Retorna `{source:"CONFAZ-INDEX", links, enqueued}`.

## Task ncm_history (`tasks/ncm_history.py`) — `run_ingest(url)` — name `fiscal.ingestion.ncm_history.run_ingest`, queue `fiscal_ingest` (autoretry, max_retries=3)

- **Entradas:** arg `url`. `GET url` UA TaxDataBot, `timeout=60`, encoding utf-8. `parse_migracao` (puro).
- **Saídas (Postgres):** `_upsert` → `fiscal.ncm_migracao` (`ncm_origem, ncm_destino, vigencia_inicio::date, vigencia_fim::date, ato_legal`) — insere se `NOT EXISTS …` (idempotente por origem+destino+vigência). Retorna `{source:"NCM_MIGRACAO", processed:N}`.

---

# Tabela resumo — fonte · API · contract · sink · Redis TTL

| fonte | API base 🌐 | contract | sink principal | Redis key · TTL |
|-------|-------------|----------|----------------|-----------------|
| DATAJUD | `api-publica.datajud.cnj.jus.br/processos` | `DatajudProcessoBronze/Silver` | MinIO `bronze-datajud` + OS `datajud-silver-YYYY-MM` + Neo4j PARTE_EM | `datajud:{date}` · 48h |
| RECEITA | `publica.cnpj.ws/cnpj/{cnpj}` | `ReceitaCnpjBronze/Silver` | (Redis; OS/Neo4j = TODO Fase 1b) | `receita:{cnpj}` · 7d |
| RECEITA (live) | `publica.cnpj.ws/cnpj/{cnpj}` | — (`_normalize`) | retorno gateway | — |
| PGFN | `regularize.pgfn.gov.br/api/situacao/{cnpj}` | `PgfnDevedorBronze/Silver` | (Redis; OS/Neo4j = TODO) | `pgfn:{cnpj}` · 7d |
| PNCP | `pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos` | `PncpContratoBronze/Silver` | Redis (silver JSON) | `pncp:{cnpj}:{ano}:{num}` · 24h |
| CAGED | `api.dados.gov.br/v1/conjuntos-dados/novo-caged/estabelecimento` | `CagedEstabelecimentoBronze/Silver` | Redis (silver JSON) | `caged:{cnpj}:{comp}` · 30d |
| SICONFI | `apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo` | `SiconfiContaBronze/Silver` | Redis (lista silver) | `siconfi:{cod}:{exerc}` · 7d |
| IBGE | `servicodados.ibge.gov.br/api/v1` + `/api/v3` | `IbgeMunicipioBronze/Silver` | Redis (silver JSON) | `ibge:{cod_ibge}` · 30d |
| SNIS | (sem task) | `SnisMunicipioBronze/Silver` | — | — |
| ABJ | `settings.ABJ_DATA_URL` (CSV) | `AbjIndicadorBronze/Silver` | OS `abj-silver` + Postgres `jurimetria.abj_indicador_raw` | — |
| CONSUMIDOR | `consumidor.gov.br/…/dadosabertos` (CSV) | — (agregação) | Redis (agg JSON) | `consumidor:{slug}` · 30d |
| BCB | `api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}` | — | retorno gateway | — |
| JURIMETRIA_AGG | OS `datajud-silver-*` + PG `abj_indicador_raw` | — | Postgres `jurimetria.indicador` | — |
| TIPI | `gov.br/.../tipi/tipi.csv` | `TipiBronze` | Postgres `fiscal.ncm` + `fiscal.ipi_aliquota` | — |
| SEFAZ | portais SP/RJ/MG (Playwright) | `SefazAliquotaBronze` | Postgres `fiscal.icms_interno` | — |
| CONFAZ (ocr) | PDF `confaz.fazenda.gov.br` | `ConfazRegraBronze` | fila revisão humana + `fiscal.doc_hash` | — |
| CONFAZ (disc.) | `confaz.fazenda.gov.br/legislacao/convenios` | — | broker Celery (send_task) | — |
| NCM_MIGRACAO | url env (CSV) | — (`parse_migracao`) | Postgres `fiscal.ncm_migracao` | — |
| TRANSPARENCIA | (stub) | — | — | — |

---

# celery_app.py — configuração 🌐

- `Celery('ingest', broker=REDIS_URL, backend=REDIS_URL)`; `timezone='America/Sao_Paulo'`; `task_default_queue='daily'`.
- `app.conf.include`: abj, caged, consumidor_gov, datajud, ibge, jurimetria_aggregate, pgfn, pncp, receita, siconfi, transparencia. (Tasks fiscais rodam no **worker fiscal** `services.fiscal.celery_app`.)
- Filas usadas: `daily`, `weekly`, `monthly`, `fiscal_ingest`.
