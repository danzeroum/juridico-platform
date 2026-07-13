# 01 — Contratos e Schemas (tipos de dado que trafegam)

Catálogo exaustivo, campo a campo, dos DTOs/contratos que cruzam fronteiras em `services/shared/contracts/*.py` e do JSON Schema neutro `schemas/alert.v1.json`. Estes arquivos são a "língua" das fronteiras (Python↔Rust via PyO3, Python↔Elixir/Oban via fila+JSON Schema, Python↔TypeScript via HTTP/JSON, Celery). Todo modelo é Pydantic `BaseModel`, na maioria `frozen=True` (imutável) e `extra="forbid"` (rejeita campos desconhecidos). Cada resposta carrega seu `contract_version`.

**Legenda:** → (vira), ⚙ (efêmero / dado que se perde), 🔒 (PII/segredo), 🌐 (cruza fronteira).

---

#### services/shared/contracts/__init__.py

Arquivo **vazio** (0 linhas / marcador de pacote). Nenhum dado trafega. Apenas torna `services.shared.contracts` importável como pacote Python.

- **Entradas:** — (nenhuma)
- **Intermediário:** — (nenhuma)
- **Saídas:** — (nenhuma)
- **Fronteiras:** — (nenhuma)

---

#### services/shared/contracts/alerts.py

Contrato da **fronteira Python↔Elixir**. `contract_version` (constante `ALERT_CONTRACT_VERSION`) = `"alerts/v1"`. Decisão de privacidade: `subject_ref` carrega apenas referências NÃO pessoais (município IBGE, CNPJ público) — nada de CPF/nome no envelope.

**Constantes de módulo**
- `ALERT_CONTRACT_VERSION: str` = `"alerts/v1"` — default de `AlertEnvelope.schema_version`.

**Enums**
- `Severity(StrEnum)`: `LOW="LOW"`, `MEDIUM="MEDIUM"`, `HIGH="HIGH"`, `CRITICAL="CRITICAL"`.
- `Channel(StrEnum)`: `WEBHOOK="webhook"`, `EMAIL="email"`, `SLACK="slack"`, `WHATSAPP="whatsapp"`.

**`AlertEnvelope`** (`frozen=True, extra="forbid"`) — mensagem versionada e imutável; contrato com o Elixir.
- **Entradas:**
  - `schema_version: str` — default `ALERT_CONTRACT_VERSION` (`"alerts/v1"`); no schema é `const "alerts/v1"` — origem: publisher
  - `alert_id: str` — UUID, chave de idempotência (insert ON CONFLICT DO NOTHING); schema `minLength:1` — origem: regra/produtor
  - `dedup_key: str` — chave de deduplicação temporal (cooldown 24h); schema `minLength:1` — origem: regra
  - `rule_id: str` — schema `minLength:1` — origem: regra
  - `severity: Severity` — enum (LOW/MEDIUM/HIGH/CRITICAL) — origem: regra
  - `subject_ref: dict[str, str]` — `default_factory=dict`; somente refs não pessoais (município_ibge, cnpj) — origem: enriquecimento 🔒(explicitamente sem PII)
  - `payload: dict[str, Any]` — `default_factory=dict`; livre — origem: regra
  - `channels: list[Channel]` — schema `minItems:1` — origem: config da regra
  - `occurred_at: datetime` — schema `format:date-time` — origem: momento do gatilho
  - `enrichment: bool` — default `False` — origem: pipeline
- **Intermediário:** ⚙ nenhum campo derivado interno; o envelope é passado inteiro ao publisher.
- **Saídas:**
  - `AlertEnvelope` inteiro → destino: `AlertPublisher.publish()` → fila Celery / outbox / HTTP webhook → consumidor Elixir/Oban
- **Fronteiras:**
  - 🌐 `AlertEnvelope` serializa Python↔JSON validado contra `schemas/alert.v1.json` (fonte de verdade honrada pelos dois lados). contract_version `"alerts/v1"`.
  - 🌐 Trafega por filas, webhooks e logs (motivo da política sem-PII em `subject_ref`).
  - 🌐 `datetime occurred_at` → string ISO-8601 (`format:date-time`) no JSON.

**`PublishReceipt`** (`frozen=True`) — recibo de publicação.
- **Entradas / Saídas:**
  - `alert_id: str` — eco do envelope publicado
  - `accepted: bool`
  - `transport: str` — `"outbox" | "http"`
  - `dedup_hit: bool` — default `False`; `True` se já existia (idempotência/cooldown)
- **Saídas:** `PublishReceipt` → retorno de `AlertPublisher.publish()` ao chamador Python.
- **Fronteiras:** 🌐 retorno da fronteira de transporte (indica se caiu em outbox ou HTTP e se houve dedup).

**`AlertPublisher(Protocol, @runtime_checkable)`** — interface estrutural.
- Atributo `name: str`; método `healthy() -> bool`; método `publish(envelope: AlertEnvelope) -> PublishReceipt`.
- **Fronteiras:** 🌐 Protocol estrutural — implementação de transporte (Celery/Elixir) satisfaz sem importar este módulo.

---

#### services/shared/contracts/scoring.py

Contrato da **fronteira Python↔Rust (PyO3)**. `CONTRACT_VERSION` = `"scoring/v1"`. Regra de ouro: só os modelos abaixo (serializáveis, imutáveis) cruzam a linha — nunca sessões de banco ou numpy arrays.

**Constantes de módulo**
- `CONTRACT_VERSION: str` = `"scoring/v1"` — default de `ScoreResult.contract_version`.

**Enums**
- `RiskLevel(StrEnum)`: `BAIXO="BAIXO"`, `MODERADO="MODERADO"`, `ALTO="ALTO"`, `CRITICO="CRITICO"`.

**`ScoreRequest`** (`frozen=True, extra="forbid"`) — entrada do cálculo.
- **Entradas:**
  - `cnpj: str` — `pattern=r"^\d{14}$"` — origem: chamador 🔒(identificador de empresa)
  - `cnae_2dig: str` — `pattern=r"^\d{2}$"` — origem: chamador
  - `features: dict[str, float]` — `default_factory=dict`; já normalizadas/derivadas pelo data-enrichment; o motor recebe números prontos, não consulta banco/rede — origem: camada Python de enriquecimento
- **Saídas:** `ScoreRequest` → `ScoreEngine.score()` (implementação Python ou Rust).
- **Fronteiras:** 🌐 cruza Python↔Rust via PyO3; features pré-computadas para que o crate Rust não faça I/O.

**`ScoreResult`** (`frozen=True, extra="forbid"`) — saída do cálculo.
- **Entradas / Saídas:**
  - `score: int` — `ge=0, le=1000`
  - `risk_level: RiskLevel` — enum
  - `confidence_interval: tuple[int, int]` — validado por `_check_ci` (lo≤hi)
  - `breakdown: dict[str, float]` — `default_factory=dict`
  - `engine: str` — `"python" | "rust"` — gravado no Decision Ledger; torna auditável qual implementação produziu o resultado
  - `contract_version: str` — default `CONTRACT_VERSION` (`"scoring/v1"`)
- **Intermediário:**
  - ⚙ `_check_ci` (model_validator `mode="after"`): desempacota `lo, hi = confidence_interval`; se `lo > hi` levanta `ValueError("confidence_interval invalido: lower > upper")`. `lo`/`hi` são efêmeros (só validação).
- **Saídas:** `ScoreResult` → retorno de `ScoreEngine.score()` → HTTP/JSON → frontend.
- **Fronteiras:**
  - 🌐 **ScoreResult ↔ LegalScoreResult** (TS: `frontend/apps/platform/lib/api/legalscore.ts`, `interface LegalScoreResult`). Python↔JSON↔TypeScript.
  - 🌐 `engine` persistido no Decision Ledger (auditoria da transição Python→Rust).
  - 🌐 `tuple[int,int] confidence_interval` → array `[lo, hi]` no JSON.

**Exceções de domínio**
- `ScoringError(RuntimeError)` — erro de domínio do scoring.
- `ScoringUnavailable(ScoringError)` — implementação escolhida indisponível/insalubre; sinaliza ao factory para cair no fallback Python puro. ⚙ controle de fluxo, não dado serializado.

**`ScoreEngine(Protocol, @runtime_checkable)`** — interface que toda implementação satisfaz.
- Atributo `name: str`; `healthy() -> bool` (auto-teste barato; confirma módulo nativo carregado); `score(request: ScoreRequest) -> ScoreResult`.
- **Fronteiras:** 🌐 Protocol estrutural — crate Rust expõe `name`/`healthy()`/`score()` sem importar este módulo.

---

#### services/shared/contracts/petibot.py

Contratos da camada **PetiBot** (Fase 4, sem LLM: seções retornam templates). Fluxo: `PetiRequest → assemble_petition() → PetiResponse`. `PETIBOT_CONTRACT_VERSION` = `"petibot/v1"`.

**Constantes / lookup**
- `PETIBOT_CONTRACT_VERSION: str` = `"petibot/v1"`.
- `SECOES_MINIMAS_POR_TIPO: dict[str, list[str]]` — tabela de seções mínimas por tipo de ação:
  - `"TRABALHISTA"` → `["DOS FATOS", "DO DIREITO", "DAS VERBAS RESCISÓRIAS", "DOS PEDIDOS"]`
  - `"CIVEL"` → `["DOS FATOS", "DO DIREITO", "DOS DANOS", "DOS PEDIDOS"]`
  - `"TRIBUTARIO"` → `["DOS FATOS", "DO DIREITO TRIBUTÁRIO", "DA ILEGALIDADE", "DOS PEDIDOS"]`
  - `"PREVIDENCIARIO"` → `["DOS FATOS", "DO DIREITO PREVIDENCIÁRIO", "DO BENEFÍCIO", "DOS PEDIDOS"]`
  - `"ADMINISTRATIVO"` → `["DOS FATOS", "DO DIREITO ADMINISTRATIVO", "DO CABIMENTO", "DOS PEDIDOS"]`
  - `"CONSUMERISTA"` → `["DOS FATOS", "DO DIREITO DO CONSUMIDOR", "DOS DANOS", "DOS PEDIDOS"]`

**Enums**
- `TipoAcao(StrEnum)`: `TRABALHISTA`, `CIVEL`, `TRIBUTARIO`, `PREVIDENCIARIO`, `ADMINISTRATIVO`, `CONSUMERISTA` (valor = nome). **Reutilizado por concilia.py** (import) e espelhado por `TipoCaso` em defensor.py.

**`PetiRequest`** (`frozen=True, extra="forbid"`)
- **Entradas:**
  - `descricao: str` — `min_length=50, max_length=5000` — origem: usuário
  - `tipo_acao: TipoAcao` — enum
  - `polo_ativo: str` — `min_length=3` — origem: usuário 🔒(parte)
  - `polo_passivo: str` — `min_length=3` 🔒(parte)
  - `valor_causa: float | None` — default `None`, `ge=0`
  - `cnpj_parte: str | None` — default `None`, `pattern=r"^\d{14}$"` 🔒
- **Saídas:** → `assemble_petition()`.

**`PetiSection`** (`frozen=True`)
- `titulo: str`; `conteudo: str`; `precedentes: list[str]` (`default_factory=list`).
- **Fronteiras:** 🌐 **PetiSection ↔ PetiSection** (TS: `frontend/apps/platform/lib/api/petibot.ts`, `interface PetiSection`). Também **reexportado dentro de `DefensorResponse.secoes`** (defensor.py importa `PetiSection`).

**`PetiResponse`** (`frozen=True, protected_namespaces=()`) — `protected_namespaces=()` liberado para permitir campos com prefixo `model_`/`risk_`/`probability_` sem warning.
- **Entradas / Saídas:**
  - `tipo_acao: str`; `polo_ativo: str`; `polo_passivo: str`
  - `secoes: list[PetiSection]`
  - `precedentes_encontrados: int` — `ge=0`
  - `risk_score: int | None` — default `None` (vem do LegalScore)
  - `probability_favorable: float | None` — default `None` (vem do TaxPredict)
  - `computed_at: str`
  - `contract_version: str` — default `PETIBOT_CONTRACT_VERSION` (`"petibot/v1"`)
- **Intermediário:** ⚙ RAG (ChromaDB + BGE-M3) fornece precedentes; degradação graciosa se offline — os hits crus se perdem, só `precedentes_encontrados`/`precedentes` sobrevivem.
- **Fronteiras:** 🌐 **PetiResponse ↔ PetiResult** (TS `petibot.ts`, `interface PetiResult`). Python↔JSON↔TS.

---

#### services/shared/contracts/concilia.py

Contratos **ConciliaIA** (Fase 4). Combina prior histórico por tipo de ação + probabilidade TaxPredict + risco do réu (LegalScore) para recomendar faixa de acordo. Fluxo: `ConciliaRequest → recommend_settlement() → ConciliaResponse`. `CONCILIA_CONTRACT_VERSION` = `"concilia/v1"`. **Importa `TipoAcao` de petibot.py.**

**Constantes**
- `CONCILIA_CONTRACT_VERSION: str` = `"concilia/v1"`.

**`ConciliaRequest`** (`frozen=True, extra="forbid"`)
- **Entradas:**
  - `descricao: str` — `min_length=20, max_length=2000`
  - `valor_causa: float` — `gt=0`
  - `tipo_acao: TipoAcao` — enum importado de petibot
  - `cnpj_reu: str | None` — default `None`, `pattern=r"^\d{14}$"` 🔒
  - `cnpj_autor: str | None` — default `None`, `pattern=r"^\d{14}$"` 🔒
- **Saídas:** → `recommend_settlement()`.

**`ConciliaFator`** (`frozen=True`)
- `nome: str`; `impacto: float` (`ge=-1.0, le=1.0`); `descricao: str`.
- **Fronteiras:** 🌐 **ConciliaFator ↔ ConciliaFator** (TS `concilia.ts`, `interface ConciliaFator`).

**`ConciliaResponse`** (`frozen=True`)
- **Entradas / Saídas:**
  - `valor_minimo: float` — `ge=0`
  - `valor_sugerido: float` — `ge=0`
  - `valor_maximo: float` — `ge=0`
  - `percentual_causa: float` — `ge=0, le=1.0`
  - `fatores: list[ConciliaFator]` — `default_factory=list`
  - `risco_reu: int | None` — default `None` (vem do LegalScore)
  - `probabilidade_procedencia: float | None` — default `None` (vem do TaxPredict)
  - `computed_at: str`
  - `contract_version: str` — default `CONCILIA_CONTRACT_VERSION` (`"concilia/v1"`)
- **Intermediário:** ⚙ prior histórico, score do réu e probabilidade TaxPredict são combinados; entradas cruas se perdem, sobram os `fatores` sumarizados.
- **Fronteiras:** 🌐 **ConciliaResponse ↔ ConciliaResult** (TS `concilia.ts`, `interface ConciliaResult`). Consome saídas de LegalScore (`risco_reu`) e TaxPredict (`probabilidade_procedencia`).

---

#### services/shared/contracts/defensor.py

Contratos da camada **Defensor** (agente jurídico de IA; pipeline multi-etapas). Fluxo: `DefensorRequest → run_agente() → DefensorResponse`. `DEFENSOR_CONTRACT_VERSION` = `"defensor/v1"`. **Importa `PetiSection` de petibot.py** (reaproveita montagem de peça).

**Constantes**
- `DEFENSOR_CONTRACT_VERSION: str` = `"defensor/v1"`.

**Enums**
- `Canal(StrEnum)` — foro/destino do protocolo: `PROCON="PROCON"`, `CONSUMIDOR_GOV="CONSUMIDOR_GOV"`, `OUVIDORIA="OUVIDORIA"`, `CONTENCIOSO="CONTENCIOSO"`. **Reutilizado por protocolo.py** (import).
- `TipoCaso(StrEnum)` — espelha `TipoAcao` do PetiBot: `TRABALHISTA`, `CIVEL`, `TRIBUTARIO`, `PREVIDENCIARIO`, `ADMINISTRATIVO`, `CONSUMERISTA`.

**`DefensorRequest`** (`frozen=True, extra="forbid"`)
- **Entradas:**
  - `descricao: str` — `min_length=50, max_length=5000`
  - `canal: Canal` — enum
  - `tipo_caso: TipoCaso` — enum
  - `reclamante: str` — `min_length=3` 🔒(parte)
  - `reclamada: str` — `min_length=3`
  - `cnpj_reclamada: str | None` — default `None`, `pattern=r"^\d{14}$"` 🔒
  - `valor: float | None` — default `None`, `ge=0`
- **Saídas:** → `run_agente()`.

**`EventoAgente`** (`frozen=True`) — item da timeline do agente (feed ao vivo).
- `ts: str`; `evento: str`; `detalhe: str`; `status: Literal["ok","running","pending"]` = default `"ok"`.
- **Fronteiras:** 🌐 modela o feed ao vivo (`caso.classificado`, ...) enviado ao frontend.

**`DefensorResponse`** (`frozen=True, protected_namespaces=()`)
- **Entradas / Saídas:**
  - `classificacao: str`; `canal: str`
  - `eventos: list[EventoAgente]`
  - `secoes: list[PetiSection]` — reaproveitado do PetiBot
  - `precedentes_encontrados: int` — `ge=0`
  - `casos_anteriores: int` — `ge=0`
  - `subsidios: list[str]` — `default_factory=list`
  - `proximo_responsavel: str` — `"agente" | "humano"` (handoff)
  - `status: str` — ex.: `"DEFESA_PRONTA"`, `"AGUARDA_PROTOCOLO"`
  - `defesa_via: str` — default `"template"`; `"llm"` se redigida por LLM
  - `computed_at: str`
  - `contract_version: str` — default `DEFENSOR_CONTRACT_VERSION` (`"defensor/v1"`)
- **Intermediário:** ⚙ pipeline determinístico (classificar caso → consultar histórico → subsídios → casar jurisprudência → redigir → preparar protocolo); estados intermediários viram `eventos`; RAG real de jurisprudência (hits crus perdidos, sobra `precedentes_encontrados`).
- **Fronteiras:** 🌐 **DefensorResponse ↔ DefensorResult** (TS `defensor.ts`, `interface DefensorResult`; input `DefensorInput`). Encadeia com protocolo.py (Canal + reclamante/reclamada/cnpj/valor).

---

#### services/shared/contracts/protocolo.py

Contratos da **automação de protocolo** (Defensor → órgãos de defesa do consumidor). Fluxo: `ProtocoloRequest → protocolar() → ProtocoloResultado`. `PROTOCOLO_CONTRACT_VERSION` = `"protocolo/v1"`. **Importa `Canal` de defensor.py.** SEGURANÇA: modo padrão é SIMULAÇÃO; submissão real exige `PROTOCOLO_MODO=real` + credenciais + host na allowlist.

**Constantes**
- `PROTOCOLO_CONTRACT_VERSION: str` = `"protocolo/v1"`.

**Enums**
- `ProtocoloModo(StrEnum)`: `SIMULACAO="simulacao"`, `REAL="real"`.
- `ProtocoloStatus(StrEnum)`: `SIMULADO="SIMULADO"` (nada submetido), `ENVIADO="ENVIADO"` (submissão real ok), `FALHA="FALHA"` (tentativa real falhou), `AGUARDA_CREDENCIAIS="AGUARDA_CREDENCIAIS"` (real sem credenciais), `CANAL_NAO_SUPORTADO="CANAL_NAO_SUPORTADO"` (sem driver para o canal).

**`ProtocoloRequest`** (`frozen=True, extra="forbid"`)
- **Entradas:**
  - `canal: Canal` — enum importado de defensor
  - `reclamante: str` — `min_length=3` 🔒(parte)
  - `reclamada: str` — `min_length=3`
  - `cnpj_reclamada: str | None` — default `None`, `pattern=r"^\d{14}$"` 🔒
  - `resumo: str` — `min_length=20, max_length=5000`
  - `defesa: str | None` — default `None`, `max_length=20000`
  - `valor: float | None` — default `None`, `ge=0`
  - `anexos: list[str]` — `default_factory=list`
- **Saídas:** → `protocolar()` → AÇÃO EXTERNA com efeito legal (submissão a portal Procon/Consumidor.gov/Ouvidoria).

**`ProtocoloResultado`** (`frozen=True`)
- **Entradas / Saídas:**
  - `canal: str`
  - `modo: str` — `"simulacao" | "real"`
  - `status: str` — valor de `ProtocoloStatus`
  - `numero_protocolo: str | None` — default `None`
  - `url: str | None` — default `None`
  - `mensagem: str`
  - `enviado_em: str`
  - `contract_version: str` — default `PROTOCOLO_CONTRACT_VERSION` (`"protocolo/v1"`)
- **Fronteiras:**
  - 🌐 `protocolar()` faz submissão real a portal externo (HTTP) quando `modo=real` 🔒(credenciais de portal, host allowlist).
  - 🌐 `ProtocoloResultado` → HTTP/JSON → frontend. Sem interface TS dedicada localizada em `lib/api/` (sem par TS conhecido).

---

#### services/shared/contracts/taxpredict.py

Contrato da camada **TaxPredict** (Fase 3b). Fluxo: `TaxPredictRequest → predict() → TaxPredictResponse`. `TAXPREDICT_CONTRACT_VERSION` = `"taxpredict/v1"`. Modelo Bayesiano: trace pré-carregado no startup; `predict()` condiciona via `pm.set_data()` (MCMC nunca no path da request). RAG: ChromaDB + BGE-M3 (Ollama).

**Constantes / lookup**
- `TAXPREDICT_CONTRACT_VERSION: str` = `"taxpredict/v1"`.
- `PRIOR_NACIONAL: float` = `0.30` (fallback quando trace não carregado).
- `PRIOR_CI_LOWER: float` = `0.10`.
- `PRIOR_CI_UPPER: float` = `0.55`.
- `_ANO_REF: int` = `2024` (ano de referência da feature `recencia`).
- `_MATERIA_INDICADOR: dict[str, float]` — peso por matéria p/ feature `indicador_economico` (0.0–1.0):
  - `"PIS_COFINS"→0.80`, `"IRPJ"→0.70`, `"CSLL"→0.60`, `"ICMS"→0.50`, `"IPI"→0.40`, `"ISS"→0.30`, `"SIMPLES"→0.20`. Fallback `.get(..., 0.50)`.

**Enums**
- `Materia(StrEnum)`: `PIS_COFINS`, `IRPJ`, `CSLL`, `ICMS`, `IPI`, `ISS`, `SIMPLES` (valor = nome).
- `Decisao(StrEnum)`: `FAVORAVEL`, `DESFAVORAVEL`, `PARCIAL`, `DESCONHECIDO`.

**`TaxPredictRequest`** (`frozen=True, extra="forbid"`)
- **Entradas:**
  - `descricao: str` — `min_length=20, max_length=2000`
  - `materia: Materia` — enum
  - `valor: float | None` — default `None`, `ge=0.0`
  - `orgao_autuante: str | None` — default `None`
  - `ano_autuacao: int | None` — default `None`, `ge=2000, le=2100`
- **Saídas:** → `predict()` e → `extract_features()`.

**`JurisprudenciaHit`** (`frozen=True`) — hit do RAG.
- `doc_id: str`; `similarity: float` (`ge=0.0, le=1.0`); `ementa: str`; `decisao: Decisao` = default `Decisao.DESCONHECIDO`; `tribunal: str | None` = `None`; `ano: int | None` = `None`.

**`TaxPredictResponse`** (`frozen=True, protected_namespaces=()`)
- **Entradas / Saídas:**
  - `materia: str`
  - `probability: float` — `ge=0.0, le=1.0`
  - `ci_lower: float` — `ge=0.0, le=1.0`
  - `ci_upper: float` — `ge=0.0, le=1.0`
  - `rag_hits: int` — `ge=0`
  - `jurisprudencias: list[JurisprudenciaHit]` — `default_factory=list`
  - `features_used: dict[str, float]` — `default_factory=dict`
  - `computed_at: str`
  - `model_version: str` — (por isso `protected_namespaces=()`)
  - `is_fallback: bool` — default `False` (True quando usa `PRIOR_NACIONAL`)
  - `contract_version: str` — default `TAXPREDICT_CONTRACT_VERSION` (`"taxpredict/v1"`)
- **Fronteiras:**
  - 🌐 **TaxPredictResponse ↔ TaxPredictResult** (TS `taxpredict.ts`, `interface TaxPredictResult`; input `TaxPredictInput`).
  - 🌐 Recalibração agendada em Celery Beat (trace recarregado fora do path).

**Helper puro `extract_features(request: TaxPredictRequest) -> dict[str, float]`** (determinístico, sem I/O)
- **Entradas:** `request.valor`, `request.ano_autuacao`, `request.materia`.
- **Intermediário (⚙ efêmeros):**
  - ⚙ `valor_log` = `math.log10(request.valor + 1) / 10.0` se `valor` truthy senão `0.0` (escala 0..~0.6 até 1B)
  - ⚙ `anos_atras` = `_ANO_REF - (request.ano_autuacao or _ANO_REF)`
  - ⚙ `recencia` = `max(0.0, min(1.0, 1.0 - anos_atras * 0.1))` (1.0 em 2024; −0.1/ano; piso 0.0)
  - ⚙ `indicador_economico` = `_MATERIA_INDICADOR.get(str(request.materia), 0.50)`
- **Saídas:** `dict` → `{"valor_log": round(valor_log,4), "recencia": round(recencia,4), "indicador_economico": indicador_economico}` → alimenta `pm.set_data()` e `TaxPredictResponse.features_used`.

---

#### services/shared/contracts/fiscal.py

Contratos da camada **FiscalEngine (NCM + ICMS)** — módulo 9. Fluxo: `NcmTriageRequest → engine.classify() → NcmTriageResult`. `FISCAL_CONTRACT_VERSION` = `"fiscal/v1"`. Determinístico por design (auditabilidade). `classify()` é puro (não toca o Decision Ledger; ancoragem é etapa separada). Fundamentos legais: Res. SF 22/1989 (7%/12%), Res. SF 13/2012 (4% importado >40%), DIFAL EC 87/2015 + LC 190/2022.

**Constantes / lookup**
- `FISCAL_CONTRACT_VERSION: str` = `"fiscal/v1"`.
- `SUL_SUDESTE: frozenset` = `{"SP","RJ","MG","PR","SC","RS"}` (Sudeste + Sul, exceto ES) — regra geográfica do interestadual.
- `ALIQUOTA_INTER_REDUZIDA: float` = `7.0`.
- `ALIQUOTA_INTER_PADRAO: float` = `12.0`.
- `ALIQUOTA_INTER_IMPORTADO: float` = `4.0`.
- `CONTEUDO_IMPORTACAO_LIMIAR: float` = `40.0` (% — acima disso importado usa 4%).
- Regex de módulo: `_WS = re.compile(r"\s+")`, `_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")`.

**Enums**
- `UF(StrEnum)`: 27 unidades — `AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, PR, PE, PI, RJ, RN, RS, RO, RR, SC, SP, SE, TO` (valor = nome).
- `FonteRegra(StrEnum)`: `TIPI="TIPI"` (lookup exato NCM/IPI na TIPI RFB), `SENADO="SENADO"` (alíquota interestadual), `CONFAZ="CONFAZ"` (convênio benefício/ST/isenção), `SEFAZ="SEFAZ"` (alíquota interna estadual), `FUZZY="FUZZY"` (NCM por correspondência aproximada), `RAG="RAG"` (NCM por busca semântica).

**`NcmCandidate`** (`frozen=True, extra="forbid"`)
- `ncm_codigo: str` — `pattern=r"^\d{8}$"`; `descricao: str`; `confidence: float` (`ge=0.0, le=1.0`); `fonte_regra: FonteRegra`.

**`NcmTriageRequest`** (`frozen=True, extra="forbid"`)
- **Entradas:**
  - `descricao: str` — `min_length=1, max_length=2000`
  - `uf_origem: UF` — enum
  - `uf_destino: UF` — enum
  - `data: date | None` — default `None`
  - `ncm_hint: str | None` — default `None`, `pattern=r"^\d{8}$"`
  - `importado: bool` — default `False`
  - `conteudo_importacao_pct: float | None` — default `None`, `ge=0.0, le=100.0`
- **Saídas:** → `engine.classify()`.

**`IcmsResolution`** (`frozen=True, extra="forbid"`) — todos `float | None` default `None`:
- `interna_pct`; `fcp_pct`; `interna_efetiva_pct`; `interestadual_pct`; `difal_pct`; `fundamento_legal: str | None`.

**`NcmTriageResult`** (`frozen=True, extra="forbid"`)
- **Entradas / Saídas:**
  - `sku_descricao: str`
  - `suggested_ncm: NcmCandidate | None` — default `None`
  - `icms: IcmsResolution`
  - `categoria: str | None` — default `None`
  - `conflito_detectado: bool` — default `False`
  - `observacoes: list[str]` — `default_factory=list`
  - `decision_proof: str | None` — default `None`; prova de inclusão (`get_proof`), preenchida na ancoragem
  - `contract_version: str` — default `FISCAL_CONTRACT_VERSION` (`"fiscal/v1"`)
- **Fronteiras:**
  - 🌐 `decision_proof` liga ao Decision Ledger (Merkle proof — individual=1 entrada; lote=1 por job com raiz Merkle, ver `services/fiscal/batch/anchor.py`).
  - 🌐 `NcmTriageResult` → HTTP/JSON → frontend (sem interface TS localizada em `lib/api/`).

**`SpreadsheetJobResponse`** (`frozen=True, extra="forbid"`) — resposta **202** do enriquecimento assíncrono de planilhas.
- `job_id: str`; `status_url: str`; `submitted_at: str`; `expected_completion: str | None` = `None`; `contract_version: str` = `FISCAL_CONTRACT_VERSION`.
- **Fronteiras:** 🌐 HTTP 202 assíncrono; job processado via Celery (`status_url` para polling).

**Helper `normalize_descricao(s: str) -> str`** (determinístico, sem I/O)
- **Entradas:** `s: str` (descrição comercial).
- **Intermediário (⚙):** ⚙ retorna `""` se `s` falsy; ⚙ `nfkd = unicodedata.normalize("NFKD", s)`; ⚙ `sem_acento` = remove combining chars; ⚙ `limpo = _NON_ALNUM.sub(" ", sem_acento.lower())`.
- **Saídas:** `_WS.sub(" ", limpo).strip()` — minúsculas, sem acento, sem pontuação, espaços colapsados.

**Helper `aliquota_interestadual(uf_origem, uf_destino, *, importado=False, conteudo_importacao_pct=None) -> tuple[float, str]`**
- **Entradas:** `uf_origem: str`, `uf_destino: str`, `importado: bool`, `conteudo_importacao_pct: float | None`.
- **Intermediário (⚙):**
  - ⚙ ramo importado: se `importado and (conteudo_importacao_pct is None or > CONTEUDO_IMPORTACAO_LIMIAR)` → retorna `(ALIQUOTA_INTER_IMPORTADO=4.0, "Resolução SF 13/2012")`
  - ⚙ `origem_privilegiada = uf_origem in SUL_SUDESTE`
  - ⚙ `destino_beneficiado = (uf_destino not in SUL_SUDESTE) or (uf_destino == "ES")`
- **Saídas:** `(7.0, "Resolução SF 22/1989 (art. 1º)")` se origem privilegiada e destino beneficiado; senão `(12.0, "Resolução SF 22/1989 (art. 1º)")`.

**Helper `compute_difal(interna_efetiva_destino: float | None, interestadual: float | None) -> float | None`**
- **Entradas:** `interna_efetiva_destino`, `interestadual`.
- **Saídas:** `None` se qualquer entrada `None`; senão `round(max(0.0, interna_efetiva_destino - interestadual), 2)` (DIFAL EC 87/2015 + LC 190/2022).

---

#### schemas/alert.v1.json

**JSON Schema draft 2020-12** — contrato neutro de linguagem para alertas; **fonte de verdade** validada pelo publisher Python (`AlertEnvelope`) **e** pelo consumidor Elixir/Oban. `$id`: `https://juridico-platform/schemas/alert.v1.json`. Versionado: mudanças incompatíveis criam `alert.v2.json`.

- **Meta:** `$schema` draft 2020-12; `title: "AlertEnvelope"`; `type: object`; `additionalProperties: false` (espelha `extra="forbid"` do Pydantic).
- **Entradas / Campos (`required`: schema_version, alert_id, dedup_key, rule_id, severity, channels, occurred_at):**
  - `schema_version: string` — `const "alerts/v1"`
  - `alert_id: string` — `minLength:1`
  - `dedup_key: string` — `minLength:1`
  - `rule_id: string` — `minLength:1`
  - `severity: string` — `enum ["LOW","MEDIUM","HIGH","CRITICAL"]`
  - `subject_ref: object` — `additionalProperties {type:string}`; só refs não pessoais (município_ibge, cnpj) 🔒(política sem-PII)
  - `payload: object`
  - `channels: array` — `minItems:1`, `items {enum ["webhook","email","slack","whatsapp"]}`
  - `occurred_at: string` — `format: date-time`
  - `enrichment: boolean` — `default false`
- **Fronteiras:**
  - 🌐 **AlertEnvelope (Python, alerts.py) ↔ alert.v1.json ↔ Elixir/Oban**. contract_version `"alerts/v1"`.
  - 🌐 Note: `subject_ref`/`payload` no schema NÃO têm `required`/defaults (Pydantic usa `default_factory=dict`); `enrichment` opcional com default. `alert_id`/`dedup_key`/`rule_id` exigem `minLength:1` (Pydantic aceita string vazia — o JSON Schema é mais estrito).
  - 🌐 Parcialmente espelhado em TS por `AlertItem` (`frontend/packages/ui/src/patterns/AlertList.tsx`, campos de exibição, não 1:1).
