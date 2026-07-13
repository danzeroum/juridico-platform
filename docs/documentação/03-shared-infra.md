# 03 — Shared / Infraestrutura (ledger, LGPD, IA, storage, config)

> Catálogo de fluxo de dados EXAUSTIVO de `services/shared/` (exceto `contracts/`, coberto em outro documento).
> Escopo: 29 arquivos `.py`.

**Legenda:**
- **→** Entrada (dado que entra na função/módulo)
- **⚙** Intermediário efêmero (existe só em memória durante o processamento; não persiste)
- **Saída** dado retornado / persistido
- **🌐** Fronteira (I/O externo: rede, DB, filesystem, secret store)
- **🔒** PII ou segredo (chave, credencial, token, dado pessoal)

---

## `ledger/merkle.py` — Decision Ledger com Merkle tree

Dois backends: `DecisionLedger` (em memória, Fase 0) e `PostgresDecisionLedger` (Postgres + RLS, Fase 1c). Funções livres: `_sha256`, `_compute_merkle_root`, `_generate_proof`.

### Entradas →
- `add_entry(request_id: str, product: str, inputs: dict, outputs: dict, sources: list[str]|None, weights: dict|None, subject_token: str|None)`
  - `request_id` → identificador do request
  - `product` → nome do produto
  - `inputs` → dados técnicos do request (SEM PII — doc diz PII fica em `subject_token`)
  - `outputs` → resultado técnico
  - `sources` → lista de fontes (default `[]`)
  - `weights` → pesos aplicados (default `{}`)
  - `subject_token` 🔒 → pseudônimo do titular CIFRADO em AES-256-GCM (nunca PII em claro)
- `get_proof(entry_id: str)` → busca por `request_id`
- `verify_integrity(entry_id: str, proof: dict)` → `proof` = `{leaf_hash, proof:[{sibling,position}], root}`
- `PostgresDecisionLedger.__init__(tenant_id: str)` 🔒 → `tenant_id` (escopo RLS)

### Intermediário (⚙ efêmero)
- `_sha256(data)` → `hashlib.sha256(data.encode()).hexdigest()` (64 hex)
- `_compute_merkle_root(hashes)` → duplica último nó se camada ímpar; hash de pares concatenados até 1 raiz; vazio ⇒ `_sha256("")`
- `_generate_proof(hashes, idx)` → passos `{sibling, position}` subindo a árvore
- **Estrutura da entrada (entry dict)** montada em memória, campos EXATOS:
  - `request_id`
  - `entry_index` (= `len(self._entries)` na versão memória; `SELECT COUNT(*)` na versão Postgres)
  - `timestamp` (= `datetime.now(UTC).isoformat()`)
  - `product`
  - `inputs_hash` (= `_sha256(json.dumps(inputs, sort_keys=True))`, 64 hex)
  - `outputs_hash` (= `_sha256(json.dumps(outputs, sort_keys=True))`, 64 hex)
  - `sources`
  - `weights_applied`
  - `subject_token` 🔒
- ⚙ `leaf_hash` = `_sha256(json.dumps(entry, sort_keys=True))` (64 hex)
- ⚙ `self._leaf_hashes` (lista in-memory), `self.merkle_root` (recalculada a cada `add_entry`)
- ⚙ `_ANCHOR_INTERVAL = 1024` (frequência de checkpoint em `ledger.anchors`)
- **Merkle proof structure** (por passo): `{"sibling": <hash 64 hex>, "position": "left"|"right"}`
  - `"left"` = irmão à esquerda (nó atual é filho direito, `position % 2 == 1`)
  - `"right"` = irmão à direita (nó atual é filho esquerdo)

### Saídas
- `add_entry` retorna `{**entry, "leaf_hash": ..., "merkle_root": ...}` — ou seja: `request_id, entry_index, timestamp, product, inputs_hash, outputs_hash, sources, weights_applied, subject_token, leaf_hash, merkle_root`
- `get_proof` retorna `{entry_id, entry_index, leaf_hash, proof, root}`
- `verify_integrity` retorna `bool` (recalcula hash subindo a prova; compara com `merkle_root`/`db_root`)
- `__len__` → contagem de entradas

### Fronteiras (🌐)
- `PostgresDecisionLedger` usa `tenant_transaction(tenant_id)` de `services.shared.tenant_db` (import lazy dentro dos métodos) 🌐
- **Advisory lock** 🌐: `SELECT pg_advisory_xact_lock(hashtext(:tid)::bigint)` — serializa escritas por tenant (evita `entry_index` duplicado / bifurcação Merkle); liberado no COMMIT/ROLLBACK
- **SQL `ledger.entries`** (INSERT), colunas EXATAS: `request_id, entry_index, product, tenant_id (::uuid), inputs_hash, outputs_hash, sources (::jsonb), weights_applied (::jsonb), subject_token, leaf_hash, merkle_root`
  - Leituras: `SELECT COUNT(*) FROM ledger.entries`; `SELECT leaf_hash FROM ledger.entries ORDER BY entry_index`; `SELECT entry_index, leaf_hash FROM ledger.entries WHERE request_id = :rid`; `SELECT merkle_root FROM ledger.entries ORDER BY entry_index DESC LIMIT 1`
- **SQL `ledger.anchors`** (INSERT a cada 1024 entradas), colunas EXATAS: `anchor_at_index, merkle_root, tenant_id (::uuid)` — parâmetros `{idx, root, tenant_id}`

---

## `ledger/__init__.py`
- Docstring apenas: `"""Decision Ledger package."""`. Sem dados.

---

## `lgpd.py` — Pseudonimização LGPD (HMAC-SHA256)

Todos os registros ingeridos passam por aqui ANTES de persistir.

### Entradas → 🔒
- `hash_cpf(cpf: str)` 🔒 → CPF (limpo com `re.sub(r"\D","",cpf)`)
- `hash_name(name: str)` 🔒 → nome (`.strip().lower()`)
- `hash_user_id(user_id: str)` 🔒 → user_id
- `pseudonymize_process_record(record: dict)` 🔒 → registro de processo. Campos PII de entrada:
  - CPFs: `parte_cpf`, `cpf_autor`, `cpf_reu`, `cpf_advogado`
  - Nomes: `parte_nome`, `nome_autor`, `nome_reu`
  - Removidos (endereço): `endereco`, `cep`, `logradouro`, `bairro`, `complemento`
  - **CNPJ mantido** (dado público) — não é tocado
- `k_anonymize(records, quasi_identifiers, k=5)` → suprime grupos com < k entidades
- `rotate_key_reprocess(records, new_key_hex: str)` 🔒 → nova chave HMAC em hex

### Intermediário (⚙ efêmero)
- ⚙🔒 `_HMAC_KEY: bytes|None` — cache global da chave (carregada lazy via `_get_key()`)
- ⚙ `_hmac_hex(value)` = `hmac.new(_get_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()` → **64 hex chars, sem truncamento**
- **Prefixos de domínio HMAC** (EXATOS):
  - CPF: `hash_cpf` → `_hmac_hex(f"cpf:{cpf_clean}")`
  - Nome: `hash_name` → `_hmac_hex(f"name:{name.strip().lower()}")`
  - User: `hash_user_id` → `_hmac_hex(f"uid:{user_id}")`
- ⚙ `k_anonymize` usa `collections.Counter` sobre tuplas de quasi-identifiers

### Saídas
- `hash_cpf/hash_name/hash_user_id` → string hex de 64 chars
- `pseudonymize_process_record` → cópia do record com campos `<field>_hash` adicionados e PII/endereço removidos (`safe.pop`)
- `k_anonymize` → lista filtrada (grupos com contagem ≥ k)
- `rotate_key_reprocess` → devolve `records` (efeito colateral: sobrescreve `_HMAC_KEY = bytes.fromhex(new_key_hex)`)

### Fronteiras (🌐) 🔒
- **HMAC key source**: `load_secret("HMAC_KEY")` de `services.shared.config` 🌐🔒 — Docker Secret `/run/secrets/HMAC_KEY` ou env `HMAC_KEY`. Ausente ⇒ `RuntimeError`.
- Determinístico: mesmo CPF + mesma chave → mesmo hash (permite join interno); rotação de chave ⇒ hash diferente.

---

## `lgpd_crypto.py` — Crypto-shredding AES-256-GCM por titular

### Entradas → 🔒
- `encrypt_for_ledger(pseudonym: str, tenant_id: str)` 🔒 → `pseudonym` (já pseudonimizado, ex.: HMAC do CNPJ/CPF) + `tenant_id`
- `decrypt_from_ledger(token: str, pseudonym: str, tenant_id: str)` 🔒 → token base64url + pseudonym + tenant (auditoria autorizada)
- `erase_titular(pseudonym: str, tenant_id: str)` 🔒 → apaga chave (crypto-shredding / direito ao esquecimento)
- `is_erased(pseudonym: str, tenant_id: str)` → verifica se chave foi apagada

### Intermediário (⚙ efêmero)
- ⚙🔒 `_KEY_STORE: dict[str, bytes]` — dicionário em memória chave→bytes (dev; produção = KMS)
- ⚙ `_STORE_LOCK = threading.Lock()`
- ⚙ `_KEY_SIZE = 32` (AES-256)
- **Key store key** (`_key_id`) EXATO: `f"{tenant_id}:{pseudonym}"` (escopo por tenant)
- ⚙🔒 `key = _load_or_create_key(kid)` → `os.urandom(32)` se ausente
- ⚙ `iv = os.urandom(12)` (96-bit IV, recomendação NIST)
- ⚙ `ciphertext_and_tag = AESGCM(key).encrypt(iv, pseudonym.encode(), None)`
- **Formato do subject_token** (EXATO): `base64.urlsafe_b64encode(iv[12] + ciphertext + tag[16])` = `base64url(iv_12_bytes || ciphertext || tag_16_bytes)`. Decrypt: `raw[:12]` = iv, `raw[12:]` = ciphertext+tag.

### Saídas
- `encrypt_for_ledger` → `subject_token` string base64url (persistido no Ledger)
- `decrypt_from_ledger` → pseudônimo em claro 🔒 (após decrypt) — chave apagada ⇒ `KeyError`; token adulterado ⇒ `InvalidTag`
- `erase_titular` → `bool` (True se a chave existia)
- `is_erased` → `bool`

### Fronteiras (🌐)
- Chama `log_pii_decrypt(pseudonym, tenant_id)` no decrypt e `log_pii_erase(pseudonym, tenant_id, existed)` no erase (de `services.shared.audit_log`) 🌐
- Produção: `_KEY_STORE` → KMS (AWS KMS / HashiCorp Vault / GCP KMS); em K8s, External Secrets Operator 🌐🔒

---

## `audit_log.py` — Audit trail estruturado de PII

Logger `audit` (separado da aplicação); emite JSON; nunca loga PII em claro.

### Entradas →
- `log_ledger_write(*, request_id, product, tenant_id: str|None, entry_index: int, has_subject_token: bool)`
- `log_pii_decrypt(*, pseudonym: str 🔒, tenant_id: str, caller: str = "unknown")`
- `log_pii_erase(*, pseudonym: str 🔒, tenant_id: str, existed: bool)`

### Intermediário (⚙ efêmero)
- ⚙ `_pseudonym_sha256(pseudonym)` = `hashlib.sha256(pseudonym.encode()).hexdigest()` — correlação sem revelar valor (o pseudônimo em claro NUNCA vai para o log)
- ⚙ `_audit_lock = threading.Lock()`
- ⚙ `_emit(event_type, fields)` monta `{event, timestamp (now UTC iso), **fields}`

### Saídas (🌐 via logger `audit`)
- Evento `ledger.write`: `{event, timestamp, request_id, product, tenant_id, entry_index, has_subject_token}`
- Evento `pii.decrypt`: `{event, timestamp, pseudonym_sha256, tenant_id, caller}`
- Evento `pii.erase`: `{event, timestamp, pseudonym_sha256, tenant_id, existed}`

### Fronteiras (🌐)
- `logging.getLogger("audit").info(json.dumps(record, ensure_ascii=False))` 🌐

---

## `tenant_db.py` — Conexão com isolamento de tenant (RLS + PgBouncer)

### Entradas → 🔒
- `tenant_transaction(tenant_id: str)` 🔒 → `tenant_id` (obrigatório; vazio ⇒ `ValueError` fail-closed)
- `get_db_connection` = alias de `tenant_transaction`
- `get_engine()` → engine sem contexto de tenant (para queries fora de RLS: `tenant.tenants`, `tenant.users`)

### Intermediário (⚙ efêmero)
- ⚙ `_get_engine()` (`@lru_cache(maxsize=1)`) — reusa `services.shared.db.engine` se disponível; senão `create_engine(DATABASE_URL, pool_pre_ping=True, future=True)`

### Saídas
- `tenant_transaction` → context manager que faz `yield conn` (SQLAlchemy `Connection`) dentro de `engine.begin()`
- `get_engine()` → `Engine`

### Fronteiras (🌐)
- Lê `os.environ["DATABASE_URL"]` 🌐 (deve apontar para PgBouncer porta 6432)
- Por transação executa: `SELECT set_config('app.tenant_id', :tid, true)` — equivalente parametrizável/injection-safe de `SET LOCAL`; revertido no COMMIT/ROLLBACK (seguro para reuso pelo PgBouncer `pool_mode=transaction`) 🌐
- GUC `app.tenant_id` alimenta as policies RLS de `bootstrap-db.sql` (`current_setting('app.tenant_id')` sem `missing_ok` ⇒ fail-closed)

---

## `db.py` — Engine PostgreSQL (SQLAlchemy + PgBouncer)

### Entradas →
- Nenhuma direta; consome `settings.DATABASE_URL` 🔒 (usuário:senha no DSN)

### Intermediário (⚙ efêmero)
- ⚙ `engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10, echo=False)`
- ⚙ `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`
- ⚙ `Base = declarative_base()`

### Saídas
- `get_db()` → generator FastAPI dependency; `yield SessionLocal()`; fecha no finally
- Exporta `engine`, `SessionLocal`, `Base`

### Fronteiras (🌐)
- Conexão PostgreSQL via PgBouncer (porta 6432) 🌐 — SEMPRE via PgBouncer, nunca direto

---

## `redis_client.py` — Cliente Redis compartilhado

### Entradas →
- Consome `settings.REDIS_URL`

### Intermediário (⚙ efêmero)
- ⚙ `_redis_client` (singleton global, lazy)

### Saídas
- `get_redis()` → `redis.Redis`

### Fronteiras (🌐) — parâmetros de conexão EXATOS
- `redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=5, socket_timeout=5, retry_on_timeout=True)` 🌐
- Usado para cache de LLM, sessões e filas Celery

---

## `config.py` — Settings (env vars / Docker Secrets)

### Entradas → 🔒
- `load_secret(name: str)` → lê `/run/secrets/<name>` (filesystem) se existir; senão `os.getenv(name.upper(), '')` 🌐🔒
- Todas as propriedades de `_Settings` são lazy (avaliadas a cada acesso)

### Saídas / Configurações expostas (nome → default → fonte)
| Setting | Default | Fonte |
|---|---|---|
| `DATAJUD_API_URL` | `https://api-publica.datajud.cnj.jus.br` | env |
| `DATAJUD_TOKEN` 🔒 | `""` | secret `datajud_token` → env `DATAJUD_TOKEN` |
| `PGFN_API_URL` | `https://www.regularize.pgfn.gov.br/api` | env |
| `RECEITA_API_URL` | `https://publica.cnpj.ws/cnpj` | env |
| `ABJ_ENABLED` | `false` | env (`1/true/yes`) |
| `ABJ_DATA_URL` | `""` | env |
| `REDIS_URL` | `redis://localhost:6379/0` | env |
| `OPENSEARCH_URL` | `http://opensearch:9200` | env |
| `NEO4J_URL` | `bolt://neo4j:7687` | env |
| `NEO4J_USER` | `neo4j` | env |
| `NEO4J_PASSWORD` 🔒 | `""` | secret `neo4j_password` → env `NEO4J_PASSWORD` |
| `CHROMA_URL` | `http://chromadb:8001` | env |
| `DATABASE_URL` 🔒 | `postgresql://postgres:postgres@pgbouncer:6432/juridico` | env |
| `HMAC_KEY` 🔒 | `""` | secret `hmac_key` → env `HMAC_KEY` |
| `MINIO_URL` | `http://minio:9000` | env |
| `MINIO_ACCESS_KEY` 🔒 | `minioadmin` | secret `minio_access_key` → env `MINIO_ACCESS_KEY` |
| `MINIO_SECRET_KEY` 🔒 | `minioadmin` | secret `minio_secret_key` → env `MINIO_SECRET_KEY` |
| `OLLAMA_URL` | `http://ollama:11434` | env |
| `LLM_PROVIDER` | `ollama` (`ollama`\|`openai`) | env |
| `LLM_API_KEY` 🔒 | `""` | secret `llm_api_key` → env `LLM_API_KEY` |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | env |
| `LLM_MODEL` | `gpt-4o` | env |
| `LLM_MODEL_LOCAL` | `llama3:8b` | env |
| `PROTOCOLO_MODO` | `simulacao` (`real` exige credenciais) | env |
| `CONSUMIDOR_GOV_USER` 🔒 | `""` | secret `consumidor_gov_user` → env |
| `CONSUMIDOR_GOV_PASSWORD` 🔒 | `""` | secret `consumidor_gov_password` → env |
| `PROCON_SP_USER` 🔒 | `""` | secret `procon_sp_user` → env |
| `PROCON_SP_PASSWORD` 🔒 | `""` | secret `procon_sp_password` → env |

- `settings = _Settings()` (instância singleton exportada)

### Fronteiras (🌐)
- Filesystem `/run/secrets/<name>` 🌐🔒 e variáveis de ambiente 🌐

> Nota: `load_secret` recebe o nome (ex.: `"hmac_key"`) mas o `os.getenv` usa `name.upper()` — o path de secret é case-sensitive (`/run/secrets/hmac_key`), a env var é maiúscula.

---

## `ai/generate.py` — Geração de texto LLM (Ollama / OpenAI)

Degradação graciosa: retorna `None` em qualquer falha (nunca levanta).

### Entradas → 🔒
- `generate_text(prompt: str 🔒, *, system: str|None = None 🔒, max_tokens: int = 600)` — `prompt` e `system` podem conter dados do caso

### Intermediário (⚙ efêmero)
- ⚙ `_TIMEOUT = (3, 30)` (connect, read)
- ⚙ `provider = settings.LLM_PROVIDER.lower()`
- **Payload Ollama** (`_ollama`): `{"model": settings.LLM_MODEL_LOCAL, "prompt": prompt, "stream": False, "options": {"num_predict": max_tokens, "temperature": 0.3}}` + opcional `"system"`
- **Payload OpenAI** (`_openai`): `messages=[{role:system, content:system}?, {role:user, content:prompt}]`, `{"model": settings.LLM_MODEL, "messages", "max_tokens", "temperature": 0.3}`

### Saídas
- `generate_text` → `str` (texto gerado) ou `None`
- Ollama parse: `resp.json().get("response")`; OpenAI parse: `resp.json()["choices"][0]["message"]["content"]`

### Fronteiras (🌐) 🔒
- POST `{settings.OLLAMA_URL}/api/generate` 🌐
- POST `{settings.LLM_BASE_URL}/chat/completions` com header `Authorization: Bearer {settings.LLM_API_KEY}` 🌐🔒 (retorna `None` se `LLM_API_KEY` vazia)

---

## `ai/rag.py` — RAG compartilhado (ChromaDB + BGE-M3)

### Entradas → 🔒
- `RAGEngine(collection_name="juridico")` → nome da coleção Chroma
- `_get_embedding(text: str)` → texto para embutir
- `upsert_document(doc_id: str, content: str 🔒, metadata: dict)` — conteúdo pode ser texto jurídico
- `search(query: str 🔒, n_results: int = 10, where: dict|None = None)`

### Intermediário (⚙ efêmero)
- ⚙ `self._chroma_client` (lazy) — host/port derivados de `settings.CHROMA_URL` (`.replace("http://","").split(":")[0]` e `.split(":")[-1]`)
- ⚙ `content_hash = hashlib.sha256(content.encode()).hexdigest()` (dedup por hash de conteúdo)
- ⚙ **embedding vector** `list[float]` via Ollama BGE-M3 (payload `{"model":"bge-m3","prompt":text}`); `None` ⇒ fallback embedder padrão do ChromaDB
- ⚙ `enriched_meta = {**metadata, "content_hash": content_hash}`
- ⚙ coleção criada com `metadata={"hnsw:space": "cosine"}`

### Saídas
- `upsert_document` → `bool` (False se já indexado com mesmo `content_hash`; True se upsert feito)
  - `collection.upsert(ids=[doc_id], documents=[content], embeddings=[embedding]?, metadatas=[enriched_meta])`
- `search` → `list[dict]` com `{id, document, metadata, distance}` (distance `None` se não retornado)

### Fronteiras (🌐)
- ChromaDB HTTP (`chromadb.HttpClient`) — coleção `juridico` (default) 🌐
- Ollama embeddings: POST `{settings.OLLAMA_URL}/api/embeddings` (timeout 10s, urllib) 🌐

---

## `ai/router.py` — LLM Router (local vs API paga)

### Entradas →
- `route(task_type: TaskType)`, `get_client(task_type: TaskType)`
- `TaskType` enum: `CLASSIFICATION`, `NER`, `EMBEDDING`, `GENERATION`, `REASONING`, `SUMMARIZATION`

### Intermediário (⚙ efêmero)
- ⚙ `ROUTING_TABLE` (provider/model/cost por task):
  - `CLASSIFICATION` → `{ollama, llama3:8b, 0.0}`
  - `NER` → `{ollama, llama3:8b, 0.0}`
  - `EMBEDDING` → `{ollama, bge-m3, 0.0}`
  - `GENERATION` → `{openai, gpt-4o, 0.01}`
  - `REASONING` → `{openai, gpt-4o, 0.03}`
  - `SUMMARIZATION` → `{openai, gpt-4o-mini, 0.002}`

### Saídas
- `route` → dict de config; `get_client` → `_ollama_client` = `{url: settings.OLLAMA_URL, model}` ou `_openai_client` = `{api_key: settings.LLM_API_KEY 🔒, model}`
- `llm_router = LLMRouter()` (singleton)

### Fronteiras (🌐)
- Clientes são stubs (`TODO Fase 1`); expõem `settings.OLLAMA_URL` / `settings.LLM_API_KEY` 🔒 mas não fazem I/O ainda

---

## `ai/cache.py` — Memoização de chamadas LLM (Redis)

### Entradas → 🔒
- `LLMMemoizer.__call__(model="gpt-4o")` → decorator; envolve função cujo primeiro arg/`prompt` kwarg é o prompt 🔒
- `template_ver = getattr(func, "__version__", "1")`

### Intermediário (⚙ efêmero)
- ⚙ `self.ttl = 30 * 24 * 3600` (30 dias)
- ⚙ **cache_key** = `hashlib.sha256(f"{model}:{template_ver}:{str(prompt)}".encode()).hexdigest()`
- ⚙ chave Redis EXATA: `f"llm:{cache_key}"`

### Saídas
- HIT: `json.loads(cached)`; MISS: executa `func`, grava `r.setex("llm:{cache_key}", ttl, json.dumps(result))`
- `memoizer = LLMMemoizer()` (singleton)

### Fronteiras (🌐)
- Redis via `get_redis()` — `r.get`/`r.setex` na chave `llm:<sha256>` 🌐

---

## `ai/__init__.py`
- Arquivo vazio (1 linha). Sem dados.

---

## `alerts/publishers.py` — Publishers de alertas (Outbox / HTTP)

### Entradas →
- `OutboxAlertPublisher(db_conn)` → conexão psycopg-compatível (reusa transação de negócio para atomicidade)
- `HttpAlertPublisher(base_url: str, client: httpx.Client|None)` → URL do serviço Elixir
- `publish(envelope: AlertEnvelope)` → envelope versionado (campos: `schema_version, alert_id, dedup_key, rule_id, severity, subject_ref, payload, channels, occurred_at, enrichment`)
- `get_alert_publisher(backend: str, *, db_conn=None, elixir_url="")` → seleção por `ALERT_BACKEND`

### Intermediário (⚙ efêmero)
- ⚙ `HttpAlertPublisher._url = base_url.rstrip("/") + "/api/v1/alertas/publicar"`
- ⚙ `envelope.model_dump_json()` (serialização do envelope)

### Saídas
- `publish` → `PublishReceipt(alert_id, accepted, transport, dedup_hit)`
  - Outbox: `dedup_hit = not inserted` (inserted = `cur.fetchone() is not None`)
  - HTTP: `accepted = status in (202,409)`, `dedup_hit = status == 409`
- `healthy()` → bool

### Fronteiras (🌐)
- **SQL `alerts_outbox`** (INSERT), colunas EXATAS gravadas: `alert_id, dedup_key, envelope (::jsonb)` — `ON CONFLICT (alert_id) DO NOTHING RETURNING alert_id`
  - Valores: `{alert_id: envelope.alert_id, dedup_key: envelope.dedup_key, envelope: envelope.model_dump_json()}` 🌐
  - `healthy()` Outbox: `SELECT 1`
  - **DDL da tabela** (do docstring): colunas `alert_id TEXT PK, dedup_key TEXT NOT NULL, envelope JSONB NOT NULL, status TEXT DEFAULT 'pending' (pending|claimed|done|failed), attempts INT DEFAULT 0, available_at TIMESTAMPTZ DEFAULT now(), created_at TIMESTAMPTZ DEFAULT now()`; índices `ix_outbox_dispatch (status, available_at)`, `ix_outbox_dedup_key (dedup_key)`
- **HTTP POST** para Elixir 🌐: `POST {base_url}/api/v1/alertas/publicar`
  - Body: `envelope.model_dump_json()`
  - Headers EXATOS: `Content-Type: application/json`, `X-Contract-Version: {ALERT_CONTRACT_VERSION}` (= `"alerts/v1"`)
  - Timeout httpx 5.0s; `healthy()`: `GET {.../api/v1/alertas}/health` esperando 200
- Fronteira Python↔Elixir: o Oban lê A MESMA tabela `alerts_outbox`; `ALERT_BACKEND=outbox` (default) | `http`

---

## `alerts/tests/test_alert_contract.py` — Testes de contrato (dados de teste)

### Entradas / dados de teste (fixtures)
- `SCHEMA_PATH` = `<repo>/schemas/alert.v1.json` (`parents[4]`) 🌐 (lê filesystem)
- `_envelope(**overrides)` — **AlertEnvelope de exemplo** (valores literais):
  - `alert_id="11111111-1111-1111-1111-111111111111"`
  - `dedup_key="arrecadacao_critica:3550308:2026-06"`
  - `rule_id="arrecadacao_critica"`
  - `severity=Severity.CRITICAL`
  - `subject_ref={"municipio_ibge": "3550308"}`
  - `payload={"delta_arrecadacao_yoy": -0.27, "z_score": 3.2}`
  - `channels=[Channel.WEBHOOK, Channel.EMAIL]`
  - `occurred_at=datetime(2026, 6, 16, 12, 0, tzinfo=UTC)`

### Saídas / asserções
- valida envelope contra `alert.v1.json`; `schema_version == ALERT_CONTRACT_VERSION` (`alerts/v1`); `subject_ref` só aceita strings (int `numero=123` ⇒ inválido); `channels` não-vazio; campo desconhecido (`campo_fantasma`/`campo_desconhecido`) rejeitado por `extra="forbid"` + `additionalProperties:false`

### Fronteiras (🌐)
- Leitura de `schemas/alert.v1.json` do filesystem 🌐

---

## `alerts/__init__.py` e `alerts/tests/__init__.py`
- Ambos vazios (1 linha). Sem dados.

---

## `storage/minio_client.py` — Camada bronze (MinIO, JSONL particionado)

### Entradas → 🔒
- `ensure_bucket(bucket, client=None)`; `bronze_bucket(source)`; `put_json(bucket, key, obj: dict, client=None)`; `put_jsonl(source, date_str, records: list[dict] 🔒, client=None)`
  - `records` podem conter dados brutos ingeridos (bronze = dado bruto imutável)

### Intermediário (⚙ efêmero)
- ⚙ **bucket name**: `bronze_bucket(source)` = `f"bronze-{source.lower()}"` (ex.: `DATAJUD` → `bronze-datajud`)
- ⚙ **partition key**: `_partition_key(date_str, ext)` = `f"dt={date_str}/part-{uuid.uuid4().hex}.{ext}"` (estilo Hive; ext `jsonl`)
- ⚙ `put_json` body = `json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")`, content_type `application/json`
- ⚙ `put_jsonl` body = `"\n".join(json.dumps(r, ...) for r in records).encode("utf-8")`, content_type `application/x-ndjson`

### Saídas
- `put_json` → `key` (str)
- `put_jsonl` → `f"{bucket}/{key}"` (ou `None` se `records` vazio); cada chamada gera nova partição (replayable); dedup lógica fica na camada silver
- `_client()` = `Minio(host, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=<url https>)`

### Fronteiras (🌐) 🔒
- MinIO (`minio.Minio`, lazy) — host de `settings.MINIO_URL` (sem `http(s)://`), credenciais `settings.MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` 🌐🔒
- `bucket_exists`/`make_bucket` (buckets privados por padrão), `put_object` 🌐

---

## `storage/neo4j_client.py` — Grafo de entidades jurídicas (Neo4j)

Modelo: `(:Empresa {cnpj})-[:PARTE_EM]->(:Processo {id, tribunal, classe, assunto, data_julgamento, valor_log})`

### Entradas →
- `ensure_constraints(driver=None)`
- `upsert_process_edges(records: list[dict], driver=None)` → registros silver do DATAJUD
- `company_processes(cnpj: str, limit=100, driver=None)` 🔒 → CNPJ (dado público)
- `litigant_network(cnpj: str, limit=50, driver=None)`
- `graph_stats(driver=None)`
- `count_processos_por_cnpj(cnpj: str, driver=None)`

### Intermediário (⚙ efêmero)
- ⚙ `_driver` (singleton lazy) = `GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))`
- ⚙ `rows` extraídos de cada record: campos `id_processo, tribunal, classe_tpu, assunto_tpu, ramo, data_julgamento (str), valor_log, cnpj_parte` (filtra `if r.get("id_processo")`)
- ⚙ `graph_stats` fallback zeros; `count_processos_por_cnpj` calcula `repetitivos = max(0, total - len(assuntos))`

### Saídas — nós, arestas e campos de retorno
- **Constraints**: `processo_id` (`Processo.id` UNIQUE), `empresa_cnpj` (`Empresa.cnpj` UNIQUE)
- **`_UPSERT_CYPHER`**: `MERGE (p:Processo {id: r.id_processo})` SET `p.tribunal, p.classe (=r.classe_tpu), p.assunto (=r.assunto_tpu), p.ramo, p.data_julgamento, p.valor_log`; se `r.cnpj_parte IS NOT NULL` → `MERGE (c:Empresa {cnpj: r.cnpj_parte})` `MERGE (c)-[:PARTE_EM]->(p)`. Retorna `len(rows)` (int)
- **`company_processes`** retorna: `id, tribunal, classe_tpu, assunto_tpu, ramo, data_julgamento` (ORDER BY data_julgamento DESC)
- **`litigant_network`** retorna: `cnpj, processos_em_comum (count DISTINCT p), ramos (collect DISTINCT p.ramo[..5])` — só CNPJ↔CNPJ (co-litigância)
- **`graph_stats`** retorna: `{empresas, processos, arestas}`
- **`count_processos_por_cnpj`** retorna: `{total, trabalhistas, repetitivos}`

### Fronteiras (🌐) 🔒
- Neo4j (`bolt://`) via `settings.NEO4J_URL` + auth `NEO4J_USER`/`NEO4J_PASSWORD` 🌐🔒
- **Node labels**: `Empresa`, `Processo`; **Relationship**: `PARTE_EM`

---

## `storage/opensearch_client.py` — Camada silver (OpenSearch, bulk)

### Entradas →
- `ensure_index(index, mapping=None, client=None)`
- `bulk_index(index, docs: list[dict], id_field="id_processo", mapping=None, client=None)`

### Intermediário (⚙ efêmero)
- ⚙ `actions` (par meta+doc para `_bulk`): `meta = {"index": {"_index": index, "_id": str(doc[id_field])?}}`
- ⚙ `_id` = `doc[id_field]` (default `id_processo`) → reindex idempotente; docs sem esse campo recebem id gerado pelo OpenSearch

### Saídas
- `bulk_index` → `len(docs)` (int); erros parciais logados (não levantam) — `resp.get("errors")` conta itens com `.index.error`

### Fronteiras (🌐)
- OpenSearch (`opensearchpy.OpenSearch(hosts=[settings.OPENSEARCH_URL], http_compress=True, timeout=30)`) 🌐
- **Índices** (convenção do docstring): `datajud-silver-YYYY-MM` (mensal), `abj-silver` (fonte ABJ)
- `indices.exists`/`indices.create`, API `_bulk` 🌐

---

## `storage/__init__.py`
- Reexporta helpers: `ensure_bucket, put_json, put_jsonl` (MinIO); `bulk_index, ensure_index` (OpenSearch); `ensure_constraints, upsert_process_edges` (Neo4j) via `__all__`. Sem dados novos.

---

## `tpu.py` — Normalização TPU (CNJ Resolução 46/2007)

### Entradas →
- `normalize_classe(codigo)`, `normalize_assunto(codigo)`, `assunto_ramo(codigo)`, `classe_hierarchy(codigo)` — `codigo: str|int|None`

### Intermediário (⚙ efêmero)
- ⚙ `_clean_code(codigo)` → mantém só dígitos; vazio ⇒ `None`
- ⚙ carrega `ASSUNTOS`/`CLASSES` de `tpu_seed`
- ⚙ `assunto_ramo` sobe a hierarquia via `parent` até achar `ramo` declarado (default `"OUTRO"`); usa `seen` para evitar ciclo

### Saídas
- `normalize_classe`/`normalize_assunto` → `(codigo_canonico, label)` (desconhecido ⇒ `(codigo, None)`)
- `assunto_ramo` → `TRABALHISTA | TRIBUTARIO | CONSUMIDOR | CIVEL | EMPRESARIAL | OUTRO`
- `classe_hierarchy` → `list[str]` (raiz → código)

### Fronteiras (🌐)
- Nenhuma (dado de referência puro, sem PII, sem tenant). Consumido por `pipeline/quality.py` e `services/jurimetria/`.

---

## `tpu_seed.py` — Semente TPU (dados de referência versionados)

### Saídas — dicionários de dados literais (sem PII)
- **`CLASSES`** (10): `1116` Cumprimento de Sentença; `156` Execução de Título Extrajudicial; `7` Procedimento Comum Cível; `985` Ação Trabalhista - Rito Ordinário; `1125` Recuperação Judicial; `132` Falência de Empresários e Sociedades; `319` Mandado de Segurança Cível; `1727` Execução Fiscal; `436` Juizado Especial Cível; `202` Ação Civil Pública (todos `parent: None`)
- **`ASSUNTOS`** (11) com `label/parent/ramo`: `864` DIREITO DO TRABALHO (TRABALHISTA); `1937` Rescisão do Contrato (parent 864); `2546` Verbas Rescisórias (parent 864); `899` DIREITO TRIBUTÁRIO (TRIBUTARIO); `5952` ICMS (parent 899); `6017` PIS/COFINS (parent 899); `1156` DIREITO DO CONSUMIDOR (CONSUMIDOR); `7771` Práticas Abusivas (parent 1156); `10375` Recuperação Judicial e Falência (EMPRESARIAL); `10376` Concurso de Credores (parent 10375); `9985` Direito Societário (EMPRESARIAL)

### Fronteiras (🌐)
- Nenhuma. Módulo Python embutido (não JSON em `data/`, que é gitignored). Tabela completa vive em `jurimetria.tpu_classe`/`tpu_assunto` (migração 004).

---

## Placeholders (sem dados)
- `consensus/__init__.py` — `"""Consensus package placeholder."""`
- `http_client/__init__.py` — `"""HTTP client helpers placeholder."""`
- `vector_store/__init__.py` — `"""Vector store placeholder."""`
- `db/__init__.py` — `"""Database helpers placeholder."""` (pacote namespace vazio; NÃO confundir com `db.py`)
- `__init__.py` (shared) — `# Shared services package`

---

## Apêndice — Dicionário mestre de entidades globais

### Env vars / Secrets (config.py)
- URLs/config: `DATAJUD_API_URL`, `PGFN_API_URL`, `RECEITA_API_URL`, `ABJ_ENABLED`, `ABJ_DATA_URL`, `REDIS_URL`, `OPENSEARCH_URL`, `NEO4J_URL`, `NEO4J_USER`, `CHROMA_URL`, `MINIO_URL`, `OLLAMA_URL`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_MODEL_LOCAL`, `PROTOCOLO_MODO`
- Secrets 🔒 (fonte `/run/secrets/<lower>` → env `<UPPER>`): `datajud_token`, `neo4j_password`, `hmac_key` (também `HMAC_KEY` upper direto em `lgpd.py`), `minio_access_key`, `minio_secret_key`, `llm_api_key`, `consumidor_gov_user`, `consumidor_gov_password`, `procon_sp_user`, `procon_sp_password`
- Secret embutido no DSN 🔒: `DATABASE_URL` (usuário:senha)

### Redis keys
- `llm:<sha256(model:template_ver:prompt)>` (cache LLM, TTL 30 dias)

### MinIO buckets & keys
- Buckets: `bronze-<source_lower>` (ex.: `bronze-datajud`), privados
- Key pattern: `dt=YYYY-MM-DD/part-<uuid.hex>.jsonl` (JSONL / `application/x-ndjson`) ou `.json`

### Chroma collections
- `juridico` (default de `RAGEngine`), config `hnsw:space=cosine`; metadados incluem `content_hash` (sha256 do conteúdo)

### OpenSearch indices
- `datajud-silver-YYYY-MM` (mensal), `abj-silver`; `_id` = `doc[id_field]` (default `id_processo`)

### Neo4j
- Labels: `Empresa` (key `cnpj`), `Processo` (key `id`; props `tribunal, classe, assunto, ramo, data_julgamento, valor_log`)
- Relationship: `PARTE_EM` (`Empresa`→`Processo`)
- Constraints: `processo_id` (Processo.id UNIQUE), `empresa_cnpj` (Empresa.cnpj UNIQUE)

### Ledger — SQL
- **`ledger.entries`** colunas: `request_id, entry_index, product, tenant_id (uuid), inputs_hash, outputs_hash, sources (jsonb), weights_applied (jsonb), subject_token, leaf_hash, merkle_root`
- **`ledger.anchors`** colunas: `anchor_at_index, merkle_root, tenant_id (uuid)` (checkpoint a cada 1024 entradas)
- Entry dict fields: `request_id, entry_index, timestamp, product, inputs_hash, outputs_hash, sources, weights_applied, subject_token, leaf_hash, merkle_root`
- Merkle proof: `{sibling: <64hex>, position: "left"|"right"}`
- Advisory lock: `pg_advisory_xact_lock(hashtext(tenant_id)::bigint)`
- GUC RLS: `set_config('app.tenant_id', <tid>, true)` (SET LOCAL parametrizado)

### alerts_outbox — SQL
- INSERT colunas: `alert_id, dedup_key, envelope (jsonb)` (`ON CONFLICT (alert_id) DO NOTHING`)
- DDL completo: `alert_id TEXT PK, dedup_key TEXT, envelope JSONB, status TEXT ('pending'), attempts INT (0), available_at TIMESTAMPTZ, created_at TIMESTAMPTZ`; índices `ix_outbox_dispatch (status, available_at)`, `ix_outbox_dedup_key (dedup_key)`
- HTTP transport: `POST {elixir}/api/v1/alertas/publicar`, header `X-Contract-Version: alerts/v1`

### Derivações de chave HMAC / AES
- **HMAC-SHA256** (pseudonimização, `lgpd.py`): chave `HMAC_KEY`; domínios `cpf:<digits>`, `name:<strip.lower>`, `uid:<user_id>` → 64 hex (sem truncamento)
- **AES-256-GCM** (crypto-shredding, `lgpd_crypto.py`): chave `os.urandom(32)` por titular, store key `f"{tenant_id}:{pseudonym}"`; token = `base64url(iv[12] || ciphertext || tag[16])`; erasure = destruir a chave
- **SHA-256** (audit_log): `_pseudonym_sha256` para correlação (não é chave; anonimiza o pseudônimo nos logs)
- **SHA-256** (ledger leaf/root, ai/cache, ai/rag content_hash): não são chaves, são hashes de integridade/cache
