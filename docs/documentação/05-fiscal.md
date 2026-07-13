# 05 — Fiscal (NCM/ICMS/DIFAL + ingestão fiscal)

> Mapeamento linha a linha dos dados de `services/fiscal/*`: triagem determinística (descrição → NCM → ICMS/DIFAL),
> ancoragem Merkle de lote, enriquecimento de planilhas via chord Celery, e ingestão fiscal (scraping SEFAZ + OCR CONFAZ).
>
> **Legenda:** `→` (vira) · `⚙` (efêmero/descartado) · `🔒` (PII/segredo) · `🌐` (cruza fronteira). ⇐ leitura · ⇒ escrita.
>
> Contratos (`NcmTriageRequest/Result`, `IcmsResolution`, `NcmCandidate`, `UF`, `FonteRegra`) detalhados em `01`.

---

## `services/fiscal/triage/engine.py` — orquestrador puro `classify()`

- **Entradas:**
  - `classify(request: NcmTriageRequest, ncm_source, icms_source, category_source=None, semantic_source=None, *, fuzzy_threshold=0.82)`.
  - Protocols de fonte (injeção): `NcmSource{get_ncm(codigo,data), catalog(data)}`, `IcmsSource{interna(uf,ncm,data)}`,
    `CategorySource{categoria(ncm)}`, `SemanticNcmSource{suggest(descricao,k)}`.
- **Intermediário (⚙):**
  - `observacoes: list[str]` (acumulador de avisos de revisão), `conflito: bool`.
  - Ramo com `ncm_hint`: `row = ncm_source.get_ncm(hint, data)` ⚙ → `candidate = match_exact(hint, row)`; se `None` → `conflito=True` + observação.
  - Ramo sem hint: `candidate, fuzzy_conflito = match_fuzzy(descricao, catalog, threshold)`; se fraco e `semantic_source`,
    `sem_cand, sem_conflito = hits_to_candidate(semantic_source.suggest(descricao))` (fallback RAG) ⚙.
  - `ncm_codigo = candidate.ncm_codigo if candidate else None` ⚙ (usado nas etapas 2 e 3).
  - `interna_row = icms_source.interna(uf_destino, ncm_codigo, data)` ⚙ → `icms = resolve_icms(...)`.
  - `categoria = category_source.categoria(ncm_codigo)` (opcional).
- **Saídas:** `NcmTriageResult{sku_descricao=request.descricao, suggested_ncm=candidate, icms, categoria, conflito_detectado, observacoes, decision_proof=None}`.
- **Fronteiras:** puro — não toca o Ledger (a ancoragem é etapa separada, evita O(N²) em lotes de 40k). Fontes via Protocol.

---

## `services/fiscal/triage/ncm_matcher.py` — correspondência de NCM (pura)

- **Entradas:** `match_exact(ncm_hint, ncm_row: dict|None)`; `match_fuzzy(descricao, catalogo: list[tuple[cod,desc]], *, threshold=0.82)`.
- **Intermediário (⚙):**
  - `DEFAULT_FUZZY_THRESHOLD = 0.82`.
  - `match_exact`: retorna `NcmCandidate{ncm_codigo=row["ncm_codigo"].strip(), descricao, confidence=1.0, fonte_regra=TIPI}`.
  - `match_fuzzy`: `alvo = normalize_descricao(descricao)` ⚙; `escolhas = {i: normalize_descricao(desc)}` ⚙ (índice→desc normalizada);
    `melhor = rapidfuzz.process.extractOne(alvo, escolhas, scorer=fuzz.token_sort_ratio)` 🌐 (lib rapidfuzz) →
    `(_texto, score, idx)` ⚙; `confidence = round(score/100, 3)`; `conflito = confidence < threshold`.
- **Saídas:** `(NcmCandidate|None, conflito:bool)` (fonte `TIPI` no exato, `FUZZY` no aproximado).
- **Fronteiras (🌐):** depende de `rapidfuzz` (C++); ausência da lib → `(None, True)` (degradação).

---

## `services/fiscal/triage/icms_resolver.py` — resolução ICMS/DIFAL (pura)

- **Entradas:** `resolve_icms(uf_origem, uf_destino, interna_row_destino: dict|None, *, importado=False, conteudo_importacao_pct=None)`;
  `interna_row_destino{aliquota_pct, fcp_pct, fundamento_legal}` ⇐ injetado pelo repository.
- **Intermediário (⚙):**
  - `_efetiva(aliquota, fcp) = round(aliquota + (fcp or 0), 2)` → `interna_efetiva` (modal + FCP/FECP).
  - `interna_pct, fcp_pct, fundamento` extraídos de `interna_row_destino` ⚙.
  - Se `uf_origem == uf_destino`: sem interestadual/DIFAL.
  - Senão: `inter_pct, inter_fundamento = aliquota_interestadual(origem, destino, importado, conteudo_importacao_pct)` (Res. SF 22/1989 7/12%, 13/2012 4%);
    `difal = compute_difal(interna_efetiva, inter_pct)` = `max(0, dest−inter)` (EC 87/2015);
    `fundamento_final = "; ".join(fundamentos)` ⚙.
- **Saídas:** `IcmsResolution{interna_pct, fcp_pct, interna_efetiva_pct, interestadual_pct, difal_pct, fundamento_legal}`.
- **Fronteiras:** pura; base legal citada em `fundamento_legal` (rastreabilidade jurídica no dado).

---

## `services/fiscal/triage/semantic.py` — fallback semântico (RAG)

- **Entradas:** `hits_to_candidate(hits: list[tuple[cod,desc,score]], *, threshold=0.78)`; `RagNcmSource.__init__(collection="fiscal_ncm")`,
  `.index_ncm(catalogo)`, `.suggest(descricao, k=5)`.
- **Intermediário (⚙):**
  - `DEFAULT_SEMANTIC_THRESHOLD = 0.78`.
  - `hits_to_candidate`: `codigo, descricao, score = max(hits, key=score)` ⚙; `codigo = só dígitos.zfill(8)`;
    `confidence = round(clamp(score,0,1), 3)`; `conflito = confidence < threshold`; fonte `RAG`.
  - `RagNcmSource.suggest`: `results = self._rag.search(descricao, n_results=k)` 🌐 (ChromaDB + BGE-M3/Ollama);
    por hit: `codigo ⇐ metadata.ncm | id.replace("ncm:","")`; `dist = r["distance"]` ⚙ → `score = 1.0 − dist` (cosseno→similaridade).
  - `index_ncm`: para cada `(codigo, descricao)` → `RAGEngine.upsert_document(f"ncm:{codigo}", descricao, {"ncm":codigo})` ⇒ Chroma.
- **Saídas:** `(NcmCandidate|None, conflito)`; ou contagem de docs indexados.
- **Fronteiras (🌐):** `RagNcmSource` cruza para ChromaDB + Ollama (E2E-only); coleção **`fiscal_ncm`**.

---

## `services/fiscal/repository.py` — acesso a dados (Protocols concretos)

- **Entradas:** `classify_one(request)`; `bulk_insert_triage_items(tenant_id 🔒, job_id, items: list[dict])`;
  conexões via `get_engine()` (global) e `tenant_transaction(tenant_id)` (RLS).
- **Intermediário (⚙) — SQL lido (⇐ Postgres, tabelas globais temporais):**
  - `DbNcmSource.get_ncm`: `SELECT ncm_codigo, descricao FROM fiscal.ncm WHERE ncm_codigo=:c AND vigencia @> COALESCE(:d, CURRENT_DATE)`.
  - `DbNcmSource.catalog`: `SELECT ncm_codigo, descricao FROM fiscal.ncm WHERE vigencia @> ...` → `list[(cod.strip(), desc)]`.
  - `DbIcmsSource.interna`: `SELECT aliquota_pct, fcp_pct, fundamento_legal FROM fiscal.icms_interno WHERE uf=:uf AND vigencia @> ...
    AND (ncm_prefix IS NULL OR :ncm LIKE ncm_prefix||'%') ORDER BY length(ncm_prefix) DESC` (regra mais específica primeiro) → floats.
  - `DbCategorySource.categoria`: `SELECT c.slug FROM fiscal.ncm_categoria nc JOIN fiscal.categoria c ... ORDER BY length(nc.ncm_prefix) DESC`.
  - `classify_one`: abre `conn` → injeta `DbNcmSource/DbIcmsSource/DbCategorySource` em `classify()`.
- **Saídas (⇒ Postgres, RLS):** `bulk_insert_triage_items` — **executemany** em `fiscal.triage_item`
  `(job_id, tenant_id::uuid, leaf_index, sku_descricao, ncm_sugerido, confidence, fonte_regra, icms_interno_efetivo_pct,
  icms_inter_pct, difal_pct, categoria, conflito, observacoes::jsonb)`.
- **Fronteiras (🌐):** `tenant_transaction` aplica `SET LOCAL app.tenant_id` (RLS FORCE) — isolamento por tenant.

---

## `services/fiscal/batch/anchor.py` — ancoragem Merkle de lote

- **Entradas:** `build_batch_anchor(results: list[NcmTriageResult])`; `inclusion_proof(leaf_hashes, leaf_index, root)`;
  `verify_inclusion(proof)`; `batch_manifest_hash(job_id, tenant_id, count)`; `serialize_result(index, result)`.
- **Intermediário (⚙):**
  - `_leaf_for_item(index, result)`: `payload = {leaf_index, sku_descricao, ncm, confidence, icms=model_dump(), categoria, conflito}` ⚙
    → `_sha256(json.dumps(payload, sort_keys=True))` (folha determinística).
  - `leaf_hashes: list[str]` ⚙ → `_compute_merkle_root(leaf_hashes)` (reusa `shared/ledger/merkle`).
  - `inclusion_proof`: `_generate_proof(leaf_hashes, leaf_index)` → `{leaf_index, leaf_hash, proof:[{sibling, position}], root}`.
  - `verify_inclusion`: recomputa `current` subindo a árvore (`position left/right`) → `== root`.
- **Saídas:**
  - `build_batch_anchor` → `{root: hex, leaf_hashes: [...], count: N}`.
  - `serialize_result` → linha de `fiscal.triage_item` `{leaf_index, sku_descricao, ncm_sugerido, confidence, fonte_regra,
    icms_interno_efetivo_pct, icms_inter_pct, difal_pct, categoria, conflito, observacoes}`.
- **Fronteiras:** mesmo algoritmo de hash/prova do Decision Ledger — provas verificam com o mesmo verificador (`decision_proof` O(log N)).

---

## `services/fiscal/tasks.py` — enriquecimento assíncrono (chord Celery)

- **Entradas:** `enrich_spreadsheet(self, job_id, tenant_id 🔒, spreadsheet_key, uf_origem="SP")`; `classify_chunk(self, rows: list[dict], uf_origem)`;
  `finalize_enrichment(self, chunk_results: list[list[dict]], job_id, tenant_id)` — args 🌐 via broker Celery.
- **Intermediário (⚙):**
  - `_CHUNK = 500`.
  - `_to_request(row, uf_origem)`: valida `uf ∈ UF.__members__` e `descricao` → `NcmTriageRequest{descricao, uf_origem, uf_destino, ncm_hint}` (ou `None`, descartado ⚙).
  - `enrich_spreadsheet`: `_colmap, rows = load_items_from_bytes(download_spreadsheet(key))` ⇐ MinIO → `chunks = [rows[i:i+500]]` ⚙ →
    `chord(group(classify_chunk.s(c, uf))) (finalize_enrichment.s(job_id, tenant_id))`.
  - `classify_chunk`: por linha → `classify_one(req).model_dump(mode="json")` → `out: list[dict]` (serializado p/ transporte do chord) 🌐.
  - `finalize_enrichment`: `dicts = flatten(chunk_results)` ⚙ → `results = [NcmTriageResult(**d)]` ⚙ → `anchor = build_batch_anchor(results)`.
- **Saídas:**
  - ⇒ **Decision Ledger** (UMA entrada por job): `PostgresDecisionLedger(tenant).add_entry(request_id=job_id, product="fiscal",
    inputs={manifest: batch_manifest_hash(...)}, outputs={batch_merkle_root, count}, sources=["TIPI","SENADO","SEFAZ"])`.
  - ⇒ **Postgres** `fiscal.triage_item` (bulk, via `bulk_insert_triage_items`).
  - `enrich_spreadsheet` retorna `{job_id, chunks, status:"dispatched"}`; `finalize_enrichment` retorna `{job_id, processed, batch_merkle_root, ledger_entry_index, completed_at}`.
- **Fronteiras (🌐):** só a **KEY** do MinIO trafega no broker (não as linhas); chord fan-out entre réplicas do `fiscal-worker`
  (CPU-bound sob GIL — NÃO threads, para preservar `SET LOCAL app.tenant_id`).

---

## `services/fiscal/storage.py` — planilhas no MinIO

- **Entradas:** `upload_spreadsheet(key, data: bytes)`, `download_spreadsheet(key)`; `_client()` ⇐ settings `MINIO_URL/ACCESS_KEY/SECRET_KEY 🔒`.
- **Intermediário (⚙):** `Minio(...)` client efêmero; `DOCUMENTS_BUCKET = "documents"`.
- **Saídas:** ⇒ MinIO bucket **`documents`** key `{spreadsheet_key}` (bytes .xlsx); leitura devolve `bytes`.
- **Fronteiras (🌐):** MinIO S3 (staging de planilhas grandes fora do broker).

---

## `services/fiscal/spreadsheet/reader.py` — leitura de planilha (openpyxl)

- **Entradas:** `load_items(path)`, `load_items_from_bytes(data: bytes)`; `detect_columns(headers)`, `read_rows(ws, colmap)`.
- **Intermediário (⚙):**
  - Aliases de cabeçalho: `_DESC_ALIASES`, `_NCM_ALIASES`, `_UF_ALIASES` (conjuntos normalizados).
  - `detect_columns`: `norm = normalize_descricao(str(raw))` ⚙ → `colmap{descricao, ncm, uf}` (índice 1-based ou None).
  - `_clean_ncm(value)`: só dígitos `.zfill(8)` (ou None).
  - `read_rows`: itera `ws.iter_rows(min_row=2)`; por linha `{row: n, descricao, ncm_hint, uf}`.
  - `_extract`: `headers = próxima linha 1` ⚙ → `colmap` → `rows`; fecha o workbook.
- **Saídas:** `(colmap, rows: list[dict{row, descricao, ncm_hint, uf}])`.
- **Fronteiras (🌐):** lê arquivo Excel (`read_only=True, data_only=True`) — dado do cliente entra no sistema aqui.

---

## `services/fiscal/spreadsheet/writer.py` — escrita preservando fórmulas

- **Entradas:** `append_enrichment(ws, results_by_row: dict[int, NcmTriageResult], *, header_row=1)`; `enrich_workbook(in_path, out_path, results_by_row)`.
- **Intermediário (⚙):**
  - `ENRICHMENT_HEADERS` (9): NCM sugerido · Confiança NCM · Fonte da regra · ICMS interno efetivo (%) · ICMS interestadual (%) ·
    DIFAL (%) · Categoria · Conflito? · Observações.
  - `_row_values(result)`: extrai de `suggested_ncm`/`icms`/`observacoes` → lista de 9 valores (`"SIM"/"NÃO"` p/ conflito, `" | ".join(obs)`).
  - `start_col = ws.max_column + 1` ⚙ — escreve colunas **à direita** (nunca reescreve células existentes → preserva fórmulas).
- **Saídas:** ⇒ células novas no worksheet; `enrich_workbook` salva `.xlsx` em `out_path` (`data_only=False` mantém fórmulas).
- **Fronteiras:** openpyxl (I/O de arquivo). Ressalva: pode não preservar gráficos/tabelas dinâmicas.

---

## `services/fiscal/celery_app.py`

- **Entradas:** ⇐ env `REDIS_URL` (broker+backend).
- **Intermediário (⚙):** `app = Celery('fiscal')`, `task_default_queue='fiscal'`, `timezone='America/Sao_Paulo'`;
  `include = [fiscal.tasks, ingest.tasks.{rfb_tipi, sefaz_scraper, confaz_ocr, confaz_discovery, ncm_history}]` (rodam no worker fiscal por causa de Chromium/Tesseract).
- **Saídas — `beat_schedule`:** `rfb-tipi-mensal` (dia 1, 03:17) · `confaz-descoberta-semanal` (seg 05:07) ·
  `sefaz-{sp,rj,mg}-semanal` (seg 04:23/04:33/04:43, args `['SP'|'RJ'|'MG']`).
- **Fronteiras (🌐):** broker Redis (filas `fiscal`, `fiscal_ingest`).

---

## Ingestão fiscal (parsers puros — wrappers Celery ficam em `06-ingest`)

### `services/fiscal/ingestion/browser.py`
- **Entradas:** `fetch_html(url, *, wait_selector=None, timeout_ms=20000, user_agent=None)`; env `PLAYWRIGHT_EXECUTABLE`, `PLAYWRIGHT_BROWSERS_PATH`.
- **Intermediário (⚙):** `resolve_chromium_executable()` (glob por `headless_shell`/`chrome`); `ua` default; `_DEFAULT_ARGS=["--no-sandbox","--disable-dev-shm-usage"]`; página Playwright efêmera.
- **Saídas:** `page.content()` → HTML renderizado (str).
- **Fronteiras (🌐):** Chromium/Playwright → portal SEFAZ (rede externa, JS dinâmico).

### `services/fiscal/ingestion/sefaz_parse.py`
- **Entradas:** `parse_aliquota_table(html, uf)`; `clean_percentage(text)`.
- **Intermediário (⚙):** `_PCT_RE` (regex de %); BeautifulSoup `soup` ⚙; `target = tabela que parece de alíquota` (heurística `_HEADER_HINTS`);
  por `tr`: `cells = [td.text]` ⚙; `aliquota = primeiro % válido em cells[1:]`.
- **Saídas:** `list[dict{uf, produto, aliquota_pct, fundamento_legal}]` (só linhas com alíquota).
- **Fronteiras:** puro (HTML→dados). Produto é texto livre → mapeado a NCM depois por fuzzy.

### `services/fiscal/ingestion/confaz_index.py`
- **Entradas:** `parse_convenio_links(html, base_url)`.
- **Intermediário (⚙):** `_CONVENIO_HINTS`; `soup`, `seen: set` (dedup) ⚙; por `<a href>`: filtra `.pdf` + indícios → `urljoin(base_url, href)`.
- **Saídas:** `list[str]` de URLs absolutas de PDFs de convênios/protocolos (ordem preservada, sem duplicatas).

### `services/fiscal/ingestion/confaz_parse.py` — PDF → texto → regras
- **Entradas:** `extract_text(pdf_bytes, *, ocr_min_chars=200)`; `native_text(pdf_bytes)`; `ocr_text(pdf_bytes, dpi=300, lang="por")`; `parse_rules(text, parser=None)`.
- **Intermediário (⚙):**
  - `_OCR_MIN_CHARS=200`; regex `_NCM_RE`, `_ALIQ_RE`, `_UF_PAREN_RE`, `_VIG_RE`, `_ATO_RE`.
  - `native = native_text` (pdfplumber) ⚙; se `< ocr_min_chars` e tesseract disponível → `ocr_text` (pymupdf render → pytesseract) 🌐.
  - `HeuristicRuleParser.parse`: `ato_ref` ⚙; por NCM: `janela = text[start-200:end+300]` ⚙ → extrai `aliquota, uf_origem, uf_destino, vigencia`.
  - `LlmRuleParser.parse`: `prompt` com schema JSON → `requests.post(OLLAMA_URL/api/generate, format=json)` 🌐 → `data["regras"]`.
- **Saídas:** `list[dict{ncm, aliquota_pct, uf_origem, uf_destino, vigencia_inicio, ato_ref, needs_review=True}]` — **sempre `needs_review=True`** (validação humana antes de persistir).
- **Fronteiras (🌐):** OCR (Tesseract) e LLM (Ollama JSON mode). Dado fiscal nunca auto-persistido como vigente.

### `services/fiscal/ingestion/ncm_history.py` — migração de NCM
- **Entradas:** `parse_migracao(csv_text, *, delimiter=";")`; `resolve_current(ncm, migracoes, data=None)`.
- **Intermediário (⚙):** aliases de coluna (`_ORIG/_DEST/_INI/_FIM/_ATO_ALIASES`); `_detect(headers)` → colmap ⚙; `_clean_ncm` (8 dígitos);
  `resolve_current`: `by_origem: dict` (índice) ⚙; laço segue cadeia de sucessão com `visitados: set` (anti-ciclo) até a `data`.
- **Saídas:** `list[dict{ncm_origem, ncm_destino, vigencia_inicio, vigencia_fim, ato_legal}]`; ou o código NCM vigente (`str|None`).

### `services/fiscal/ingestion/ibge_parse.py` — municípios IBGE (DTB)
- **Entradas:** `parse_municipios(csv_text, *, delimiter=";")`; `detect_columns(headers)`.
- **Intermediário (⚙):** aliases (`_COD/_MUN/_UF_ALIASES`); `_clean_codigo` (7 dígitos); valida `uf ∈ UF.__members__`.
- **Saídas:** `list[dict{codigo_ibge, municipio, uf}]` (descarta linhas inválidas).

### `services/fiscal/ingestion/diario.py` — monitor de Diário Oficial (puro)
- **Entradas:** `file_sha256(data: bytes)`; `matched_fiscal_terms(text)`; `is_fiscally_relevant(text, *, min_terms=1)`.
- **Intermediário (⚙):** `FISCAL_TERMS` (10 regex: ICMS, alíquota, CONFAZ, isenção, RICMS, substituição tributária, FECP, FCP, decreto, convênio); `_COMPILED`.
- **Saídas:** hash SHA-256 (dedup/detecção de mudança → `fiscal.doc_hash`); lista de termos casados; bool de relevância.
- **Fronteiras:** puro; a persistência do hash em `fiscal.doc_hash` fica no wrapper Celery (módulo 06).

---

## Entidades globais desta fatia (para o dicionário mestre)

- **Postgres `fiscal.*` — lido:** `fiscal.ncm(ncm_codigo, descricao, vigencia)`, `fiscal.icms_interno(uf, ncm_prefix, aliquota_pct, fcp_pct, fundamento_legal, vigencia)`,
  `fiscal.ncm_categoria(ncm_prefix, categoria_id)` ⨝ `fiscal.categoria(id, slug)`.
- **Postgres `fiscal.*` — escrito (RLS):** `fiscal.triage_item(job_id, tenant_id, leaf_index, sku_descricao, ncm_sugerido, confidence, fonte_regra,
  icms_interno_efetivo_pct, icms_inter_pct, difal_pct, categoria, conflito, observacoes)`.
- **Decision Ledger:** 1 entrada por job — `product="fiscal"`, `sources=["TIPI","SENADO","SEFAZ"]`, `subject_token=None`, output `batch_merkle_root`.
- **Celery tasks (fila `fiscal`):** `fiscal.tasks.enrich_spreadsheet(job_id, tenant_id, spreadsheet_key, uf_origem)`,
  `fiscal.tasks.classify_chunk(rows, uf_origem)`, `fiscal.tasks.finalize_enrichment(chunk_results, job_id, tenant_id)`.
- **Celery beat (fila `fiscal_ingest`):** `fiscal.ingestion.rfb_tipi.run_ingest`, `.sefaz_scraper.run_ingest`, `.confaz_ocr.run_ingest`, `.confaz_discovery.run_ingest`, `.ncm_history.run_ingest`.
- **MinIO:** bucket **`documents`** key `{spreadsheet_key}` (planilhas .xlsx).
- **ChromaDB:** coleção **`fiscal_ncm`** (embeddings BGE-M3 de descrições NCM oficiais).
- **Constantes de negócio:** `DEFAULT_FUZZY_THRESHOLD=0.82`, `DEFAULT_SEMANTIC_THRESHOLD=0.78`, `_CHUNK=500`, `_OCR_MIN_CHARS=200`, `ENRICHMENT_HEADERS` (9 colunas).
- **env/segredos:** `REDIS_URL`, `MINIO_URL/ACCESS_KEY/SECRET_KEY 🔒`, `OLLAMA_URL`, `PLAYWRIGHT_EXECUTABLE`, `PLAYWRIGHT_BROWSERS_PATH`.
- **Sempre `needs_review=True`:** regras extraídas de CONFAZ (OCR/LLM) nunca auto-persistem como alíquota vigente.
