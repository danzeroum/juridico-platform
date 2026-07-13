# 08 — Defensor · PetiBot · LicitaWatch · Cluster Analítico

Catálogo de fluxo de dados linha-a-linha dos serviços agênticos (Defensor), montagem de peças (PetiBot), monitor de licitações (LicitaWatch) e do cluster analítico (Jurimetria, Knowledge Graph, Early Warning, Chamber Profiler, Second Opinion, Settlement Optimizer).

**Legenda:**
- **⚙** — valor Intermediário efêmero (existe apenas durante a execução; não persiste nem cruza fronteira).
- **🔒** — dado pessoal (PII) — nome/CPF de titular; sujeito a LGPD.
- **🌐** — Fronteira de sistema (LLM, RAG/ChromaDB, Neo4j, Postgres, AlertEnvelope/fila Elixir, chamada in-process cross-service).

Classificação por arquivo em quatro listas: **Entradas / Intermediário (⚙) / Saídas / Fronteiras (🌐)**. Nomes EXATOS conforme o código.

---

## DEFENSOR

### `services/defensor/orchestrator.py` — `run_agente()` (pipeline do agente jurídico)

**Entradas**
- `request: DefensorRequest` (frozen) — campos:
  - `descricao: str` (50–5000 chars) — fatos relatados 🔒 (pode conter PII do reclamante/relato)
  - `canal: Canal` (`PROCON | CONSUMIDOR_GOV | OUVIDORIA | CONTENCIOSO`)
  - `tipo_caso: TipoCaso` (`TRABALHISTA | CIVEL | TRIBUTARIO | PREVIDENCIARIO | ADMINISTRATIVO | CONSUMERISTA`)
  - `reclamante: str` (≥3) 🔒 (nome do consumidor/pessoa)
  - `reclamada: str` (≥3) — empresa reclamada
  - `cnpj_reclamada: str | None` (`^\d{14}$`)
  - `valor: float | None` (≥0)
- Constante `_LIMIAR_HANDOFF_HUMANO = 50_000.0`
- Constante `_SUBSIDIOS_BASE = ["contrato/termo de adesão", "histórico de cobranças", "protocolos de atendimento"]`
- Constante `_LLM_SYSTEM` (prompt de sistema do advogado)

**Intermediário (⚙ ephemeral)**
- `_classificar(request)` → `classificacao = f"{tipo_caso.value} · {canal.value}"` ⚙
- `_consultar_historico(request)` → `casos_anteriores = len(request.reclamante) % 5` ⚙ (stub determinístico; deriva de nome 🔒)
- `subsidios = list(_SUBSIDIOS_BASE)` ⚙ (3 docs)
- `peti_req: PetiRequest` ⚙ (mapeia DefensorRequest→PetiRequest: descricao, tipo_acao=TipoAcao(tipo_caso.value), polo_ativo=reclamante 🔒, polo_passivo=reclamada, valor_causa=valor, cnpj_parte=cnpj_reclamada)
- `_redigir_secoes(request, peti.secoes)` → `(secoes, defesa_via)` ⚙
  - por seção, quando `llm_ok`: monta `prompt` ⚙ incorporando `sec.titulo`, `canal.value`, `tipo_caso.value`, `reclamante` 🔒, `reclamada`, `descricao` 🔒 + instrução "1 a 2 parágrafos … sem inventar fatos"
  - `texto = generate_text(prompt, system=_LLM_SYSTEM, max_tokens=400)` (🌐 LLM)
  - `n_llm` ⚙ (contador de seções redigidas por IA); `llm_ok` ⚙ (curto-circuita após 1ª falha)
  - proveniência `via`: `"template"` se n_llm==0; `"llm"` se n_llm==len(secoes); senão `"parcial"`
- `_definir_responsavel(request)` → `(proximo_responsavel, status)` ⚙
  - `alto_valor = valor is not None and valor >= 50_000.0`
  - se `canal == CONTENCIOSO or alto_valor` → `("humano", "AGUARDA_PROTOCOLO")`; senão `("agente", "DEFESA_PRONTA")`
- `_detalhe_redacao` ⚙ (mapa via→detalhe: llm/parcial/template)
- `_now_iso()` → timestamp ISO UTC (por evento) ⚙

**Timeline `eventos: list[EventoAgente]`** (cada item: `ts`, `evento`, `detalhe`, `status ∈ {ok,running,pending}`) — sequência EXATA:
1. `evento="caso.classificado"`, `detalhe=classificacao`, status=ok
2. `evento="reclamante.consultado"`, `detalhe=f"{casos_anteriores} casos anteriores"`, status=ok
3. `evento="subsidios.solicitando"`, `detalhe="crm · pedidos"`, status=ok
4. `evento="subsidios.ok"`, `detalhe=f"{len(subsidios)} docs anexados"`, status=ok
5. `evento="jurisprudencia.match"`, `detalhe=f"{peti.precedentes_encontrados} precedentes"`, status=ok
6. `evento="defesa.redigindo"`, `detalhe=_detalhe_redacao[defesa_via]`, `status="ok" if defesa_via != "template" else "running"`
7. `evento="defesa.pronta"`, `detalhe=f"{len(secoes)} seções"`, status=ok
8. `evento="protocolo.preparado"`, `detalhe=f"{canal.value} · responsável: {proximo_responsavel}"`, `status="ok" if proximo_responsavel=="agente" else "pending"`

**Saídas**
- `DefensorResponse` (frozen) — campos:
  - `classificacao: str`
  - `canal: str` (= request.canal.value)
  - `eventos: list[EventoAgente]` (8 itens acima)
  - `secoes: list[PetiSection]` (redigidas; conteúdo 🔒 quando via LLM incorpora relato)
  - `precedentes_encontrados: int` (≥0, = peti.precedentes_encontrados)
  - `casos_anteriores: int` (≥0)
  - `subsidios: list[str]`
  - `proximo_responsavel: str` (`"agente" | "humano"`)
  - `status: str` (`DEFESA_PRONTA | AGUARDA_PROTOCOLO`)
  - `defesa_via: str` (`llm | parcial | template`)
  - `computed_at: str` (ISO UTC)
  - `contract_version: str = "defensor/v1"`

**Fronteiras (🌐)**
- 🌐 **LLM** — `generate_text(prompt, system=_LLM_SYSTEM, max_tokens=400)` por seção (degradação graciosa → None).
- 🌐 **in-process cross-service** — `assemble_petition(peti_req)` (PetiBot) → dispara RAG.
- 🌐 (transitivo via PetiBot) **RAG/ChromaDB** — coleção `petibot_jurisprudencia`.

---

### `services/defensor/protocolar.py` — `protocolar()`

**Entradas**
- `req: ProtocoloRequest` (frozen) — campos:
  - `canal: Canal`
  - `reclamante: str` (≥3) 🔒
  - `reclamada: str` (≥3)
  - `cnpj_reclamada: str | None` (`^\d{14}$`)
  - `resumo: str` (20–5000) 🔒
  - `defesa: str | None` (≤20000)
  - `valor: float | None` (≥0)
  - `anexos: list[str]`
- `settings.PROTOCOLO_MODO` (🌐 config; default `"simulacao"`)

**Intermediário (⚙)**
- `modo = settings.PROTOCOLO_MODO` ⚙
- `driver = get_driver(req.canal, modo)` ⚙
- `resultado = driver.submit(req)` ⚙

**Saídas**
- `ProtocoloResultado` (do driver) — retornado ao chamador.
- `logger.info(...)` de auditoria com `canal.value, resultado.modo, resultado.status, resultado.numero_protocolo`.

**Fronteiras (🌐)**
- 🌐 **Config** — `settings.PROTOCOLO_MODO`.
- 🌐 **in-process** — driver factory + `driver.submit`.

---

### `services/defensor/protocolo/base.py` — interface `ProtocoloDriver` + utilidades

**Entradas**
- `req: ProtocoloRequest` (via `numero_simulado`).

**Intermediário (⚙)**
- `now_iso()` → ISO UTC ⚙
- `numero_simulado(req)`:
  - `base = f"{canal.value}|{reclamante}|{reclamada}|{resumo}"` ⚙ 🔒 (inclui nome + resumo)
  - `digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:10].upper()` ⚙ (SHA-256, 10 hex chars)
  - retorna `f"SIM-{canal.value}-{digest}"` ⚙

**Saídas**
- `str` número de protocolo simulado determinístico.
- Classe abstrata `ProtocoloDriver` (attr `canal`, método abstrato `submit`; contrato: NUNCA levanta).

**Fronteiras (🌐)** — nenhuma (utilidade pura).

---

### `services/defensor/protocolo/factory.py` — `get_driver()`

**Entradas**
- `canal: Canal`
- `modo: str`
- `_DRIVERS_REAIS: dict[Canal, type[ProtocoloDriver]]` = `{CONSUMIDOR_GOV: ConsumidorGovDriver, PROCON: ProconSPDriver}`

**Intermediário (⚙)**
- `driver_cls = _DRIVERS_REAIS.get(canal)` ⚙

**Saídas**
- `ProtocoloDriver`:
  - `modo != ProtocoloModo.REAL.value` → `SimulacaoDriver()`
  - `modo == "real"` + canal mapeado → driver real; senão `SimulacaoDriver()` (OUVIDORIA/CONTENCIOSO sem automação → simula)

**Fronteiras (🌐)** — nenhuma direta (seleciona driver).

---

### `services/defensor/protocolo/simulacao.py` — `SimulacaoDriver.submit()`

**Entradas**
- `req: ProtocoloRequest`
- attr `canal = "*"`

**Intermediário (⚙)**
- `numero_simulado(req)` ⚙ (SHA-256)
- `now_iso()` ⚙

**Saídas**
- `ProtocoloResultado`:
  - `canal = req.canal.value`
  - `modo = ProtocoloModo.SIMULACAO.value` (`"simulacao"`)
  - `status = ProtocoloStatus.SIMULADO.value` (`"SIMULADO"`)
  - `numero_protocolo = numero_simulado(req)` (`SIM-<canal>-<digest>`)
  - `url = None`
  - `mensagem` (aviso "nenhuma submissão real")
  - `enviado_em = now_iso()`

**Fronteiras (🌐)** — NENHUMA (garantia: zero chamada externa).

---

### `services/defensor/protocolo/real.py` — drivers reais Playwright

**Entradas**
- `req: ProtocoloRequest`
- Credenciais via `settings` (🌐 secrets):
  - `ConsumidorGovDriver`: `settings.CONSUMIDOR_GOV_USER`, `settings.CONSUMIDOR_GOV_PASSWORD` 🔒 (segredo)
  - `ProconSPDriver`: `settings.PROCON_SP_USER`, `settings.PROCON_SP_PASSWORD` 🔒 (segredo)
- attrs de classe: `canal`, `portal_url`, `portal_nome`
  - ConsumidorGov: canal=`"CONSUMIDOR_GOV"`, url=`https://www.consumidor.gov.br`, nome=`"Consumidor.gov"`
  - ProconSP: canal=`"PROCON"`, url=`https://www.procon.sp.gov.br`, nome=`"Procon-SP"`

**Intermediário (⚙)**
- `user, password = self._credenciais()` ⚙ 🔒
- gating: `if not (user and password)` → `AGUARDA_CREDENCIAIS` ⚙
- `_resultado(req, status, mensagem, numero, url)` → helper monta ProtocoloResultado ⚙
- `_submit_real(req, user, password)` — lazy-import `playwright.sync_api.sync_playwright`; scaffold (fluxo login/captcha/preenchimento comentado) → levanta `NotImplementedError` → capturado → `FALHA`.

**Saídas**
- `ProtocoloResultado` com `modo = ProtocoloModo.REAL.value` (`"real"`) e um dos status:
  - `AGUARDA_CREDENCIAIS` (sem credenciais — não toca a rede)
  - `FALHA` (exceção controlada; `mensagem=f"Falha na submissão real: {exc}"`)
  - (`ENVIADO` previsto no scaffold, não alcançável hoje)
- `logger.warning` em falha real.

**Fronteiras (🌐)**
- 🌐 **Secrets/config** — credenciais de portal.
- 🌐 **Portal externo (Playwright/Chromium)** — bloqueado no ambiente; scaffold nunca submete.

---

## PETIBOT

### `services/petibot/assembler.py` — `assemble_petition()`

**Entradas**
- `request: PetiRequest` (frozen) — campos:
  - `descricao: str` (50–5000) 🔒 (relato)
  - `tipo_acao: TipoAcao`
  - `polo_ativo: str` (≥3) 🔒
  - `polo_passivo: str` (≥3)
  - `valor_causa: float | None` (≥0)
  - `cnpj_parte: str | None` (`^\d{14}$`)
- `SECOES_MINIMAS_POR_TIPO: dict[str, list[str]]` (títulos por tipo de ação — TRABALHISTA/CIVEL/TRIBUTARIO/PREVIDENCIARIO/ADMINISTRATIVO/CONSUMERISTA)
- `_DEFAULT_SECTIONS = ["DOS FATOS", "DO DIREITO", "DOS PEDIDOS"]`
- `_SECTION_TEMPLATES: dict[str, str]` — 12 chaves: `DOS FATOS`, `DO DIREITO`, `DO DIREITO TRIBUTÁRIO`, `DA ILEGALIDADE`, `DAS VERBAS RESCISÓRIAS`, `DOS DANOS`, `DO DIREITO PREVIDENCIÁRIO`, `DO BENEFÍCIO`, `DO DIREITO ADMINISTRATIVO`, `DO CABIMENTO`, `DO DIREITO DO CONSUMIDOR`, `DOS PEDIDOS`.

**Intermediário (⚙)**
- `tipo = request.tipo_acao.value` ⚙
- `titulos = SECOES_MINIMAS_POR_TIPO.get(tipo, _DEFAULT_SECTIONS)` ⚙
- `_lookup_precedentes(descricao, tipo)` → `(doc_ids, n_total)` ⚙ (via provenance RAG):
  - `RAGEngine(collection_name="petibot_jurisprudencia")` (🌐 RAG)
  - `results = rag.search(query=descricao, n_results=5)` — `query=descricao` 🔒
  - `doc_ids = [str(r["id"]) for r in results]`; retorna `(doc_ids, len(doc_ids))`; falha → `([], 0)` (degradação graciosa)
- `precedente_ids, n_precedentes` ⚙
- laço por título: `template = _SECTION_TEMPLATES.get(titulo, f"[Fundamentar: {titulo}]")` ⚙; `prec = [precedente_ids[i]] if i < len(precedente_ids) else []` ⚙ (1 precedente por seção por índice posicional)

**Saídas**
- `PetiResponse` (frozen) — campos:
  - `tipo_acao: str`
  - `polo_ativo: str` 🔒
  - `polo_passivo: str`
  - `secoes: list[PetiSection]` (cada `PetiSection`: `titulo`, `conteudo` (template), `precedentes: list[str]`)
  - `precedentes_encontrados: int` (≥0)
  - `risk_score: int | None = None` (não populado aqui)
  - `probability_favorable: float | None = None` (não populado aqui)
  - `computed_at: str` (ISO UTC)
  - `contract_version: str = "petibot/v1"`

**Fronteiras (🌐)**
- 🌐 **RAG/ChromaDB** — coleção `petibot_jurisprudencia`; embeddings BGE-M3 via Ollama (🌐, fallback embedder padrão); ChromaHttpClient em `settings.CHROMA_URL`.

---

## LICITAWATCH

### `services/licitawatch/rules.py` — `LICITAWATCH_RULES`

**Entradas / Saídas (constante de regras)**
- `LICITAWATCH_RULES: list[dict]` — 4 regras, cada uma com `id`, `name`, `description`, `field`, `threshold`, `severity`, `cooldown_hours`:
  - **LL01** `id="LL01_concentracao_fornecedor"`, `field="pct_mesmo_vencedor"`, `threshold=0.70`, `severity="ALTO"`, `cooldown_hours=720`
  - **LL02** `id="LL02_dispensa_excessiva"`, `field="pct_dispensa"`, `threshold=0.30`, `severity="ALTO"`, `cooldown_hours=720`
  - **LL03** `id="LL03_unico_proponente"`, `field="pct_unico_proponente"`, `threshold=0.50`, `severity="CRITICO"`, `cooldown_hours=720`
  - **LL04** `id="LL04_prazo_curto"`, `field="pct_prazo_curto"`, `threshold=0.20`, `severity="MEDIO"`, `cooldown_hours=360`

**Fronteiras (🌐)** — nenhuma.

---

### `services/licitawatch/monitor.py` — `LicitacaoIndicadores`, `evaluate_licitacoes()`, `build_indicadores_from_silver()`

**Entradas**
- `evaluate_licitacoes(ind: LicitacaoIndicadores)`
- `build_indicadores_from_silver(cnpj_orgao: str, referencia: str, contratos: list[PncpContratoSilver])`
  - de cada `PncpContratoSilver` lê: `valor_contrato`, `cnpj_fornecedor`, `is_dispensa`, `is_unico_proponente`, `prazo_abertura_dias`
- Constantes: `_PRAZO_CURTO_DIAS = 5`; `_SEVERITY_MAP = {CRITICO→Severity.CRITICAL, ALTO→HIGH, MEDIO→MEDIUM, BAIXO→LOW}`

**`LicitacaoIndicadores` (dataclass)** — campos:
- `cnpj_orgao: str` (CNPJ de órgão público — NÃO é PII)
- `referencia: str` (`"YYYY"`)
- `total_contratos: int = 0`
- `pct_mesmo_vencedor: float | None = None` (máx share de um fornecedor)
- `pct_dispensa: float = 0.0`
- `pct_unico_proponente: float = 0.0`
- `pct_prazo_curto: float = 0.0`
- `valor_total: float = 0.0`

**Intermediário (⚙) — `build_indicadores_from_silver`**
- `total = len(contratos)` ⚙
- `valor_total = sum(c.valor_contrato for c in contratos)` ⚙
- `fornecedores = [c.cnpj_fornecedor ... if c.cnpj_fornecedor]` ⚙
- LL01: `mais_freq = Counter(fornecedores).most_common(1)[0][1]` ⚙; `pct_mesmo_vencedor = round(mais_freq/total, 4)`
- LL02: `n_dispensa = sum(1 ... if c.is_dispensa)` ⚙; `pct_dispensa = round(n_dispensa/total, 4)`
- LL03: `n_unico = sum(1 ... if c.is_unico_proponente)` ⚙; `pct_unico = round(n_unico/total, 4)`
- LL04: `n_prazo = sum(1 ... if prazo_abertura_dias is not None and < 5)` ⚙; `pct_prazo = round(n_prazo/total, 4)`
- (contratos vazios → `LicitacaoIndicadores(cnpj_orgao, referencia)` zerado)

**Intermediário (⚙) — `evaluate_licitacoes`**
- guarda: `if ind.total_contratos == 0: return []`
- `field_values` ⚙ (mapa nome→valor: pct_mesmo_vencedor, pct_dispensa, pct_unico_proponente, pct_prazo_curto)
- por regra: `value = field_values.get(rule["field"])`; pula se `None` ou `value <= rule["threshold"]` ⚙
- `severity = _SEVERITY_MAP.get(rule["severity"], Severity.MEDIUM)` ⚙
- `dedup_key = f"{rule['id']}:{ind.cnpj_orgao}:{ind.referencia}"` ⚙
- `alert_id = str(uuid.uuid5(uuid.NAMESPACE_OID, dedup_key))` ⚙ (determinístico)

**Saídas**
- `build_...` → `LicitacaoIndicadores` (com `valor_total = round(valor_total, 2)`).
- `evaluate_...` → `list[AlertEnvelope]` — cada envelope:
  - `alert_id` (uuid5), `dedup_key`, `rule_id = rule["id"]`, `severity`
  - `subject_ref = {"cnpj": ind.cnpj_orgao}` (comentário: CNPJ de órgão público — não é PII)
  - `payload = {"total_contratos", "valor_observado": round(value,4), "threshold": rule["threshold"], "referencia"}`
  - `channels = [Channel.WEBHOOK]`
  - `occurred_at = datetime.now(UTC)`

**Fronteiras (🌐)**
- 🌐 **AlertEnvelope** — produtor de alertas (contrato Python↔Elixir `alerts/v1`), canal `webhook`.
- 🌐 **in-process** — consome `PncpContratoSilver` (camada ingest silver).

---

## CLUSTER ANALÍTICO

### `services/jurimetria/queries.py` — feature store `jurimetria.indicador` + Market Intelligence

**Entradas**
- `get_indicators(tribunal, classe, assunto, periodo, fonte, limit=100, offset=0)`
- `get_congestion(tribunal)`
- `get_duration(classe)`
- `get_litigiosity(assunto=None)`
- `market_intelligence(tribunal=None, ramo=None)`
- `_INDICADOR_COLS` (tupla de colunas): `tribunal, classe_tpu, assunto_tpu, periodo, fonte, n_processos, duracao_mediana_dias, duracao_p25_dias, duracao_p75_dias, taxa_congestionamento, taxa_litigiosidade, pct_provimento`

**Intermediário (⚙)**
- `_rows(sql, params)` — helper Postgres; degradação graciosa (`except → return []`) ⚙
- `where: list[str]`, `params: dict` construídos por filtro ⚙; normalizações: `tribunal.upper()`, `fonte.upper()`; `params["limit"]=min(limit,500)`, `offset=max(offset,0)`
- `market_intelligence`: `linhas = _rows(...)`; `total = sum((r.get("total_processos") or 0) for r in linhas)` ⚙

**Colunas SQL lidas de `jurimetria.indicador`**
- `get_indicators`: `_INDICADOR_COLS` (12 colunas); `ORDER BY n_processos DESC LIMIT :limit OFFSET :offset`
- `get_congestion`: `tribunal, classe_tpu, assunto_tpu, periodo, fonte, taxa_congestionamento, n_processos` (WHERE `taxa_congestionamento IS NOT NULL`, LIMIT 200)
- `get_duration`: `tribunal, classe_tpu, assunto_tpu, periodo, fonte, duracao_mediana_dias, duracao_p25_dias, duracao_p75_dias, n_processos` (WHERE `duracao_mediana_dias IS NOT NULL`, LIMIT 200)
- `get_litigiosity`: `tribunal, classe_tpu, assunto_tpu, periodo, fonte, taxa_litigiosidade, n_processos` (WHERE `taxa_litigiosidade IS NOT NULL`, LIMIT 200)
- `market_intelligence`: `classe_tpu, assunto_tpu, SUM(n_processos) AS total_processos, AVG(taxa_congestionamento) AS congestionamento_medio, AVG(duracao_mediana_dias) AS duracao_mediana_tipica, AVG(pct_provimento) AS provimento_medio` — `GROUP BY classe_tpu, assunto_tpu ORDER BY total_processos DESC LIMIT 100`

**Saídas**
- `get_*` → `list[dict]` (linhas de indicador).
- `market_intelligence` → `dict`: `{"tribunal": upper|"TODOS", "ramo", "total_processos", "segmentos": linhas, "n_segmentos": len(linhas)}` — ZERO PII (dados agregados).

**Fronteiras (🌐)**
- 🌐 **Postgres** — `get_engine()` (tabela global/pública, sem RLS/tenant); `jurimetria.indicador`.
- 🌐 **Decision Ledger** (no router `gateway/routers/jurimetria.py`, não neste módulo): `market_intelligence` → `_ledger_entry` → `PostgresDecisionLedger(tenant_id)` ou `DecisionLedger()`; `ledger.add_entry(product="jurimetria-market-intelligence", inputs={tribunal, ramo}, outputs={total_processos, n_segmentos}, sources=["jurimetria.indicador"], subject_token=None)` + `log_ledger_write(has_subject_token=False)`.

---

### `services/knowledge_graph/analysis.py` — núcleo puro (Litigant Network)

**Entradas**
- `classify_relationship(processos_em_comum: int)`
- `annotate_network(rows: list[dict])`
- `network_summary(rows: list[dict])` — cada row usa chave `processos_em_comum`
- Limiares: `_OCASIONAL = 2`, `_RECORRENTE = 5`, `_PREDATORIO = 20`

**Intermediário (⚙)**
- `classify_relationship`: `>= 20 → "PREDATORIO"`; `>= 5 → "RECORRENTE"`; `>= 2 → "OCASIONAL"`; senão `"ISOLADO"` ⚙
- `annotate_network`: `n = int(r.get("processos_em_comum") or 0)`; anexa `"relacao"` a cada row ⚙
- `network_summary`: `annotated` ⚙; `dist = {"ISOLADO":0,"OCASIONAL":0,"RECORRENTE":0,"PREDATORIO":0}` contado ⚙; `predatorios` ⚙

**Saídas**
- `classify_relationship` → `str` (`ISOLADO|OCASIONAL|RECORRENTE|PREDATORIO`).
- `annotate_network` → `list[dict]` (rows + `relacao`).
- `network_summary` → `dict`: `{"n_vizinhos", "distribuicao": dist, "tem_litigancia_predatoria": len(predatorios)>0, "vizinhos": annotated}`.

**Fronteiras (🌐)** — nenhuma (núcleo puro; sem I/O).

---

### `services/knowledge_graph/queries.py` — camada I/O Neo4j

**Entradas**
- `company_processes(cnpj: str, limit=100)`
- `litigant_network(cnpj: str, limit=50)`
- `graph_stats()`

**Intermediário (⚙)**
- lazy-import dos read fns de `services.shared.storage.neo4j_client` ⚙
- `rows = _q(cnpj, limit)` (falha → `rows = []`) ⚙
- `network_summary(rows)` aplicado in-process ⚙

**Saídas**
- `company_processes` → `list[dict]` (por processo). Cypher RETURN: `p.id AS id, p.tribunal AS tribunal, p.classe AS classe_tpu, p.assunto AS assunto_tpu, p.ramo AS ramo, p.data_julgamento AS data_julgamento` (ORDER BY data_julgamento DESC).
- `litigant_network` → `dict`: `{"cnpj": cnpj, **network_summary(rows)}`. Cypher RETURN: `outra.cnpj AS cnpj, count(DISTINCT p) AS processos_em_comum, collect(DISTINCT p.ramo)[..5] AS ramos` (WHERE `outra.cnpj <> $cnpj`, ORDER BY processos_em_comum DESC).
- `graph_stats` → `dict`: `{"empresas", "processos", "arestas"}` (falha/vazio → zeros). Cypher RETURN: `empresas, processos, count(r) AS arestas`.

**Fronteiras (🌐)**
- 🌐 **Neo4j** — read fns `company_processes`, `litigant_network`, `graph_stats` (auth `settings.NEO4J_URL/USER/PASSWORD`). Modelo `(:Empresa {cnpj})-[:PARTE_EM]->(:Processo)`. Somente CNPJ↔CNPJ (dados públicos, sem PII). Degradação graciosa.

---

### `services/early_warning/detect.py` — núcleo puro (Early Warning)

**Entradas**
- `detect_surges(valores: list[float], taxa_congestionamento: float | None = None)`
- Limiares: `_Z_SURTO = 2.0`, `_PCT_SURTO = 0.5`, `_CONG_CRITICO = 0.7`, `_MIN_PONTOS = 3`

**Intermediário (⚙)**
- `serie = [float(v) for v in valores if v is not None]` ⚙
- se `len(serie) >= 3`:
  - `historico = serie[:-1]`, `atual = serie[-1]` ⚙
  - `_mean_std(historico)` → `(media, desvio)` ⚙ (média + desvio-padrão populacional: `var = Σ(x-m)²/n`, `desvio = var**0.5`)
  - `z = (atual - media)/desvio if desvio > 0 else 0.0` ⚙
  - `var_pct = (atual - historico[-1])/historico[-1] if historico[-1] > 0 else 0.0` ⚙
  - gatilho SURTO_VOLUME se `z >= 2.0 or var_pct >= 0.5`
- `_severity_from_z(z)`: `>=4 CRITICAL`, `>=3 HIGH`, `>=2 MEDIUM`, senão `LOW` ⚙
- gatilho PICO_CONGESTIONAMENTO se `taxa >= 0.7`; severidade `HIGH if taxa >= 0.85 else MEDIUM`

**Saídas**
- `dict`: `{"n_gatilhos", "tem_alerta": >0, "gatilhos": [...], "disclaimer": "heurística de detecção de surto — não validada"}`.
  - gatilho SURTO_VOLUME: `{"tipo":"SURTO_VOLUME", "severidade": _severity_from_z(z) if z>=2 else "MEDIUM", "z_score": round(z,2), "variacao_pct": round(var_pct,4), "valor_atual": round(atual,2), "media_historica": round(media,2)}`
  - gatilho PICO_CONGESTIONAMENTO: `{"tipo":"PICO_CONGESTIONAMENTO", "severidade": HIGH|MEDIUM, "taxa_congestionamento": round(taxa,4)}`

**Fronteiras (🌐)** — nenhuma (núcleo puro). Saída pronta para virar AlertEnvelope na borda (subject_ref tribunal/assunto — sem PII).

---

### `services/early_warning/queries.py` — camada I/O

**Entradas**
- `evaluate(tribunal: str, classe: str | None = None, assunto: str | None = None)`
- `_serie_e_congestionamento(tribunal, classe, assunto)`

**Intermediário (⚙)**
- `where = ["tribunal = :tribunal", "periodo <> 'TODOS'"]` + filtros opcionais classe/assunto ⚙
- `params["tribunal"] = tribunal.upper()` ⚙
- SQL: `SELECT periodo, SUM(n_processos) AS n, AVG(taxa_congestionamento) AS cong FROM jurimetria.indicador WHERE ... GROUP BY periodo ORDER BY periodo ASC`
- `valores = [row["n"] for row in rows]` ⚙; `cong = rows[-1]["cong"] if rows else None` ⚙ (último período)
- `detect_surges(valores, cong)` in-process ⚙

**Colunas SQL lidas** — `periodo`, `n_processos` (SUM→`n`), `taxa_congestionamento` (AVG→`cong`) de `jurimetria.indicador`.

**Saídas**
- `evaluate` → `dict`: `{"tribunal": upper, "classe_tpu": classe, "assunto_tpu": assunto, **detect_surges(...)}`.

**Fronteiras (🌐)**
- 🌐 **Postgres** — `get_engine()`, `jurimetria.indicador` (falha → `([], None)`).
- 🌐 **in-process** — `detect_surges`.

---

### `services/chamber_profiler/profile.py` — núcleo puro (Judge/Chamber Profiler)

**Entradas**
- `build_profile(tribunal: str, rows: list[dict])` — cada row: `{classe_tpu, assunto_tpu, n_processos, pct_provimento, taxa_congestionamento, duracao_mediana_dias}`
- Tiers (funções `_tier_*`).

**Intermediário (⚙)**
- `_tier_provimento(pct)`: None→`SEM_DADOS`; `>=0.5 ALTO_PROVIMENTO`; `>=0.25 MODERADO_PROVIMENTO`; senão `BAIXO_PROVIMENTO` ⚙
- `_tier_congestionamento(taxa)`: None→`SEM_DADOS`; `>=0.7 MUITO_CONGESTIONADO`; `>=0.5 CONGESTIONADO`; senão `FLUIDO` ⚙
- `_tier_duracao(dias)`: None→`SEM_DADOS`; `>=720 LENTO`; `>=365 MEDIANO`; senão `RAPIDO` ⚙
- `_wavg(pairs)`: média ponderada por `n_processos`, ignora None/peso≤0; `(num/den) if den else None` ⚙
- `total = sum(int(r.get("n_processos") or 0) for r in rows)` ⚙
- `prov = _wavg([(pct_provimento, n_processos)...])`, `cong = _wavg([(taxa_congestionamento, n_processos)...])`, `dur = _wavg([(duracao_mediana_dias, n_processos)...])` ⚙

**Saídas**
- `dict`: `{"tribunal": upper, "grao": "tribunal+classe", "n_processos": total, "n_segmentos": len(rows), "perfil": {"provimento": {"valor": round(prov,4)|None, "faixa": _tier_provimento(prov)}, "congestionamento": {"valor": round(cong,4)|None, "faixa": _tier_congestionamento(cong)}, "duracao_mediana_dias": {"valor": round(dur,1)|None, "faixa": _tier_duracao(dur)}}, "disclaimer": "perfil AGREGADO por órgão (não por juiz individual) …"}`.
- GOVERNANÇA LGPD: perfila órgão julgador AGREGADO (tribunal+classe), NUNCA juiz individual.

**Fronteiras (🌐)** — nenhuma (núcleo puro).

---

### `services/chamber_profiler/queries.py` — camada I/O

**Entradas**
- `profile_tribunal(tribunal: str, classe: str | None = None)`
- `_rows(tribunal, classe)`

**Intermediário (⚙)**
- `where = ["tribunal = :tribunal", "fonte IN ('DATAJUD', 'BLEND')"]` + classe opcional ⚙
- `params["tribunal"] = tribunal.upper()` ⚙
- SQL: `SELECT classe_tpu, assunto_tpu, n_processos, pct_provimento, taxa_congestionamento, duracao_mediana_dias FROM jurimetria.indicador WHERE ...`

**Colunas SQL lidas** — `classe_tpu, assunto_tpu, n_processos, pct_provimento, taxa_congestionamento, duracao_mediana_dias` de `jurimetria.indicador` (filtro `fonte IN ('DATAJUD','BLEND')`).

**Saídas**
- `profile_tribunal` → `build_profile(tribunal, _rows(...))` (dict do núcleo).

**Fronteiras (🌐)**
- 🌐 **Postgres** — `get_engine()`, `jurimetria.indicador` (falha → `[]`).
- 🌐 **in-process** — `build_profile`.

---

### `services/second_opinion/consensus.py` — núcleo puro (Second Opinion Engine)

**Entradas**
- `synthesize_opinion(legalscore: float | None = None, taxpredict_prob: float | None = None, pct_provimento: float | None = None)`
- `_normalize_signals(legalscore, taxpredict_prob, pct_provimento)`

**Intermediário (⚙)**
- `_normalize_signals` → `sinais: dict[str, float]` (clamp 0..1) ⚙:
  - `"legalscore" = max(0, min(1, legalscore/1000.0))`
  - `"taxpredict" = max(0, min(1, taxpredict_prob))`
  - `"jurimetria" = max(0, min(1, pct_provimento))`
- guarda: `if not sinais: return {"status": "sem_sinais"}`
- `valores = list(sinais.values())` ⚙
- `favorabilidade = sum(valores)/len(valores)` ⚙
- concordância (só com ≥2 sinais): `amplitude = max(valores)-min(valores)` ⚙; `concordancia = round(1.0 - amplitude, 4)`; `nivel = "ALTA" if amplitude<=0.2 else ("MEDIA" if amplitude<=0.4 else "BAIXA")`; com 1 sinal → `concordancia=None`, `nivel="UNICO_SINAL"`
- `_verdict(favorabilidade)`: `>=0.6 FAVORAVEL`; `>=0.4 INCERTO`; senão `DESFAVORAVEL` ⚙

**Saídas**
- `dict`: `{"status": "ok", "favorabilidade": round(...,4), "veredito": _verdict(...), "concordancia", "nivel_concordancia": nivel, "sinais": {k: round(v,4)}, "n_sinais": len(sinais), "disclaimer": "heurística de consenso — não validada …"}` (ou `{"status":"sem_sinais"}`).

**Fronteiras (🌐)**
- 🌐 **Decision Ledger** (no router `gateway/routers/second_opinion.py`): `ledger.add_entry(product="second-opinion", inputs=body.model_dump() {legalscore, taxpredict_prob, pct_provimento}, outputs={veredito, favorabilidade}, sources=["legalscore","taxpredict","jurimetria"], subject_token=None)` + `log_ledger_write(has_subject_token=False)`.

---

### `services/settlement_optimizer/optimize.py` — núcleo puro (Settlement Optimizer)

**Entradas**
- `optimize_settlement(valor_causa: float, prob_favorable: float | None = None, pct_provimento: float | None = None, custo_autor: float = 0.0, custo_reu: float = 0.0)`
- `_blend_prob(prob_favorable, pct_provimento)`

**Intermediário (⚙)**
- guarda: `if valor_causa < 0: raise ValueError` (única exceção do cluster)
- `_blend_prob`: `sinais = [x for x in (prob_favorable, pct_provimento) if x is not None]`; vazio → `0.5`; senão `max(0, min(1, sum(sinais)/len(sinais)))` ⚙
- `p = _blend_prob(...)` ⚙
- `ev_autor = p*valor_causa - custo_autor` ⚙
- `ev_reu = p*valor_causa + custo_reu` ⚙
- `tem_zopa = ev_reu >= ev_autor` ⚙
- `piso = max(0.0, ev_autor)` ⚙; `teto = min(valor_causa, ev_reu)` ⚙
- `ponto_meio = round((piso+teto)/2, 2) if tem_zopa else None` ⚙

**Saídas**
- `dict`: `{"prob_procedencia": round(p,4), "valor_esperado_autor": round(ev_autor,2), "valor_esperado_reu": round(ev_reu,2), "tem_zopa", "faixa_acordo": [round(piso,2), round(teto,2)]|None, "acordo_sugerido": ponto_meio, "recomendacao": "ACORDAR" if (tem_zopa and ponto_meio is not None) else "LITIGAR", "disclaimer": "heurística de análise de decisão — não validada …"}`.

**Fronteiras (🌐)**
- 🌐 **Decision Ledger** (no router `gateway/routers/settlement_optimizer.py`): `ledger.add_entry(product="settlement-optimizer", inputs=body.model_dump() {valor_causa, prob_favorable, pct_provimento, custo_autor, custo_reu}, outputs={recomendacao, acordo_sugerido}, sources=["taxpredict","jurimetria"], subject_token=None)` + `log_ledger_write(has_subject_token=False)`.

---

## Notas de fronteira/config transversais

- **`settings` (config/secrets)** lidos: `PROTOCOLO_MODO` (default `simulacao`), `CONSUMIDOR_GOV_USER/PASSWORD` 🔒, `PROCON_SP_USER/PASSWORD` 🔒, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_MODEL_LOCAL`, `LLM_API_KEY` 🔒, `LLM_BASE_URL`, `OLLAMA_URL`, `CHROMA_URL`, `NEO4J_URL/USER/PASSWORD` 🔒.
- **LLM** (`generate_text`): provedor `ollama` (`{OLLAMA_URL}/api/generate`) ou `openai` (`{LLM_BASE_URL}/chat/completions`), temperatura 0.3; retorna `None` em falha (degradação graciosa).
- **Decision Ledger**: escolhe `PostgresDecisionLedger(tenant_id)` se `os.environ["DATABASE_URL"]` setado, senão `DecisionLedger()` in-memory; falha do ledger é engolida (não derruba a resposta).
