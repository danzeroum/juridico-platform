# 02 — Gateway (dados de request/response, auth, dispatch)

Catálogo de fluxo de dados (linha a linha) do serviço `services/gateway`: o entrypoint FastAPI, os três middlewares (segurança, JWT, rate-limit), o helper de observabilidade, a camada de autenticação (JWT RS256 + PBKDF2 + consulta `tenant.users`) e os 20 routers de produto. Para cada endpoint são catalogados: parâmetros de path/query/body/header, campos lidos de `request.state`, leituras de Redis/DB/serviços, o shape da resposta, tratamento de `Idempotency-Key`, despacho Celery, escritas no Decision Ledger e corpos de erro `application/problem+json`.

**Legenda:** `→` fluxo de dado · `⚙` valor efêmero/descartado (nunca sai do processo) · `🔒` segredo/credencial/PII · `🌐` fronteira de serialização (HTTP JSON, JWT, Celery broker, DB, Redis).

Convenção comum a **todos** os routers de produto: o middleware injeta `request.state.{user_id, tenant_id, role}`; o helper local `_get_tenant(request)` lê `request.state.tenant_id` e devolve `401` (problem+json `Token JWT não contém tenant_id.`) se ausente.

---

## Infraestrutura do gateway

#### services/gateway/main.py

App FastAPI `juridico-platform-gateway` v`0.2.0`. Monta middlewares, registra 20 routers, define handlers globais de erro (RFC 9457) e duas rotas app-level.

- **Entradas**
  - `→` Env: `OTEL_EXPORTER_OTLP_ENDPOINT` (setup OTLP), presença dos SDKs OTel/Prometheus (feature flags `_OTEL_AVAILABLE`/`_PROM_AVAILABLE`).
  - `→` `Request` cru para os 3 exception handlers (`request.url.path`).
  - `🌐` `GET /` e `GET /.well-known/jwks.json` (app-level, `include_in_schema=False`).
- **Intermediário**
  - `⚙` `JsonFormatter` — serializa cada `LogRecord` em JSON (`level,name,message,timestamp[,exc_info]`) para stdout.
  - `⚙` `TracerProvider` + `BatchSpanProcessor(OTLPSpanExporter)` construídos no `lifespan`.
  - `⚙` JWKS: carrega PEM pública → `load_pem_public_key` → `public_numbers` (`n`,`e`) → base64url sem padding. Descartado após montar o dict.
  - `⚙` `_status_title(status)` — mapa código→título PT-BR (400/401/402/403/404/409/422/429/500/501/503).
- **Saídas**
  - `🌐` `GET /` → `{name, version:"0.2.0", docs:"/docs"}`.
  - `🌐` `GET /.well-known/jwks.json` → `{keys:[{kty:"RSA",use:"sig",alg:"RS256",n,e}]}`; fallback em erro → `{keys:[{...,pem}]}` (🔒 expõe PEM pública inteira).
  - `🌐` `/metrics` (Prometheus, se instrumentator disponível), `/docs`, `/redoc`, `/openapi.json`.
  - **problem+json** (`_problem_json`): corpo `{type: https://juridico-platform/errors/{suffix|status}, title, status, detail, instance, contract_version:"1.0"}`, header `Content-Type: application/problem+json`. Se `detail` já é dict problem+json completo (`type`+`title`+`status`), passa direto (evita double-wrapping), injetando `instance` se faltar.
    - `HTTPException` → status/detalhe originais.
    - `RequestValidationError` → 422, `type_suffix="validation-error"`, `detail` = join de `loc → msg`.
    - `Exception` genérica → 500 (`logger.exception`, detalhe genérico).
- **Fronteiras**
  - `🌐` Ordem dos middlewares (externo→interno na resposta): `SecurityHeadersMiddleware` → `RateLimitMiddleware` → `JWTAuthMiddleware`. (Nota: `add_middleware` empilha; JWT é adicionado primeiro, portanto roda mais externo na entrada.)
  - Prefixos de router: `/api/v1` (health), `/api/v1/auth`, `/api/v1/legalscore`, `/contabilia`, `/compliance`, `/taxpredict`, `/fiscal`, `/licitawatch`, `/petibot`, `/danobot`, `/concilia`, `/jurimetria`, `/knowledge-graph`, `/forecasting`, `/chamber-profiler`, `/second-opinion`, `/settlement-optimizer`, `/early-warning`, `/defensor`, `/entidade`.

#### services/gateway/middleware.py

Três `BaseHTTPMiddleware`. Config por env: `RATE_LIMIT_PER_MIN`(100), `RATE_LIMIT_FAIL_CLOSED`(false), cooldown de circuito `_REDIS_COOLDOWN=30.0s`, var global `_redis_down_until`.

- **Entradas**
  - `→` `request.url.path` (roteamento público/privado), header `Authorization` (`🔒` Bearer token), `request.client.host` (fallback de chave de rate-limit).
  - `→` Rotas públicas (skip JWT): `/health`, `/api/v1/health`, `/.well-known/jwks.json`, `/api/v1/auth/token`, `/openapi.json`, `/docs`, `/redoc`, e qualquer path com prefixo `/docs`/`/redoc`.
- **Intermediário**
  - **SecurityHeadersMiddleware** → adiciona em toda resposta: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: geolocation=(), microphone=()`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
  - **JWTAuthMiddleware** — `⚙` `token = auth_header[7:]` → `validate_token(token)` → `payload` (claims). Grava em `request.state`: `user_id ← sub`, `tenant_id ← tenant_id`, `role ← role` (default `"viewer"`). Payload descartado após extração.
  - **RateLimitMiddleware** — `⚙` `tenant_id = request.state.tenant_id or client_host`; `⚙` `current_minute = int(time.time()//60)`; chave `ratelimit:{tenant_id}:{current_minute}`. Circuito: se `now < _redis_down_until` pula Redis.
- **Saídas**
  - `🌐`/`🔒` **Redis**: `INCR ratelimit:{tenant}:{minuto}`; se `count==1` → `EXPIRE key 60`. Se `count > RATE_LIMIT_PER_MIN` → **429** problem+json (`title:"Rate limit excedido"`, header extra `Retry-After: 60`).
  - JWT ausente/inválido em rota protegida → **401** problem+json (`Header Authorization com Bearer token obrigatório.` / `Token inválido ou expirado` + `str(exc)`).
  - Redis fora: `_on_limiter_unavailable` → fail-open (segue) ou fail-closed (**503**, `Retry-After: 5`) conforme `RATE_LIMIT_FAIL_CLOSED`; seta `_redis_down_until = now + 30`.
  - `_problem_json` local: `{type: https://juridico-platform/errors/{status}, title, status, detail, instance, contract_version:"1.0"}` + `Content-Type: application/problem+json`.
- **Fronteiras**
  - `🌐` JWT (RS256) — decodificado por `services.gateway.auth.jwt.validate_token`.
  - `🌐` Redis via `services.shared.redis_client.get_redis`.

#### services/gateway/observability.py

Context manager `span(name, attributes)` com degradação graciosa (no-op se OTel ausente).

- **Entradas** `→` `name` (o prefixo antes do 1º `.` vira o tracer), dict `attributes` (chaves podem conter ponto, ex.: `descricao.len`).
- **Intermediário** `⚙` cria span OTel via `get_tracer(name.split(".",1)[0]).start_as_current_span(name)`; aplica `set_attribute` só para valores não-`None`.
- **Saídas** `🌐` spans/atributos exportados via OTLP (fora do processo). `yield None` quando OTel indisponível.
- **Fronteiras** `🌐` OpenTelemetry.

---

## Autenticação — services/gateway/auth/

#### services/gateway/auth/__init__.py

Vazio (pacote namespace, 1 linha em branco). Sem fluxo de dados.

#### services/gateway/auth/jwt.py

JWT RS256. `ALGORITHM="RS256"`, `TOKEN_EXPIRY_SECONDS`(env `JWT_EXPIRY_SECONDS`, 3600), `ISSUER`(env `JWT_ISSUER`, `"juridico-platform"`). Chaves em cache de módulo (`_private_key_pem`/`_public_key_pem`).

- **Entradas**
  - `🔒` `load_secret("JWT_PRIVATE_KEY")` / `load_secret("JWT_PUBLIC_KEY")` (Docker Secret/env).
  - `→` Env `ENV` (default `production`); dev-envs = `{dev, development, test}`.
  - `→` `issue_token(user_id, tenant_id, role, expires_in)`, `validate_token(token)`.
- **Intermediário**
  - `⚙` Fail-closed em produção: sem chaves configuradas fora de dev → `RuntimeError` (nunca gera par efêmero). Em dev → `_generate_ephemeral_keypair()` (RSA 2048, `public_exponent=65537`, PKCS8/NoEncryption).
  - `⚙` `now = int(time.time())` → montagem do payload.
- **Saídas / claims JWT (conjunto canônico)**
  - `🌐`/`🔒` **`issue_token`** → JWT assinado (RS256) com claims: **`sub`** (user_id), **`tenant_id`**, **`role`**, **`iat`** (now), **`exp`** (now+expires_in), **`iss`** (ISSUER).
  - **`validate_token`** → `pyjwt.decode(..., algorithms=["RS256"], options={"require":["sub","tenant_id","role","exp","iss"]}, issuer=ISSUER)`; lança `InvalidTokenError`/`ExpiredSignatureError` etc. em falha. **Nota:** `iat` é emitido mas não está em `require`.
  - `get_public_key_pem()` → PEM público (str) para JWKS.
- **Fronteiras** `🌐` JWT (assinatura RS256), Docker Secret / `services.shared.config.load_secret`.

#### services/gateway/auth/password.py

PBKDF2-HMAC-SHA256 (stdlib). `_ALGO="pbkdf2_sha256"`, `_DEFAULT_ITERATIONS=600_000` (OWASP 2023), `_SALT_BYTES=16`.

- **Entradas** `🔒` `hash_password(plain, *, iterations)`, `verify_password(plain, encoded)`.
- **Intermediário** `⚙` `salt = os.urandom(16)`; `dk = pbkdf2_hmac("sha256", plain.utf8, salt, iterations)`; base64 de salt e dk. Verificação: split de `encoded` por `$`, recomputa e compara com `hmac.compare_digest` (tempo constante).
- **Saídas**
  - **Formato do hash armazenado (estilo Django):** `pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`.
  - `verify_password` → `bool`. **Falha fechado** (`False`) para senha/encoded vazios, algo divergente, ou `ValueError`/`TypeError`.
- **Fronteiras** — sem I/O; hash consumido/produzido por `auth/users.py`.

#### services/gateway/auth/users.py

Autenticação contra `tenant.users`/`tenant.tenants`. `AuthBackendError(RuntimeError)` distingue infra (503) de credencial (401). Tabelas fora de RLS (login ocorre antes do contexto de tenant).

- **Entradas** `🔒` `authenticate(email, password, tenant_slug)`.
- **Intermediário**
  - `⚙` guard: retorna `None` se qualquer arg vazio.
  - `🌐` SQL `_QUERY` (SQLAlchemy `text`) — **colunas lidas:** `tenant.users u`: `u.id::text→user_id`, `u.tenant_id::text→tenant_id`, `u.email`, `u.role`, `u.password_hash`, `u.active`; `tenant.tenants t`: `t.slug→tenant_slug`, `t.name→tenant_name`, `t.id`, `t.active`. `JOIN t.id=u.tenant_id WHERE t.slug=:slug AND lower(u.email)=lower(:email) AND u.active AND t.active LIMIT 1`. Params bind: `{slug, email}`.
  - `⚙`/`🔒` `verify_password(password, row["password_hash"])` — hash nunca sai da função.
- **Saídas**
  - **`AuthenticatedUser`** (frozen dataclass): `user_id`, `tenant_id`, `tenant_slug`, `tenant_name`, `email`, `role` — todos `str`.
  - `None` se linha inexistente **ou** senha inválida (mesma resposta → 401 no router, sem enumeração).
  - `raise AuthBackendError` (engulfa exceção de conexão/engine/query) → router mapeia 503.
- **Fronteiras** `🌐` DB Postgres via `services.shared.tenant_db.get_engine` (`engine.connect()`, sem tenant context).

---

## Routers — infra e auth

#### services/gateway/routers/__init__.py

Vazio (1 linha). Sem fluxo.

#### services/gateway/routers/health.py

Público (`tags=["infra"]`), sem JWT.

| método | path | params | response |
|---|---|---|---|
| GET | `/health` (→ `/api/v1/health`) | — | `{status:"healthy", service:"gateway", version:"0.2.0", timestamp:isoUTC}` 200 |

- **Entradas** nenhuma. **Intermediário** `⚙` `datetime.now(UTC).isoformat()`. **Saídas** `🌐` JSON 200. **Fronteiras** `🌐` HTTP JSON.

#### services/gateway/routers/auth.py

`tags=["auth"]`. Emissão de JWT + claims do usuário.

| método | path | params | response |
|---|---|---|---|
| POST | `/token` | body `LoginRequest{username:str, password:str, tenant_slug:str}` | `TokenResponse{access_token:str, token_type="bearer", expires_in:int}` 200 · 401 · 503 |
| GET | `/me` | (lê `request.state`) | `{user_id, tenant_id, role}` 200 · 401 |

- **Entradas**
  - `🔒` `LoginRequest`: `username` (carrega o e-mail), `password`, `tenant_slug`. `/token` é rota **pública** (skip JWT no middleware).
  - `→` Env `ENV`; dev-envs `{dev, development, test}`.
  - `→` `/me`: `request.state.user_id/tenant_id/role`.
- **Intermediário**
  - `⚙` `authenticate(username, password, tenant_slug)` → `AuthenticatedUser | None`.
  - `⚙` `AuthBackendError`: em prod → 503; em dev/test → `_dev_fallback_user` (tenant `00000000-0000-0000-0000-000000000001`, role `admin`, **sem validar senha** — nunca em prod).
- **Saídas**
  - `🌐`/`🔒` `/token` → `issue_token(user_id, tenant_id, role)` → `TokenResponse{access_token, token_type:"bearer", expires_in:TOKEN_EXPIRY_SECONDS}`.
  - **problem+json**: 401 `Credenciais inválidas.` (user `None`); 503 `Backend de autenticação indisponível.` / `Serviço de autenticação indisponível.`
  - `/me` → `{user_id, tenant_id, role(default "viewer")}`; 401 `Não autenticado.` se sem `user_id`.
- **Fronteiras** `🌐` HTTP JSON, JWT (emissão), DB (via `authenticate`).

---

## Router de referência — LegalScore

#### services/gateway/routers/legalscore.py

Template P2 completo (Idempotency-Key, OTel span, Decision Ledger, audit_log). `_ledger = DecisionLedger()` (singleton in-memory dev); `_get_ledger(tenant_id)` → `PostgresDecisionLedger(tenant_id)` se `DATABASE_URL`. `_SCORE_DISCLAIMER` = "heurística…".

| método | path | params | response |
|---|---|---|---|
| POST | `/score` | body `ScoreRequest{cnpj:str /^\d{14}$/}`; header `Idempotency-Key?`; state `tenant_id` | `ScoreResponse` 200 · 400 · 429 · 501 |
| GET | `/company/{cnpj}` | path `cnpj`; state `tenant_id` | perfil cadastral 200 · 404 |
| GET | `/company/{cnpj}/processes` | path `cnpj`; query `page=1,per_page=20` | 501 (não implementado) |
| GET | `/company/{cnpj}/risk-breakdown` | path `cnpj` | 501 |
| POST | `/batch` | body `BatchScoreRequest{cnpjs:list[str] len 1..1000}`; state `tenant_id` | `{job_id,total,status:"queued"[,warning]}` 202 · 400 · 503 |
| GET | `/batch/{job_id}` | path `job_id` | status do job 200 · 404 · 503 |
| GET | `/model-metrics` | state `tenant_id` | métricas do modelo 200 |
| GET | `/audit/{request_id}` | path `request_id`; state `tenant_id` | prova Merkle 200 · 404 |

- **Entradas**
  - `🔒` `ScoreRequest.cnpj` (`pattern=^\d{14}$`), header **`Idempotency-Key`** (via `Header(alias=...)`), `request.state.tenant_id`.
  - `BatchScoreRequest.cnpjs` (`min_length=1, max_length=1000`).
  - path: `cnpj`, `job_id`, `request_id`; query `page`, `per_page`.
- **Intermediário**
  - `⚙` `request_id = str(uuid4())`.
  - `⚙` OTel span `legalscore.score` com atributos `tenant.id`, **`cnpj.partial = cnpj[:6]+"****"`** (🔒 CNPJ mascarado), `idempotency.key_present`.
  - `🌐`/`🔒` **Idempotência (Redis, 24h TTL):** `get_idempotency_result(redis, tenant_id, idempotency_key)` → se cache-hit devolve `ScoreResponse(**cached)`.
  - `⚙` **Feature vector** (`assemble_features(cnpj, redis)` → `fv`): `fv.features`, `fv.cnae_2dig`, `fv.source_date`, `fv.sources_used`, `fv.sources_missing`, `fv.is_partial`. Construído e passado ao engine; não persistido cru.
  - `⚙` engine SEAMS `get_score_engine().score(EngineScoreRequest{cnpj, features, cnae_2dig})` → `eng_result{score, risk_level, confidence_interval, breakdown, engine}`.
  - `⚙` `pseudonym = hash_user_id(cnpj)` → `subject_token = encrypt_for_ledger(pseudonym, tenant_id)` (🔒 AES-256-GCM por titular; crypto-shredding).
  - `company_profile`: lê `receita:{cnpj}` do Redis → `receita_bronze_to_silver(data)`.
  - fallback `_stub_score`: score determinístico via `sum(int(d) for d in cnpj)`.
- **Saídas**
  - **`ScoreResponse`**: `cnpj:str`, `score:int(0..1000)`, `risk_level:str(BAIXO|MODERADO|ALTO|CRITICO)`, `confidence_interval:list[float] [lower,upper]`, `breakdown:dict[str,float]`, `disclaimer:str`, `request_id:str`, `source_date:str|None`, `lag_days:int|None`, `engine:str="python"`, `contract_version:str="scoring/v1"`. Disclaimer ganha sufixo `[PARTIAL: <sources_missing>]` se `fv.is_partial`.
  - `🌐`/`🔒` **Decision Ledger** `add_entry`: `request_id`, `product="legalscore"`, `inputs={cnpj_partial: cnpj[:6]+"****", features}`, `outputs={score, risk_level}`, `sources=fv.sources_used`, `subject_token` (cifrado). Retorna `entry_index`.
  - `🌐` **audit_log** `log_ledger_write(request_id, product="legalscore", tenant_id, entry_index, has_subject_token=True)`.
  - `🌐`/`🔒` **Redis write** `set_idempotency_result(redis, tenant_id, idempotency_key, result.model_dump())` (só se key + redis presentes).
  - `/batch`: `🌐`/`🔒` `create_batch_job(redis, cnpjs, tenant_id)` → `job_id`; **Celery** `send_task("scoring.tasks.run_batch_score", args=[job_id, cnpjs], queue="scoring")`. Falha Celery → resposta 202 com `warning`. Falha Redis → 503.
  - `/batch/{job_id}` → `get_batch_status(redis, job_id)`; 404 se `None`. `/audit/{request_id}` → `get_proof(request_id)`; 404 (KeyError). `/model-metrics` → `get_current_metrics()` (`model_type, auc, brier_score, calibration_r2, n_validation_samples, validation_status, validation_note, last_calibrated, target_auc, target_brier`).
  - problem+json: 400 CNPJ inválido, 404 (perfil/job/audit), 501 (endpoints não implementados), 503 Redis.
- **Fronteiras** `🌐` HTTP JSON · Redis (`get_redis`) · Celery broker (queue `scoring`) · Decision Ledger (Postgres/in-memory) · engine SEAMS · OTel.

---

## Routers de produto

#### services/gateway/routers/chamber_profiler.py

Perfil AGREGADO de órgão julgador (LGPD: nunca por juiz). `tags=["chamber-profiler"]`.

| método | path | params | response |
|---|---|---|---|
| GET | `/tribunal/{tribunal}` | path `tribunal`; query `classe:str?`; state `tenant_id` | `queries.profile_tribunal(tribunal, classe)` (faixas de provimento/congestionamento/duração) |

- **Entradas** `→` path `tribunal`, query `classe`, `request.state.tenant_id`. **Intermediário** `⚙` `_get_tenant`. **Saídas** `🌐` dict de perfil agregado. **Fronteiras** `🌐` `services.chamber_profiler.queries` (DB).

#### services/gateway/routers/compliance.py

Monitoramento municipal via cache Redis. `_REDIS_URL` (env `REDIS_URL`). **Sem JWT `_get_tenant`** (não lê `request.state`). `contract_version="compliance/v1"`.

| método | path | params | response |
|---|---|---|---|
| GET | `/municipalities` | query `uf:str?`, `page≥1`, `per_page 1..100` | `{total,page,per_page,municipalities[],contract_version}` · 503 |
| GET | `/municipality/{ibge_code}` | path `ibge_code` (7 díg.) | summary+`rules_available`+`lgpd_note` · 400 · 503 |
| GET | `/alerts` | query `severity:str?`, `page`, `per_page` | `{total,page,per_page,alerts[],contract_version}` · 503 |
| POST | `/municipality/{ibge_code}/evaluate` | path `ibge_code` | `{cod_ibge,evaluated_at,rules_fired,envelopes[],contract_version}` · 400 · 503 |
| GET | `/uf/{uf}/municipios` | path `uf` (2 letras) | `{uf,total,municipios[],source:"IBGE"}` · 400 |
| GET | `/municipio/{cod_ibge}/populacao` | path `cod_ibge` | `{cod_ibge,populacao,ano,source:"IBGE"}` · 400 |
| GET | `/municipio/{cod_ibge}/perfil` | path `cod_ibge` | perfil socioeconômico completo · 400 |

- **Entradas** `→` path `ibge_code`/`cod_ibge`/`uf`; query `uf`, `severity`, `page`, `per_page`. Validação inline: `isdigit() and len==7` (IBGE), `isalpha() and len==2` (UF).
- **Intermediário**
  - `⚙` `_build_summary`: lê Redis `siconfi:{cod}:{ano}`, `siconfi:{cod}:{ano-1}`, `caged:{cod}:{ref}`, `caged:{cod}:{last_ref}`, `snis:{cod}`, `ibge:{cod}` → `build_indicadores_from_cache(...)` → `ind` → `evaluate_municipio(ind)` → `alerts`.
  - `⚙` `list_municipalities`: `r.keys("snis:*")` ∪ `r.keys("ibge:*")` → universo de códigos; paginação em memória.
  - `⚙` `list_alerts`: `r.keys("compliance_alert:*")`.
  - `⚙` OTel via `obs_span("compliance.municipality_detail", {ibge_code})`.
- **Saídas**
  - `🌐` summary: `{cod_ibge, municipio, uf, populacao, referencia, indicadores{delta_arrecadacao_yoy, delta_emprego_yoy, cobertura_agua_pct, cobertura_esgoto_pct, source_lag_days, source_date}, sources_missing[], active_alerts, alert_rules_triggered[]}`.
  - `evaluate` → `envelopes = [json.loads(e.model_dump_json())]` (AlertEnvelope, preview sem publicar).
  - **problem+json** custom (domínio `juridico.io`): `ibge-invalido`(400), `cache-indisponivel`(503), `uf-invalida`(400), `avaliacao-falhou`(503) — todos com `contract_version:"compliance/v1"`.
  - `/uf/.../municipios`, `/populacao`, `/perfil`: chamam `services.ingest.tasks.ibge.fetch_*` (fetch ao vivo do IBGE).
- **Fronteiras** `🌐` Redis (`redis.from_url`, `decode_responses=True`), IBGE (HTTP externo via ingest tasks), OTel.

#### services/gateway/routers/concilia.py

Recomendação de faixa de acordo. Enriquecimento opcional cross-produto (degradação graciosa).

| método | path | params | response |
|---|---|---|---|
| POST | `/recommend` | body `ConciliaRequest` | `recommend_settlement(...).model_dump()` 200 · 422 |

- **Entradas** `→` `ConciliaRequest{tipo_acao(enum), valor_causa, descricao, cnpj_reu?, ...}`.
- **Intermediário**
  - `⚙` `_get_taxpredict(descricao, materia)` → reusa `taxpredict._get_model`; monta `TaxPredictRequest(descricao[:2000], Materia(materia))` → `extract_features` → `model.predict` → `probability` (float|None).
  - `⚙` `_get_legalscore(cnpj)` → Redis `score:{cnpj}` → `data.get("score")` (int|None).
  - `⚙` OTel `obs_span("concilia.recommend", {tipo_acao, valor_causa})`.
- **Saídas** `🌐` `ConciliaResponse` (dump): `{tipo_acao, valor_causa, faixa_min, faixa_max, percentual_min, percentual_max, fatores:[{nome,impacto}], contract_version:"concilia/v1"}`. 422 validation-error global.
- **Fronteiras** `🌐` HTTP JSON, Redis (`score:{cnpj}`), TaxPredict model (MinIO), OTel.

#### services/gateway/routers/contabilia.py

Upload de DRE (CSV) → relatório de auditoria contábil síncrono. `_engine = CrossCheckEngine()`. `MAX_FILE_SIZE=5MB`. **Sem JWT `_get_tenant`.**

| método | path | params | response |
|---|---|---|---|
| POST | `/audit/upload` | `file:UploadFile` (multipart), query `cnpj:str?` | relatório JSON 200 · 400 · 413 · 422 |
| GET | `/audit/{report_id}` | path `report_id` | sempre 404 (reservado Fase 3) |

- **Entradas** `🌐`/`🔒` `file` (multipart; `content_type` ∈ `{text/csv, text/plain, application/csv, application/vnd.ms-excel}`), `cnpj?`.
- **Intermediário**
  - `⚙` `content = await file.read()`; guard tamanho > 5MB → 413.
  - `⚙` `_parse_dre_csv(content)`: decode utf-8 → `csv.DictReader`; colunas `conta,valor[,descricao]`; campos reconhecidos `FINANCIAL_FIELDS = {receita_liquida, headcount, ativo_circulante, passivo_circulante, ebitda, importacoes, variacao_estoque, receita_servicos_publicos}`; séries `receita_mensal*`→`serie_receitas_mensais`, `despesa_mensal*`→`serie_despesas_mensais`. Linhas não-numéricas ignoradas.
  - `⚙` `_engine.run_checks(financials, public_data={})` → `findings:list[CrossCheckFinding]`.
  - `⚙` `report_id = str(uuid4())`, `generated_at = now(UTC).iso`. OTel span `contabilia.upload` (atrib. `fields.count`, `cnpj.present`).
- **Saídas** `🌐` `report{report_id, generated_at, cnpj, filename, status:"CONCLUIDO", summary{CRITICO,ALTO,MEDIO}, total_findings, findings:[{rule,severity,description,detail}], fields_analyzed[], data_lag_note, contract_version:"contabilia/v1"}`. problem+json custom: `formato-nao-suportado`(400), `arquivo-muito-grande`(413), `dre-invalida`(422), `relatorio-nao-encontrado`(404).
- **Fronteiras** `🌐` HTTP multipart in / JSON out; `CrossCheckEngine` (em memória, sem I/O); OTel.

#### services/gateway/routers/danobot.py

Bloqueado por LGPD (DATASUS art. 11) até parecer DPO (PD-06).

| método | path | params | response |
|---|---|---|---|
| POST | `/predict` | — | sempre **501** problem+json `danobot/blocked-pd06` |

- **Saídas** `🌐` problem+json `{type: https://juridico.io/errors/danobot/blocked-pd06, title:"DanoBot bloqueado", status:501, detail, instance, contract_version:"danobot/v1"}`. Sem entradas/intermediário reais.

#### services/gateway/routers/defensor.py

Agente jurídico (pipeline agêntico + timeline). `DEFENSOR_CONTRACT_VERSION`.

| método | path | params | response |
|---|---|---|---|
| POST | `/run` | body `DefensorRequest{canal(enum), tipo_caso(enum), ...}` | `run_agente(case).model_dump()` 200 · 422 |
| GET | `/reputacao/{termo:path}` | path `termo` (aceita barras) | `{termo, encontrado, reputacao, source:"Consumidor.gov", contract_version}` |
| POST | `/protocolar` | body `ProtocoloRequest{canal(enum), ...}` | `protocolar(req).model_dump()` 200 · 422 |

- **Entradas** `→` `DefensorRequest`, `ProtocoloRequest`; path `termo`.
- **Intermediário**
  - `⚙` OTel spans `defensor.run` (`canal`, `tipo_caso`), `defensor.protocolar` (`canal`).
  - `⚙` `reputacao`: `slug = slugify(termo)` → Redis `consumidor:{slug}` → `json.loads`.
- **Saídas**
  - `🌐` `/run` → `DefensorResponse`: `{classificacao, canal, eventos:[{ts,evento,detalhe,status}], precedentes_encontrados, casos_anteriores, subsidios[], proximo_responsavel, status, contract_version:"defensor/v1"}`.
  - `/protocolar` → `{canal, modo, status(SIMULADO por padrão), numero_protocolo, url, mensagem, contract_version:"protocolo/v1"}`. Submissão real exige `PROTOCOLO_MODO=real` + allowlist.
  - `/reputacao` → reputação Consumidor.gov (`encontrado=false` se sem dado).
- **Fronteiras** `🌐` HTTP JSON, Redis (`consumidor:{slug}`), RAG jurisprudência (via orchestrator), OTel.

#### services/gateway/routers/early_warning.py

Detecção de surtos de litigiosidade. Só dados agregados. `tags=["early-warning"]`.

| método | path | params | response |
|---|---|---|---|
| GET | `/evaluate` | query `tribunal:str!`, `classe?`, `assunto?`; state `tenant_id` | `queries.evaluate(tribunal, classe, assunto)` |

- **Entradas** `→` query `tribunal`(obrigatório), `classe`, `assunto`; `state.tenant_id`. **Saídas** `🌐` gatilhos de surto/congestionamento (heurística). **Fronteiras** `🌐` `services.early_warning.queries` (série jurimetria.indicador).

#### services/gateway/routers/entidade.py

Cadastro público de CNPJ (Receita). `ENTIDADE_CONTRACT_VERSION="entidade/v1"`.

| método | path | params | response |
|---|---|---|---|
| GET | `/{cnpj}` | path `cnpj` (14 díg. após limpeza) | `{cnpj, encontrado, cadastro, source:"Receita/CNPJ", contract_version}` · 422 |

- **Intermediário** `⚙` `digits = filtro isdigit(cnpj)`; guard `len!=14` → 422 (`cnpj-invalido`). `fetch_cnpj(digits)` ao vivo. **Saídas** `🌐` cadastro (`razao_social, situacao_cadastral, porte, cnae_fiscal, municipio, uf`) ou `encontrado=false`. **Fronteiras** `🌐` Receita/CNPJ (HTTP externo via `services.ingest.tasks.receita_cnpj`).

#### services/gateway/routers/fiscal.py

NCM + ICMS. Template P2 (Idempotency-Key, OTel, Decision Ledger, upload assíncrono via MinIO+Celery). `_MAX_UPLOAD_ROWS=50_000`. `tags=["fiscal"]`.

| método | path | params | response |
|---|---|---|---|
| POST | `/ncm/triage` | body `NcmTriageRequest`; header `Idempotency-Key?`; state `tenant_id` | `NcmTriageResult` (+`decision_proof`,`sku_descricao`) |
| GET | `/ncm/{codigo}` | path `codigo` (8 díg.); query `data:date?`; state `tenant_id` | `{ncm_codigo, descricao}` · 400 · 404 |
| GET | `/icms/{ncm}/{uf}` | path `ncm`,`uf`; query `uf_origem="SP"`,`importado=False`,`data?` | `icms.model_dump()` · 400 |
| POST | `/spreadsheet/enrich` | `file:UploadFile(.xlsx)`; query `uf_origem="SP"`; state `tenant_id` | `SpreadsheetJobResponse{job_id,status_url,submitted_at}` 202 · 400 · 413 · 503 |
| GET | `/jobs/{job_id}` | path `job_id`; state `tenant_id` | status do job · 404 · 503 |
| GET | `/audit/{request_id}` | path `request_id`; state `tenant_id` | `{request_id, proof}` · 404 |

- **Entradas** `🔒`/`→` `NcmTriageRequest{descricao, uf_origem, uf_destino, ...}`, header **`Idempotency-Key`**, path `codigo`/`ncm`/`uf`/`job_id`/`request_id`, query `data`(date)/`uf_origem`/`importado`(bool), `file`(.xlsx). Validações inline: NCM `isdigit and len==8`; UF ∈ `UF.__members__`.
- **Intermediário**
  - `⚙` `request_id = f"fiscal_{uuid4().hex[:16]}"`, `job_id = f"fiscal_{uuid4().hex[:16]}"`.
  - `⚙` OTel span `fiscal.triage` (`tenant.id`).
  - `⚙` `classify_one(body)` → `result{suggested_ncm, icms{interna_efetiva_pct, difal_pct}}`.
  - `⚙` enrich: `load_items_from_bytes(content)` → `(colmap, rows)`; guard `len(rows) > 50_000` → 413.
- **Saídas**
  - `🌐`/`🔒` **Decision Ledger** (triage): `add_entry(request_id, product="fiscal", inputs={descricao, uf_o, uf_d}, outputs={ncm, interna_efetiva, difal}, sources=[fonte_regra])`. **Sem `subject_token`** (dado fiscal, não PII pessoal). `result.model_copy(update={decision_proof: request_id, sku_descricao: descricao})`.
  - `🌐`/`🔒` **MinIO write**: `upload_spreadsheet(f"fiscal/uploads/{tenant_id}/{job_id}.xlsx", content)` (falha → 503). Só a **KEY** vai ao worker (não as linhas inline).
  - `🌐`/`🔒` **Redis** `create_batch_job(redis, [None]*total, tenant_id)` (rastreio de job; best-effort).
  - `🌐` **Celery** `send_task("fiscal.tasks.enrich_spreadsheet", args=[job_id, tenant_id, spreadsheet_key, uf_origem], queue="fiscal")` (falha → 503).
  - `/jobs/{job_id}` → `get_batch_status`; 404/503. `/audit/{request_id}` → `get_proof`; 404. `/ncm/{codigo}` → DB `DbNcmSource(conn).get_ncm(codigo, data)`. `/icms/...` → DB `DbIcmsSource(conn).interna(uf, ncm, data)` → `resolve_icms(...)`.
- **Fronteiras** `🌐` HTTP JSON/multipart · DB (`get_engine().connect()`) · Redis · MinIO (`services.fiscal.storage`) · Celery broker (queue `fiscal`) · Decision Ledger · OTel.

#### services/gateway/routers/forecasting.py

Projeção de volume de ações (heurística linear). `tags=["forecasting"]`.

| método | path | params | response |
|---|---|---|---|
| GET | `/demand` | query `tribunal:str!`, `classe?`, `assunto?`, `horizonte:int 1..12 (=3)`; state `tenant_id` | `queries.forecast_demand(...)` |

- **Entradas** `→` query + `state.tenant_id`. **Saídas** `🌐` projeção (ou `status=insuficiente` se <3 períodos). **Fronteiras** `🌐` `services.forecasting.queries` (jurimetria.indicador).

#### services/gateway/routers/jurimetria.py

Feature store `jurimetria.indicador` + Market Intelligence (Decision Ledger). Zero PII. `tags=["jurimetria"]`.

| método | path | params | response |
|---|---|---|---|
| GET | `/indicators` | query `tribunal?,classe?,assunto?,periodo?,fonte?(DATAJUD\|ABJ\|BLEND),limit 1..500(=100),offset≥0(=0)`; state `tenant_id` | `{count,results[],limit,offset}` |
| GET | `/tribunal/{tribunal}/congestion` | path `tribunal`; state `tenant_id` | `{tribunal,count,results[]}` |
| GET | `/classe/{classe}/duration` | path `classe`; state `tenant_id` | `{classe_tpu,count,results[]}` |
| GET | `/litigiosity` | query `assunto?`; state `tenant_id` | `{assunto_tpu,count,results[]}` |
| POST | `/market-intelligence` | body `MarketIntelligenceRequest{tribunal?,ramo?}`; state `tenant_id` | `{request_id, ...report}` |

- **Intermediário**
  - `⚙` `request_id = str(uuid4())`; OTel spans `jurimetria.indicators`, `jurimetria.market_intelligence`.
  - `⚙` `queries.get_indicators/get_congestion/get_duration/get_litigiosity/market_intelligence(...)`.
- **Saídas**
  - `🌐` MI report inclui `total_processos`, `n_segmentos` (+demais).
  - `🌐` **Decision Ledger** (`_ledger_entry`, try/except silencioso): `add_entry(request_id, product="jurimetria-market-intelligence", inputs={tribunal, ramo}, outputs={total_processos, n_segmentos}, sources=["jurimetria.indicador"], subject_token=None)` → **audit_log** `log_ledger_write(..., has_subject_token=False)`.
- **Fronteiras** `🌐` HTTP JSON, DB (`services.jurimetria.queries`), Decision Ledger, OTel.

#### services/gateway/routers/knowledge_graph.py

Consultas read-only ao grafo Neo4j Empresa→Processo (só CNPJ↔CNPJ público). `tags=["knowledge-graph"]`.

| método | path | params | response |
|---|---|---|---|
| GET | `/stats` | state `tenant_id` | `queries.graph_stats()` |
| GET | `/company/{cnpj}/processes` | path `cnpj`; query `limit 1..500(=100)`; state `tenant_id` | `{cnpj,count,results[]}` |
| GET | `/company/{cnpj}/network` | path `cnpj`; query `limit 1..200(=50)`; state `tenant_id` | `queries.litigant_network(cnpj,limit)` (ISOLADO→PREDATORIO) |

- **Intermediário** `⚙` OTel spans `kg.company_processes`, `kg.litigant_network`. **Saídas** `🌐` nós/arestas do grafo (co-litigância). **Fronteiras** `🌐` Neo4j via `services.knowledge_graph.queries`, OTel.

#### services/gateway/routers/licitawatch.py

Monitoramento PNCP via cache Redis. `_REDIS_URL`. **Sem JWT `_get_tenant`.** `contract_version="licitawatch/v1"`.

| método | path | params | response |
|---|---|---|---|
| GET | `/contratos/{cnpj_orgao}` | path `cnpj_orgao` (14 díg.); query `referencia:str! (YYYY)` | `{cnpj_orgao,referencia,contratos[],total}` · 422 |
| POST | `/orgao/{cnpj_orgao}/evaluate` | path `cnpj_orgao`; query `referencia!` | indicadores + envelopes LL01–LL04 · 422 |

- **Intermediário**
  - `⚙` guard `isdigit and len==14` → 422 (`licitawatch/cnpj-invalido`).
  - `🌐` Redis `scan_iter("pncp:{cnpj_orgao}:{referencia}:*", count=100)` → `r.get(k)` (slice `[:200]` list / `[:500]` evaluate) → `json.loads` / `PncpContratoSilver(**...)`.
  - `⚙` `build_indicadores_from_silver(...)` → `ind`; `evaluate_licitacoes(ind)` → `envelopes`.
  - `⚙` OTel spans `licitawatch.list_contratos`/`licitawatch.evaluate_orgao` (atrib. **`cnpj_orgao[:6]+"****"`** mascarado, `referencia`).
- **Saídas** `🌐` evaluate → `{cnpj_orgao, referencia, total_contratos, indicadores{pct_mesmo_vencedor, pct_dispensa, pct_unico_proponente, pct_prazo_curto}, alertas, envelopes:[e.model_dump(mode="json")], contract_version}`. Redis fora → degradação (`contratos:[], total:0`).
- **Fronteiras** `🌐` Redis (`pncp:*`), OTel. (PNCP populado offline pelo ingest.)

#### services/gateway/routers/petibot.py

Montagem de petição (template + RAG ChromaDB).

| método | path | params | response |
|---|---|---|---|
| POST | `/assemble` | body `PetiRequest{tipo_acao(enum), ...}` | `assemble_petition(case).model_dump()` 200 · 422 |

- **Intermediário** `⚙` OTel `obs_span("petibot.assemble", {tipo_acao})`. **Saídas** `🌐` `{tipo_acao, secoes:[{titulo,conteudo,ordem}], precedentes_encontrados, contract_version:"petibot/v1"}`. **Fronteiras** `🌐` HTTP JSON, ChromaDB (RAG precedentes, graceful), OTel.

#### services/gateway/routers/second_opinion.py

Parecer de consenso entre produtos → Decision Ledger. `tags=["second-opinion"]`.

| método | path | params | response |
|---|---|---|---|
| POST | `/opinion` | body `SecondOpinionRequest{legalscore?0..1000, taxpredict_prob?0..1, pct_provimento?0..1}`; state `tenant_id` | `{request_id, ...result}` |

- **Intermediário** `⚙` `request_id=str(uuid4())`; `synthesize_opinion(legalscore, taxpredict_prob, pct_provimento)` → `result{veredito, favorabilidade, ...}`.
- **Saídas** `🌐` `{request_id, ...result}` (ou `status=sem_sinais`). `🌐` **Decision Ledger** `add_entry(product="second-opinion", inputs=body.model_dump(), outputs={veredito, favorabilidade}, sources=["legalscore","taxpredict","jurimetria"], subject_token=None)` + **audit_log** `has_subject_token=False` (try/except silencioso).
- **Fronteiras** `🌐` HTTP JSON, Decision Ledger.

#### services/gateway/routers/settlement_optimizer.py

Faixa ótima de acordo (ZOPA) → Decision Ledger. `tags=["settlement-optimizer"]`.

| método | path | params | response |
|---|---|---|---|
| POST | `/optimize` | body `SettlementRequest{valor_causa≥0, prob_favorable?0..1, pct_provimento?0..1, custo_autor=0.0, custo_reu=0.0}`; state `tenant_id` | `{request_id, ...result}` |

- **Intermediário** `⚙` `request_id=str(uuid4())`; `optimize_settlement(valor_causa, prob_favorable, pct_provimento, custo_autor, custo_reu)` → `result{recomendacao, acordo_sugerido, ...}`.
- **Saídas** `🌐` `{request_id, ...result}`. `🌐` **Decision Ledger** `add_entry(product="settlement-optimizer", inputs=body.model_dump(), outputs={recomendacao, acordo_sugerido}, sources=["taxpredict","jurimetria"], subject_token=None)` + audit_log `has_subject_token=False`.
- **Fronteiras** `🌐` HTTP JSON, Decision Ledger.

#### services/gateway/routers/taxpredict.py

Predição probabilística tributária (Bayesiano hierárquico + RAG). `_MODEL_CACHE` (lazy por matéria), `_RAG_N_RESULTS=5`. SLA p95<3s (MCMC nunca neste path).

| método | path | params | response |
|---|---|---|---|
| POST | `/predict` | body `TaxPredictRequest{materia(enum), descricao, ...}` | `TaxPredictResponse` 200 · 422 · 503 |
| GET | `/macro` | — | `{ipca, bcb, source:"IBGE+BCB", contract_version}` |

- **Entradas** `→` `TaxPredictRequest{materia, descricao}`. `request.url` usado só em corpo de erro 503.
- **Intermediário**
  - `⚙` `features = extract_features(case)`; OTel `obs_span("taxpredict.predict", {materia, descricao.len})`.
  - `⚙`/`🔒` `_get_model(materia)`: MinIO (`settings.MINIO_URL/ACCESS_KEY/SECRET_KEY`) → `TaxPredictionModel(materia).load_from_minio(minio, "gold", f"taxpredict/{materia_lower}.nc")` → cache. Fallback prior nacional se indisponível.
  - `⚙` `_rag_lookup(descricao, materia)`: `RAGEngine(collection="taxpredict_jurisprudencia").search(query=descricao, n_results=5)` → hits `{doc_id, similarity=1-distance, ementa[:500], decisao(enum), tribunal, ano}`.
- **Saídas**
  - `🌐` **`TaxPredictResponse`**: `{materia, probability(round4), ci_lower, ci_upper, rag_hits, jurisprudencias:[JurisprudenciaHit], features_used:dict, computed_at:isoUTC, model_version, is_fallback:bool, contract_version:"taxpredict/v1"}`. Fallback → `probability=PRIOR_NACIONAL`, `model_version="prior_nacional_v1"`, `is_fallback=True`.
  - problem+json 503 `taxpredict/model-unavailable` (predição real falhou).
  - `/macro` → `fetch_ipca()` (IBGE) + `fetch_macro()` (BCB, `{}` enquanto bloqueado).
- **Fronteiras** `🌐` HTTP JSON, MinIO (bucket `gold`, trace `.nc`), ChromaDB/Ollama (RAG), IBGE+BCB (HTTP), OTel. **Sem `_get_tenant`/Decision Ledger.**

---

## Notas transversais

- **`_get_tenant` (lê `request.state.tenant_id` → 401 se ausente)** está presente em: legalscore, fiscal, chamber_profiler, early_warning, forecasting, jurimetria, knowledge_graph, second_opinion, settlement_optimizer, e `auth./me`. **Ausente** (não lê `request.state`) em: compliance, contabilia, concilia, danobot, defensor, entidade, licitawatch, petibot, taxpredict, health — embora o middleware JWT ainda proteja essas rotas (não estão em `_PUBLIC_PATHS`).
- **Idempotency-Key** (header `Header(alias="Idempotency-Key")`, 24h TTL Redis): apenas **legalscore `/score`** e **fiscal `/ncm/triage`**.
- **Decision Ledger + audit_log**: legalscore (`subject_token` cifrado), fiscal (sem subject_token), jurimetria-MI, second-opinion, settlement-optimizer (todos `subject_token=None`).
