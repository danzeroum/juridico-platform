# 09 — Frontend (DTOs TS, client, BFF, estado React, componentes)

Catálogo exaustivo, arquivo por arquivo, de TODOS os dados que cruzam o frontend
TypeScript/HTML em `frontend/`. Documentação apenas — nenhum código foi alterado.

**Legenda**
- ⚙ = **Intermediário**: view-model derivado, dados memoizados de query, string formatada.
- 🔒 = dado sensível (JWT, CNPJ, credenciais, PII).
- 🌐 = **Fronteira**: HTTP ao gateway, cookie/JWT, DTO que espelha um contrato Python.
- **Entradas** = props, respostas de fetch, env, cookies, campos de formulário.
- **Saídas** = requisições HTTP ao gateway, cookies gravados, DTOs renderizados, downloads `.doc`/`.json`.

---

## Tabela mestre: rota → api fn → endpoint gateway → DTO de resposta

| Rota (page) | api fn | Método + endpoint gateway | DTO de resposta (TS) | Espelha contrato Python |
|---|---|---|---|---|
| `/login` (form nativo) | `POST /api/auth/login` (BFF) | `POST /api/v1/auth/token` | `{ access_token }` / `{ ok: true }` | TokenResponse |
| (todas, hidratação) | `authApi.me()` → `GET /api/auth/me` (BFF) | `GET /api/v1/auth/me` | `MeResponse` | UserClaims / MeResponse |
| `/legalscore` | `legalscoreApi.score(cnpj)` | `POST /api/v1/legalscore/score` | `LegalScoreResult` | **ScoreResponse** |
| `/legalscore` (métricas) | `legalscoreApi.modelMetrics()` | `GET /api/v1/legalscore/model-metrics` | `ModelMetrics` | ModelMetricsResponse |
| `/legalscore` (auditoria) | `legalscoreApi.audit(reqId)` | `GET /api/v1/legalscore/audit/{id}` | `{ request_id, leaf_hash, merkle_root, proof[] }` | AuditProofResponse |
| `/legalscore` (lote) | `legalscoreApi.batchScore(cnpjs)` | `POST /api/v1/legalscore/batch` | `{ job_id, total, status }` | BatchAccepted (202) |
| `/legalscore` (lote) | `legalscoreApi.batchStatus(jobId)` | `GET /api/v1/legalscore/batch/{jobId}` | `BatchJob` | BatchJobStatus |
| `/contabilia` | `contabiliaApi.upload(file,cnpj?)` | `POST /api/v1/contabilia/audit/upload` (multipart) | `AuditReport` | AuditReportResponse |
| `/compliance-radar` | `complianceApi.evaluate(ibge)` | `POST /api/v1/compliance/municipality/{ibge}/evaluate` | `ComplianceEvaluation` | EvaluationResponse |
| `/compliance-radar` | `complianceApi.municipios(uf)` | `GET /api/v1/compliance/uf/{uf}/municipios` | `MunicipiosResponse` | MunicipiosResponse (IBGE) |
| `/compliance-radar` | `complianceApi.populacao(cod)` | `GET /api/v1/compliance/municipio/{cod}/populacao` | `PopulacaoResponse` | PopulacaoResponse (IBGE) |
| `/compliance-radar` | `complianceApi.perfil(cod)` | `GET /api/v1/compliance/municipio/{cod}/perfil` | `PerfilResponse` | PerfilResponse (IBGE) |
| `/taxpredict` | `taxpredictApi.predict(input)` | `POST /api/v1/taxpredict/predict` | `TaxPredictResult` | **PredictResponse** |
| `/taxpredict` | `taxpredictApi.macro()` | `GET /api/v1/taxpredict/macro` | `MacroResult` | MacroResponse (IBGE/BCB) |
| `/licita-watch` | `licitawatchApi.evaluate(cnpj,ref)` | `POST /api/v1/licitawatch/orgao/{cnpj}/evaluate?referencia=` | `LicitaEvaluation` | EvaluationResponse |
| `/petibot` | `petibotApi.assemble(input)` | `POST /api/v1/petibot/assemble` | `PetiResult` | **AssembleResponse** |
| `/concilia` | `conciliaApi.recommend(input)` | `POST /api/v1/concilia/recommend` | `ConciliaResult` | **RecommendResponse** |
| `/defensor` | `defensorApi.run(input)` | `POST /api/v1/defensor/run` | `DefensorResult` | DefensorRunResponse |
| `/defensor` | `defensorApi.reputacao(termo)` | `GET /api/v1/defensor/reputacao/{termo}` | `ReputacaoResult` | ReputacaoResponse |
| `/defensor` | `defensorApi.protocolar(input)` | `POST /api/v1/defensor/protocolar` | `ProtocoloResult` | ProtocoloResponse |
| `/entidade/[cnpj]` | `entidadeApi.get(cnpj)` | `GET /api/v1/entidade/{cnpj}` | `EntidadeResponse` | EntidadeResponse (Receita) |
| `/inicio`, `/alertas`, `/auditoria`, `/conformidade`, `/configuracoes`, `/danobot`, `/tribuna`, `/entidade` | — (mock only) | — | — (view-models locais) | — |

---

# lib/api — cliente HTTP + módulos por produto

## `lib/api/client.ts` 🌐

- **Entradas**
  - `GATEWAY_URL` = `process.env.NEXT_PUBLIC_GATEWAY_URL ?? 'http://localhost:8000'` 🌐 (base de toda chamada ao gateway a partir do browser).
  - Resposta `fetch` bruta: `res.ok`, `res.status`, header `content-type`, header `Retry-After`, corpo `problem+json`/`json`.
- **Intermediário ⚙**
  - `ApiError.problem` (shape RFC 7807, montado a partir do corpo): `{ type: string; title: string; status: number; detail: string; instance?: string; contract_version?: string; retry_after?: number }` 🌐. Fallbacks: `type ?? 'about:blank'`, `title ?? res.statusText`, `detail ?? 'Erro desconhecido.'`; `retry_after` lê `problem['retry-after']` ou header `Retry-After` → `Number(...)`.
  - `ApiError extends Error`: campos públicos `status: number`, `problem: {...}`; `name = 'ApiError'`; `message = problem.detail`.
- **Saídas 🌐**
  - `request<T>(path, init)`: `fetch(\`${GATEWAY_URL}${path}\`, { credentials: 'include', headers: { 'Content-Type': 'application/json', ...init.headers }, ...init })`. `204` → `undefined`.
  - `api.get<T>(path)` → GET.
  - `api.post<T>(path, body)` → POST com `JSON.stringify(body)`.
  - `api.postForm<T>(path, body: FormData)` → POST multipart (headers `{}` para o browser definir o boundary).
- **Fronteiras 🌐** — todo tráfego browser↔gateway; `credentials: 'include'` envia o cookie httpOnly `jwt`; `ApiError.problem` espelha o `application/problem+json` (RFC 7807) do gateway Python.

## `lib/api/auth.ts` 🌐🔒

- **Entradas**
  - `MeResponse` (DTO recebido de `/api/auth/me`): `{ user_id: string; tenant_id: string | null; role: RbacRole }` 🌐 (espelha claims do JWT no gateway).
- **Intermediário ⚙** — nenhum; repassa o JSON.
- **Saídas 🌐**
  - `authApi.me()` → `fetch('/api/auth/me', { cache: 'no-store' })` (same-origin, BFF). Lança `Error('auth/me ${status}')` se `!res.ok`.
- **Fronteiras 🌐🔒** — same-origin ao BFF que porta o cookie `jwt` (httpOnly) ao gateway.

## `lib/api/legalscore.ts` 🌐

- **Entradas / DTOs recebidos**
  - `LegalScoreBreakdownFactor`: `{ name: string; label: string; value: number /*0–1*/; description?: string }`.
  - `LegalScoreResult` 🌐 (**espelha ScoreResponse** Python): `{ score: number; risk_level: 'BAIXO'|'MODERADO'|'ALTO'|'CRITICO'; confidence_interval: [number, number]; breakdown: LegalScoreBreakdownFactor[]; engine: 'python'|'rust'; disclaimer: string; source_date: string; lag_days: number; request_id: string; leaf_hash?: string; merkle_root?: string; is_partial?: boolean }`.
  - `ModelMetrics` 🌐 (espelha `GET /model-metrics`, services/scoring/validation): `{ model_type: 'heuristica'|'calibrado'; validation_status: 'pending'|'validated'; auc: number|null; brier_score: number|null; calibration_r2: number|null; n_validation_samples: number; validation_note: string; last_calibrated: string|null; target_auc: number; target_brier: number }`.
  - `BatchJob`: `{ job_id: string; status: 'queued'|'running'|'done'|'failed'; progress: number; total: number; created_at: string; download_url?: string }`.
  - resposta `audit`: `{ request_id: string; leaf_hash: string; merkle_root: string; proof: Array<{ position: 'L'|'R'; hash: string }> }`.
  - resposta `batchScore`: `{ job_id: string; total: number; status: string }` (202).
- **Saídas 🌐 (payloads enviados)**
  - `score(cnpj)` → POST `/api/v1/legalscore/score` body `{ cnpj }` 🔒.
  - `modelMetrics()` → GET `/api/v1/legalscore/model-metrics`.
  - `audit(requestId)` → GET `/api/v1/legalscore/audit/${requestId}`.
  - `batchScore(cnpjs)` → POST `/api/v1/legalscore/batch` body `{ cnpjs: string[] }` 🔒.
  - `batchStatus(jobId)` → GET `/api/v1/legalscore/batch/${jobId}`.
- **Fronteiras 🌐** — `LegalScoreResult ↔ ScoreResponse`; `risk_level` alinhado à união `RiskLevel` (tokens).

## `lib/api/compliance.ts` 🌐

- **Entradas / DTOs recebidos**
  - `ComplianceEvaluation`: `{ cod_ibge: string; evaluated_at: string; rules_fired: number; envelopes: unknown[]; contract_version: string }`.
  - `Municipio`: `{ cod_ibge: string; municipio: string; uf: string }`.
  - `MunicipiosResponse`: `{ uf: string; total: number; municipios: Municipio[]; source: string; contract_version: string }`.
  - `PopulacaoResponse`: `{ cod_ibge: string; populacao: number|null; ano: string|null; source: string; contract_version: string }`.
  - `PerfilResponse`: `{ cod_ibge: string; populacao: number|null; populacao_ano: string|null; pib_reais: number|null; pib_ano: string|null; pib_per_capita: number|null; empresas: number|null; pessoal_ocupado: number|null; pessoal_assalariado: number|null; cempre_ano: string|null; area_km2: number|null; area_ano: string|null; densidade_demografica: number|null; source: string; contract_version: string }`.
- **Saídas 🌐**
  - `evaluate(ibgeCode)` → POST `/api/v1/compliance/municipality/${ibgeCode}/evaluate` body `{}`.
  - `municipios(uf)` → GET `/api/v1/compliance/uf/${uf}/municipios` (coleta ao vivo IBGE).
  - `populacao(codIbge)` / `perfil(codIbge)` → GET correspondentes.
- **Fronteiras 🌐** — DTOs espelham as respostas de compliance (IBGE) com `contract_version`.

## `lib/api/concilia.ts` 🌐

- **Entradas / DTOs recebidos**
  - `ConciliaFator`: `{ nome: string; impacto: number; descricao: string }`.
  - `ConciliaResult` 🌐 (**espelha RecommendResponse**): `{ valor_minimo: number; valor_sugerido: number; valor_maximo: number; percentual_causa: number /*0–1*/; fatores: ConciliaFator[]; risco_reu?: number|null; probabilidade_procedencia?: number|null; computed_at: string; contract_version: string }`.
- **Saídas 🌐 (payload)**
  - `ConciliaInput`: `{ descricao: string; valor_causa: number; tipo_acao: string; cnpj_reu?: string 🔒; cnpj_autor?: string 🔒 }`.
  - `recommend(input)` → POST `/api/v1/concilia/recommend`.
- **Fronteiras 🌐** — `ConciliaResult ↔ RecommendResponse`.

## `lib/api/contabilia.ts` 🌐

- **Entradas / DTOs recebidos**
  - `AuditFinding`: `{ rule: string; severity: 'CRITICO'|'ALTO'|'MEDIO'; description: string; detail: string }`.
  - `AuditReport` 🌐: `{ report_id: string; generated_at: string; cnpj?: string|null 🔒; filename?: string|null; status: string; summary: Record<string, number>; total_findings: number; findings: AuditFinding[]; fields_analyzed: string[]; data_lag_note: string; contract_version: string }`.
- **Saídas 🌐 (payload)**
  - `upload(file: File, cnpj?)`: constrói `FormData` com `form.append('file', file)`; querystring `?cnpj=${encodeURIComponent(cnpj)}` 🔒. `api.postForm<AuditReport>('/api/v1/contabilia/audit/upload'+qs, form)`.
- **Fronteiras 🌐** — upload multipart; `AuditReport ↔ AuditReportResponse`.

## `lib/api/defensor.ts` 🌐

- **Entradas / DTOs recebidos**
  - `EventoAgente`: `{ ts: string; evento: string; detalhe: string; status: 'ok'|'running'|'pending' }`.
  - `DefensorResult` 🌐: `{ classificacao: string; canal: string; eventos: EventoAgente[]; secoes: PetiSection[]; precedentes_encontrados: number; casos_anteriores: number; subsidios: string[]; proximo_responsavel: string; status: string; defesa_via: string; computed_at: string; contract_version: string }`.
  - `ReputacaoResult`: `{ termo: string; encontrado: boolean; reputacao: { empresa?: string; total?: number; respondidas?: number; resolvidas?: number; pct_resposta?: number; pct_resolucao?: number; nota_media?: number|null }; source: string; contract_version: string }`.
  - `ProtocoloResult`: `{ canal: string; modo: string; status: string; numero_protocolo: string|null; url: string|null; mensagem: string; enviado_em: string; contract_version: string }`.
- **Saídas 🌐 (payloads)**
  - `DefensorInput`: `{ descricao: string; canal: string; tipo_caso: string; reclamante: string; reclamada: string; cnpj_reclamada?: string 🔒; valor?: number }` → POST `/api/v1/defensor/run`.
  - `reputacao(termo)` → GET `/api/v1/defensor/reputacao/${encodeURIComponent(termo)}`.
  - `ProtocoloInput`: `{ canal: string; reclamante: string; reclamada: string; cnpj_reclamada?: string 🔒; resumo: string; defesa?: string; valor?: number; anexos?: string[] }` → POST `/api/v1/defensor/protocolar` 🔒 (ação externa sensível).
- **Fronteiras 🌐** — `secoes` reusa `PetiSection` (importado de petibot); `defesa_via` mapeado a `Provenance`; `status`/`modo` mapeados às uniões `ProtocolStatus`/`ProtocolMode`.

## `lib/api/entidade.ts` 🌐🔒

- **Entradas / DTOs recebidos**
  - `CnpjCadastro`: `{ razao_social?: string; situacao_cadastral?: string; data_situacao_cadastral?: string|null; porte?: string|null; natureza_juridica?: string|null; capital_social?: number|null; data_abertura?: string|null; municipio?: string|null; uf?: string|null; cnae_fiscal?: string|null; cnae_descricao?: string|null }`.
  - `EntidadeResponse` 🌐: `{ cnpj: string 🔒; encontrado: boolean; cadastro: CnpjCadastro; source: string; contract_version: string }`.
- **Saídas 🌐**
  - `get(cnpj)` → GET `/api/v1/entidade/${cnpj.replace(/\D/g,'')}` 🔒 (normaliza só dígitos).
- **Fronteiras 🌐** — dados ao vivo da Receita; `EntidadeResponse ↔ EntidadeResponse (Python)`.

## `lib/api/licitawatch.ts` 🌐

- **Entradas / DTOs recebidos**
  - `LicitaIndicadores`: `{ pct_mesmo_vencedor: number; pct_dispensa: number; pct_unico_proponente: number; pct_prazo_curto: number }` (0–1).
  - `LicitaEvaluation` 🌐: `{ cnpj_orgao: string 🔒; referencia: string; total_contratos: number; indicadores: LicitaIndicadores; alertas: number; envelopes: unknown[]; contract_version: string }`.
- **Saídas 🌐**
  - `evaluate(cnpjOrgao, referencia)` → POST `/api/v1/licitawatch/orgao/${cnpjOrgao}/evaluate?referencia=${encodeURIComponent(referencia)}` body `{}`.
- **Fronteiras 🌐** — dados PNCP; `LicitaEvaluation ↔ EvaluationResponse`.

## `lib/api/petibot.ts` 🌐

- **Entradas / DTOs recebidos**
  - `PetiSection`: `{ titulo: string; conteudo: string; precedentes: string[] }` (reusado por defensor).
  - `PetiResult` 🌐 (**espelha AssembleResponse**): `{ tipo_acao: string; polo_ativo: string; polo_passivo: string; secoes: PetiSection[]; precedentes_encontrados: number; risk_score?: number|null; probability_favorable?: number|null; computed_at: string; contract_version: string }`.
- **Saídas 🌐 (payload)**
  - `PetiInput`: `{ descricao: string; tipo_acao: string; polo_ativo: string; polo_passivo: string; valor_causa?: number; cnpj_parte?: string 🔒 }` → POST `/api/v1/petibot/assemble`.
- **Fronteiras 🌐** — `PetiResult ↔ AssembleResponse`; RAG com precedentes verificáveis.

## `lib/api/taxpredict.ts` 🌐

- **Entradas / DTOs recebidos**
  - `JurisprudenciaHit`: `{ doc_id: string; similarity: number; ementa: string; decisao: 'FAVORAVEL'|'DESFAVORAVEL'|'PARCIAL'|'DESCONHECIDO'; tribunal?: string|null; ano?: number|null }`.
  - `TaxPredictResult` 🌐 (**espelha PredictResponse**): `{ materia: string; probability: number; ci_lower: number; ci_upper: number; rag_hits: number; jurisprudencias: JurisprudenciaHit[]; features_used: Record<string, number>; computed_at: string; model_version: string; is_fallback: boolean; contract_version: string }`.
  - `IpcaMensal`: `{ periodo: string; valor: number }`.
  - `MacroResult`: `{ ipca: { acumulado_12m?: number; referencia?: string; mensal?: IpcaMensal[] }; bcb?: { selic?: number; selic_data?: string; cambio_usd?: number; cambio_data?: string }; source: string; contract_version: string }`.
- **Saídas 🌐 (payload)**
  - `TaxPredictInput`: `{ descricao: string; materia: string; valor?: number; orgao_autuante?: string; ano_autuacao?: number }` → POST `/api/v1/taxpredict/predict`.
  - `macro()` → GET `/api/v1/taxpredict/macro`.
- **Fronteiras 🌐** — `TaxPredictResult ↔ PredictResponse`; `MacroResult` espelha coleta IBGE/BCB.

## `lib/export/documents.ts`

- **Entradas**
  - `DocSection`: `{ titulo: string; conteudo: string }`.
  - `DocOptions`: `{ filename: string; title: string; subtitle?: string; sections: DocSection[]; footer? string }`.
  - `downloadJson(filename: string, data: unknown)`.
- **Intermediário ⚙**
  - `slugifyFilename(s)` → normaliza NFD, remove acentos/não-alfanuméricos, lowercase; fallback `'documento'`.
  - `escapeHtml(s)` → escapa `& < >`.
  - Monta string HTML (`<!DOCTYPE html>` com namespaces MS Office/Word) a partir das seções.
- **Saídas (download local, não HTTP)**
  - `downloadDoc(...)` → `Blob([html], { type: 'application/msword' })` → download `${filename}.doc`.
  - `downloadJson(...)` → `Blob([JSON.stringify(data,null,2)], { type: 'application/json' })` → download `${filename}.json`.
  - `triggerDownload(blob, filename)` cria `<a download>` e revoga o objectURL.

---

# BFF — app/api/auth/*/route.ts (Next Route Handlers)

## `app/api/auth/login/route.ts` 🌐🔒

- **Entradas**
  - Corpo aceito: JSON (fetch client) OU `form-urlencoded` (submit nativo). `readBody(req)` → `Record<string,string>`.
  - Campos UI: `email`, `password`, `tenant` (do `<form>`); ou `username`/`tenant_slug` (JSON).
  - `GATEWAY_URL` = `process.env.NEXT_PUBLIC_GATEWAY_URL ?? 'http://localhost:8000'` 🌐.
- **Intermediário ⚙ — mapeamento de campos**
  - `payload = { username: raw.username ?? raw.email ?? '', password: raw.password ?? '', tenant_slug: raw.tenant_slug ?? raw.tenant ?? '' }` (UI `email`→`username`, `tenant`→`tenant_slug`) 🔒.
- **Saídas 🌐 + cookie**
  - `POST ${GATEWAY_URL}/api/v1/auth/token` com JSON `{ username, password, tenant_slug }` 🔒.
  - Sucesso: repassa `set-cookie` do gateway; se ausente e houver `data.access_token`, grava cookie **`jwt`** 🔒: `{ httpOnly: true, secure: NODE_ENV === 'production', sameSite: 'strict', maxAge: 60*60*24 /*24h*/, path: '/' }`.
  - Resposta ao client: `NextResponse.json({ ok: true })` (fetch/JSON) ou `redirect('/inicio', 303)` (submit nativo).
  - Erro: fetch → `NextResponse.json(err, { status })`; submit nativo → `redirect('/login?erro=1', 303)`.
- **Fronteiras 🌐🔒** — cookie httpOnly `jwt`; DTO de request espelha o schema `POST /auth/token` (username/password/tenant_slug) do gateway.

## `app/api/auth/logout/route.ts` 🔒

- **Entradas** — `GET` ou `POST` (navegação do botão "Sair" / form).
- **Saídas + cookie** — `clearAndRedirect(req)`: `redirect('/login', 303)` + `res.cookies.set('jwt', '', { httpOnly: true, path: '/', maxAge: 0 })` (expira o cookie).
- **Fronteiras 🔒** — limpa a sessão httpOnly.

## `app/api/auth/me/route.ts` 🌐🔒

- **Entradas** — cookie httpOnly `jwt` via `req.cookies.get('jwt')?.value` 🔒; `GATEWAY_URL` 🌐.
- **Intermediário ⚙** — sem `jwt` → `401 { detail: 'Não autenticado.' }`.
- **Saídas 🌐** — `GET ${GATEWAY_URL}/api/v1/auth/me` com header `Authorization: Bearer ${jwt}` 🔒, `cache: 'no-store'`; repassa `data` + `res.status`; catch → `502 { detail: 'Gateway indisponível.' }`.
- **Fronteiras 🌐🔒** — proxy same-origin que mantém o token fora do JS do browser; resposta = `MeResponse`.

---

# Estado / providers / middleware / layout

## `app/context/shell.tsx` — ShellProvider 🔒

- **Entradas**
  - `DEMO_DEFAULT` = `process.env.NEXT_PUBLIC_DEMO_MODE !== 'false'` (demo liga por padrão).
  - `VALID_ROLES: RbacRole[] = ['admin','analyst','viewer']`.
  - Hidratação: `authApi.me()` → `MeResponse { user_id, tenant_id, role }` 🌐🔒.
- **Intermediário ⚙ — estado React**
  - `Tenant`: `{ id: string; name: string }`.
  - `ShellContextValue`: `{ tenant: Tenant|null; role: RbacRole; demoMode: boolean; setTenant: (t:Tenant)=>void; setRole: (r:RbacRole)=>void; setDemoMode: (v:boolean)=>void }`.
  - Estado inicial: `tenant = { id:'demo', name:'Acme Ltda.' }`, `role = 'admin'`, `demoMode = DEMO_DEFAULT`.
  - `useEffect`: se `me()` resolve → `if VALID_ROLES.includes(me.role) setRole(me.role)`; `if me.tenant_id setTenant({ id: me.tenant_id, name: me.tenant_id })`; falha (401) → mantém defaults demo (best-effort, `cancelled` guard).
- **Saídas** — contexto para toda a shell; `useShell()` lança se fora do provider.
- **Fronteiras 🔒** — ponte entre sessão real (JWT via `me()`) e o modo demo.

## `app/providers.tsx` — Providers (React Query)

- **Entradas** — `NODE_ENV` (devtools só em `development`).
- **Intermediário ⚙**
  - `QueryClient` `defaultOptions.queries`: `staleTime: 30_000`; `retry`: função — `if (status === 429 || status === 501) return false; else failureCount < 2`.
  - Singleton `browserQueryClient` no browser; novo client no server.
- **Saídas** — `QueryClientProvider` + `ReactQueryDevtools` (dev).

## `app/layout.tsx` — RootLayout

- **Entradas** — `metadata` `{ title, description, other:{'color-scheme':'light'} }`; `globals.css`.
- **Saídas** — `<html lang="pt-BR"><body><Providers>{children}</Providers></body></html>`.

## `app/(shell)/layout.tsx` — ShellLayout

- **Saídas** — `<ShellProvider>` → `Sidebar` + `Topbar` + `<main>{children}</main>` (max-width `content`).

## `app/page.tsx` — RootPage

- **Saídas** — `redirect('/inicio')`.

## `middleware.ts` 🔒

- **Entradas**
  - `REQUIRE_AUTH` = `process.env.REQUIRE_AUTH === 'true'` (desligado por padrão = modo demo).
  - `PUBLIC_PATHS = ['/login']`; cookie `jwt` 🔒.
- **Intermediário ⚙**
  - `!REQUIRE_AUTH` → `NextResponse.next()`.
  - Libera `/api/auth*` e `PUBLIC_PATHS`.
  - Sem cookie `jwt` → `redirect('/login?next=${pathname}')`.
  - **NOTA (do código)**: valida apenas PRESENÇA do cookie, não a assinatura RS256 (P0 pendente).
- **Saídas** — `config.matcher` exclui assets estáticos e arquivos com extensão de imagem.
- **Fronteiras 🔒** — proteção de rota por presença de cookie JWT.

## `next.config.mjs`

- **Entradas** — `NEXT_SERVER_ACTIONS_ALLOWED_ORIGINS` (origens permitidas para server actions).

---

# components/ (app-específicos)

## `components/shell/Sidebar.tsx`

- **Entradas** — `useShell()` → `{ tenant, role }`; `usePathname()`.
- **Intermediário ⚙**
  - `NavItem`: `{ code: string; label: string; href: string; locked?: boolean }`.
  - `PLATAFORMA_NAV` (IN/EN/AL/AU/CF); `PRODUTOS_NAV` (LS/CT/CR/TP/LW/DB[locked]/PB/DF/CC/TC); `configItem` (CG).
  - `NavLink`: `isActive = pathname === href || pathname.startsWith(href+'/')`.
- **Saídas (DTOs renderizados)** — nav com `tenant?.name ?? '—'`, código+label; `role === 'admin'` mostra Configurações; footer com `role` e link `href="/api/auth/logout"` 🔒. `DB` fica `locked` (chip "bloq.").

## `components/shell/Topbar.tsx`

- **Entradas** — `useShell()` → `{ role, setRole, demoMode, setDemoMode }`; `usePathname()`, `useRouter()`.
- **Intermediário ⚙**
  - `ROLE_LABELS: Record<RbacRole,string>` = `{ admin:'Admin', analyst:'Analista', viewer:'Leitor' }`.
  - `ROLE_ORDER: RbacRole[] = ['admin','analyst','viewer']`.
  - `pathToBreadcrumb(pathname)` → mapa fixo rota→título.
  - `handleSearch`: Enter → `router.push('/entidade/${encodeURIComponent(val)}')` 🔒 (CNPJ/empresa/município).
- **Saídas** — breadcrumb, busca global, toggle demo (`setDemoMode(!demoMode)`), switcher RBAC (`setRole(r)`), barra de rate-limit mock (42/100), sino de notificações (3).

## `components/ApiErrorBanner.tsx` 🌐

- **Entradas** — props `{ error: unknown; demoMode?: boolean }`; importa `ApiError` e `ProblemJson`.
- **Intermediário ⚙** — `if (demoMode || !(error instanceof ApiError)) return null`.
- **Saídas** — `<ProblemJsonError error={error.problem as ProblemJson} />` 🌐 (renderiza o RFC 7807).

---

# páginas (auth) e (shell)

## `(auth)/login/page.tsx` 🔒

- **Entradas (form fields)** — `<form action="/api/auth/login" method="POST">` com `name="email"` (type email, required), `name="password"` (type password, required), `name="tenant"` (`<select>`: `''`, `dev-tenant`). 🔒
- **Saídas** — submit nativo ao BFF `/api/auth/login`; hero estático (chips, SLA honesto). `metadata.title`.

## `(shell)/inicio/page.tsx` — dashboard (mock)

- **Entradas** — `useShell()` → `{ demoMode, setDemoMode }`; `useRouter()`.
- **Intermediário ⚙ (mock/view-models)**
  - `PRODUCTS` (8 cards: code/name/desc/href/sla, DanoBot `blocked`).
  - `SOURCES` (Receita 2d … SNIS 548d).
  - `RECENT_ALERTS` (severity `CRITICAL|HIGH|MEDIUM`, title, ref 🔒 CNPJ/IBGE, time).
  - KPIs inline (Consultas, Auditorias, Alertas críticos, Uso da API).
- **demoMode branching** — `!demoMode` → `<EmptyState>` com CTA "Ativar dados de demonstração".
- **Saídas** — grid de produtos (navegação), `FreshnessSeal` por fonte via `lagToFreshnessBand`, CTA entidade.

## `(shell)/legalscore/page.tsx` 🌐🔒

- **Entradas**
  - `useShell()` → `{ role, demoMode }`; form field `cnpj` (state) 🔒; checkbox `simulateDegraded`; tab `activeTab`.
  - Fetch: `useMutation(() => legalscoreApi.score(cnpj))` → `LegalScoreResult` 🌐.
- **Intermediário ⚙**
  - `MOCK_BREAKDOWN` (7 fatores), `MOCK_HISTORY` (12 meses), `factorColor(v)`.
  - `hasResult = demoMode || scoreMutation.isSuccess`.
  - `result` view-model: em demo, objeto sintético (`score` 648/521, `risk_level:'MODERADO'`, `confidence_interval`, `engine:'rust'`, `request_id:'req_demo_001'`, `lag_days:4`, `is_partial`); senão `scoreMutation.data`.
- **role branching** — `role === 'viewer'` → `<ViewerBanner>`; `RbacGate requires="analyst"` envolve "Calcular score"/"Score em lote"; `requires="admin"` envolve "Recalibrar modelo".
- **Saídas (DTOs renderizados)** — `TrustHeader`, `ScoreGauge`, `HeuristicBadge`, breakdown bars, `MerklePanel` (auditoria), `AreaChart` (recharts), `JobProgress`/`Dropzone` (lote), `DegradationBanner`, `ApiErrorBanner`.

## `(shell)/contabilia/page.tsx` 🌐🔒

- **Entradas**
  - `useShell()` → `{ role, demoMode }`; upload de `File` via `Dropzone`.
  - Fetch: `useMutation((file) => contabiliaApi.upload(file))` → `AuditReport` 🌐 (multipart).
- **Intermediário ⚙**
  - `Stage = 'upload'|'processing'|'report'`; `expanded: Set<string>`.
  - `SEVERITY_VARIANT`/`SEVERITY_STATUS` maps; `FindingView { id, severity, label, status, evidence, source?, lagDays? }`.
  - `findings`: demo/sem dados → `MOCK_FINDINGS`; senão `apiData.findings.map(...)` (`f.rule`→id, `f.description`→label, `f.detail`→evidence).
  - `reportId`: demo → `'rep_demo_001'`, senão `apiData.report_id`.
  - Mocks: `CHECKS` (CC01–CC08), `BENFORD_DATA`, `MOCK_STEPS: JobStep[]`.
- **Saídas** — `JobProgress` (processing), lista de achados (expand), `downloadDoc` (laudo `.doc`), `BarChart` Benford (só demo), `FreshnessSeal` SICONFI 365d.

## `(shell)/compliance-radar/page.tsx` 🌐

- **Entradas**
  - `useShell()` → `{ demoMode }`; `selectedUf`, `selectedMun { cod, nome }`.
  - Fetch: `evalMutation` → `complianceApi.evaluate(PERFIL_IBGE='1302603')` → `ComplianceEvaluation`; `municipiosQuery` → `complianceApi.municipios(selectedUf)` (`enabled: !!selectedUf`) → `MunicipiosResponse`; `perfilQuery` → `complianceApi.perfil(selectedMun.cod)` (`enabled: !!selectedMun`) → `PerfilResponse`. 🌐
- **Intermediário ⚙** — `UF_DATA` (27 UFs), `SEVERITY_COLORS`, `MOCK_ALERTS: AlertItem[]`, `MOCK_INDICATORS`, `TABS`.
- **Saídas** — cartograma UF, lista de municípios ao vivo IBGE, perfil formatado (`toLocaleString` pt-BR: população/PIB/per capita/empresas/pessoal/área/densidade), `AlertList`, `EmptyState`, `ApiErrorBanner`.

## `(shell)/taxpredict/page.tsx` 🌐

- **Entradas**
  - `useShell()` → `{ role, demoMode }`; form fields `descricao`, `materia` (`MATERIAS`), checkbox `showFallback`.
  - Fetch: `predictMutation` → `taxpredictApi.predict({ descricao, materia })` → `TaxPredictResult`; `macroQuery` → `taxpredictApi.macro()` (staleTime 1h) → `MacroResult`. 🌐
- **Intermediário ⚙**
  - `MOCK_RESULT` (probability 0.62, ci, shap[], jurisprudencias[]).
  - `result` view-model: demo (com/sem fallback 0.30) ou mapeado de `apiData` (`features_used`→shap com `impact:0`; `jurisprudencias`→chips).
  - `ipca = macroQuery.data?.ipca`, `bcb = macroQuery.data?.bcb`.
  - `DecisaoChip` map FAVORAVEL→LOW etc.; `cn()` helper local.
- **role branching** — `viewer` → `ViewerBanner`; `RbacGate requires="analyst"` no "Prever desfecho".
- **Saídas** — card macro (IPCA/SELIC/USD + mini-barras mensal), `ProbabilityDonut`, `HeuristicBadge`, SHAP bars, `VerifiableCitationChip` (link DATAJUD), `DegradationBanner` (fallback), `ApiErrorBanner demoMode`.

## `(shell)/licita-watch/page.tsx` 🌐🔒

- **Entradas**
  - `useShell()` → `{ demoMode }`; form fields `cnpj` 🔒, `referencia` (default '2026').
  - Fetch: `evalMutation` → `licitawatchApi.evaluate(cnpj.replace(/\D/g,''), referencia)` → `LicitaEvaluation`. 🌐
- **Intermediário ⚙**
  - `RULES` (mock LL01–LL04), `pctSeverity(pct,crit,high)`, `MOCK_CONTRATOS`, `SEVERITY_COLORS`.
  - `rules`: demo/sem dados → `RULES`; senão derivado de `apiData.indicadores` (`pct_* * 100`, `pctSeverity`).
  - `totalContratos`: demo 247 ou `apiData.total_contratos`.
- **Saídas** — cards de regra com %, `FreshnessSeal` PNCP 1d, `Table` de contratos (só demo), `EmptyState`, `ApiErrorBanner demoMode`.

## `(shell)/petibot/page.tsx` 🌐🔒

- **Entradas**
  - `useShell()` → `{ role, demoMode }`; form fields `descricao`, `tipo` (`TIPOS`), `poloAtivo`, `poloPassivo`.
  - Fetch: `assembleMutation` → `petibotApi.assemble({ descricao, tipo_acao, polo_ativo, polo_passivo })` → `PetiResult`. 🌐
- **Intermediário ⚙**
  - `MOCK_SECOES` (4 seções DOS FATOS/DO DIREITO/VERBAS/PEDIDOS com precedentes).
  - `SecaoView { titulo, conteudo, precedentes: {doc_id,href,count}[], precedentes_count }`.
  - `secoes`: demo → `MOCK_SECOES`; senão `apiData.secoes.map(...)` (precedentes[]→chips com href DATAJUD).
- **role branching** — `viewer` → `ViewerBanner`; `RbacGate requires="analyst"` no "Montar peça".
- **Saídas** — cards editáveis (`contentEditable`), `VerifiableCitationChip`, `AntiHallucinationGuard`, `downloadDoc` (.docx→.doc), rail de enriquecimento (LegalScore/TaxPredict mock, RAG ChromaDB).

## `(shell)/concilia/page.tsx` 🌐🔒

- **Entradas**
  - `useShell()` → `{ role, demoMode }`; form fields `tipo`, `valor`, `cnpjReu` 🔒, `descricao`.
  - Fetch: `recommendMutation` → `conciliaApi.recommend({ descricao, valor_causa: Number(valor.replace…), tipo_acao, cnpj_reu })` → `ConciliaResult`. 🌐
- **Intermediário ⚙**
  - `riskBand(score)` → LOW/MODERADO/ALTO/CRITICO; `MOCK_RESULT`.
  - `result` view-model: demo ou de `apiData` (`percentual_causa*100`→pct, `riskBand(risco_reu)`, `probabilidade_procedencia`, `fatores`).
- **role branching** — `viewer` → `ViewerBanner`; `RbacGate requires="analyst"` no "Recomendar acordo".
- **Saídas** — `SettlementRangeBar` (min/sugerido/max, pctOfCase), badge risco réu, prob. procedência, waterfall de fatores, `ApiErrorBanner demoMode`.

## `(shell)/defensor/page.tsx` 🌐🔒 (agente, fluxo 4 fases)

- **Entradas**
  - `useShell()` → `{ role, demoMode }`; form fields `descricao`, `canal` (`CANAIS`), `tipo` (`TIPOS`), `reclamante`, `reclamada`.
  - Fetch: `runMutation` → `defensorApi.run({ descricao, canal, tipo_caso, reclamante, reclamada })` → `DefensorResult`; `reputacaoQuery` → `defensorApi.reputacao(reclamada)` (`enabled: !demoMode && reclamada.length>=3`) → `ReputacaoResult`; `protoMutation` → `defensorApi.protocolar({...})` → `ProtocoloResult`. 🌐🔒
- **Intermediário ⚙**
  - `Phase = 'entrada'|'exec'|'result'|'proto'`; `Scenario = 'normal'|'juris_vazia'|'llm_template'|'erro'`; `PHASE_INDEX`.
  - `TITULO_BY_EVENTO` map; `PROVENANCE_BY_VIA` (`llm→ia`, `parcial`, `template`).
  - `events: AgentEvent[]` — demo → `MOCK_EVENTS` (8 eventos); senão `apiData.eventos.map(...)` (+`titulo` derivado).
  - `provenance: Provenance` — demo por `scenario`; real via `PROVENANCE_BY_VIA[apiData.defesa_via]`.
  - `secoes: SecaoView[]` (`{ titulo, conteudo, precedentes_count, precedentes:{doc_id,href}[] }`) — demo `MOCK_SECOES` ou `apiData.secoes`.
  - `jurisEmpty` — reconciliação: demo `scenario==='juris_vazia'`, real `precedentes_encontrados===0 && todas seções sem precedentes`.
  - `useStaggeredReveal({ total: events.length, auto:false })` → `{ revealed, done, run }`; `startFeed()` remonta (replayKey) e roda stagger.
  - `mapProtocolo(p: ProtocoloResult)` → props de `ProtocolStatusCard`.
  - `RepView { empresa?, total?, pct_resolucao?, nota_media? }`.
  - Fixtures: `DEMO_API_ERROR` (ApiError 503), `MOCK_EVENTS`, `MOCK_SECOES`, `DEMO_REPUTACAO`, `PROTOCOLO_FIXTURE` (5 estados).
- **role branching** — `isViewer` → `ViewerBanner`; `RbacGate requires="analyst"` em "Acionar agente" e "Protocolar defesa".
- **Saídas** — `StepIndicator`, `Segmented` (tratamento/cenário/estado proto), `AgentLiveFeed`, `ProvenanceTag`, `VerifiableCitationChip`, `AntiHallucinationGuard`, `ProtocolStatusCard`, `downloadDoc` (defesa), `EnrichmentRail` (reputação Consumidor.gov).

## `(shell)/entidade/page.tsx` (índice) 🔒

- **Entradas** — form field `cnpj` 🔒; `useRouter()`.
- **Intermediário ⚙** — `handleSubmit`: `clean = cnpj.replace(/\D/g,'')`; `if clean.length===14` → `router.push('/entidade/${encodeURIComponent(cnpj)}')`.
- **Saídas** — `EmptyState` + form de busca.

## `(shell)/entidade/[cnpj]/page.tsx` 🌐🔒

- **Entradas**
  - `useParams()` → `cnpj` 🔒; `useShell()` → `{ demoMode }`.
  - Fetch: `entidadeQuery` → `entidadeApi.get(cnpjDigits)` (`enabled: !demoMode && cnpjDigits.length===14`) → `EntidadeResponse`. 🌐
- **Intermediário ⚙**
  - `fmtDate(v)` (YYYY-MM-DD→DD/MM/YYYY); `MOCK_ENTITY`, `MOCK_LENSES` (6 lentes com summary/label/variant).
  - `entity` view-model: demo `MOCK_ENTITY` (cnpj override) ou mapeado de `cad = entidadeQuery.data?.cadastro` (`razao_social`, `situacao_cadastral`, `cnae_fiscal`+`cnae_descricao`, `porte`, `capital_social`→BRL, `data_abertura`→fmtDate).
  - `ativa = entity.situacao === 'ATIVA'`.
- **demoMode branching** — real + `isLoading` → `SkeletonCard`; `!encontrado` → `DegradationBanner` + `EmptyState`.
- **Saídas** — header da entidade, `TrustHeader` (onVerify→/auditoria), grid de lentes (navegação `/${href}?cnpj=`), rail (alertas, Decision Ledger CTA).

## Páginas mock-only (sem fetch)

### `(shell)/alertas/page.tsx`
- **Entradas** — filtro `filterSeverity: AlertSeverity|null`.
- **Intermediário ⚙** — `MOCK_ALERTS: AlertItem[]` (5); `severities`.
- **Saídas** — `AlertList` filtrada; nota "sem PII · subject_ref apenas".

### `(shell)/auditoria/page.tsx`
- **Entradas** — `selected` request_id.
- **Intermediário ⚙** — `MOCK_DECISIONS` (3), `PRODUCT_CODE` map, `MOCK_PROOF: MerkleProof[]`.
- **Saídas** — `MerklePanel` (requestId/leaf/root/proof mock), `downloadJson` (trilha ANPD).

### `(shell)/conformidade/page.tsx` 🔒
- **Intermediário ⚙** — `ROPA` (5 fontes, `classe: publico|pessoal|sensivel`), `CLASS_STYLE`.
- **Saídas** — cards de direitos LGPD (Acesso/Portabilidade/Eliminação) com `downloadJson`; `Table` ROPA; playbook de incidentes; export trilha ANPD.

### `(shell)/configuracoes/page.tsx` 🔒
- **Entradas** — `useShell()` → `{ role }`.
- **Intermediário ⚙** — `USERS` (4), `ROLE_BADGE` map.
- **role branching** — `RbacGate requires="admin"` envolve toda a página (fallback "Acesso restrito").
- **Saídas** — tabela usuários/papéis, rate limit, chaves de API (mascaradas 🔒) — botões `disabled` (endpoints em implementação).

### `(shell)/danobot/page.tsx`
- **Saídas** — página estática "BLOQUEADO" (HTTP 501 intencional, aguardando DPO, PD-06). Sem fetch.

### `(shell)/tribuna/page.tsx`
- **Intermediário ⚙** — `PRESENCE` (4, status online/away/offline), `TIMELINE` (3).
- **Saídas** — minuta compartilhada (`contentEditable`), `Avatar`/`AvatarStack`, timeline, presença, canais. Beta/tempo real mock.

---

# packages/ui/src — primitives

## `primitives/Avatar.tsx`
- **Props** `AvatarProps`: `{ name: string; src?: string; size?: 'xs'|'sm'|'md'|'lg'; className?: string; status?: 'online'|'away'|'offline' }`.
- **Props** `AvatarStackProps`: `{ names: string[]; max?: number; size?: AvatarSize }`.
- ⚙ `initials` derivadas de `name.split(' ').slice(0,2)`.

## `primitives/Badge.tsx`
- **Props** `BadgeProps extends React.HTMLAttributes<HTMLSpanElement>`: `{ variant?: BadgeVariant; dot?: boolean }`.
  - `BadgeVariant = 'accent'|'muted'|'heuristica'|'calibrado'|'blocked'|'beta'|'live'|RiskLevel|AlertSeverity`.
- **Props** `MonoChipProps extends React.HTMLAttributes<HTMLSpanElement>`: `{ href?: string }`.
- ⚙ `getVariantStyle(variant)`; reexporta `RISK_COLORS` (tokens).

## `primitives/Button.tsx`
- **Props** `ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>`: `{ variant?: 'primary'|'secondary'|'ghost'|'danger'; size?: 'sm'|'md'|'lg'; loading?: boolean }`. `forwardRef`.

## `primitives/Card.tsx`
- **Props** `CardProps extends React.HTMLAttributes<HTMLDivElement>`: `{ padding?: 'none'|'sm'|'md'|'lg' }`.
- `CardHeader`, `SectionLabel` — `React.HTMLAttributes<HTMLDivElement|HTMLSpanElement>`.

## `primitives/Dropzone.tsx`
- **Props** `DropzoneProps`: `{ accept?: string; maxSize?: number; hint?: string; onFiles: (files: FileList)=>void; className?: string; disabled?: boolean }`.
- **Saídas** — `onFiles(FileList)` (upload de `File`).

## `primitives/Input.tsx`
- **Props** `InputProps extends React.InputHTMLAttributes<HTMLInputElement>`: `{ mono?: boolean; label?: string; error?: string; hint?: string; startIcon?: React.ReactNode; endIcon?: React.ReactNode }`. `forwardRef`.
- **Props** `TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement>`: `{ label?: string; error?: string; hint?: string; charCount?: { current: number; max: number } }`. `forwardRef`.

## `primitives/Segmented.tsx`
- **Props** `SegmentedProps`: `{ options: SegmentedOption[]; value: string; onChange: (id:string)=>void; 'aria-label'?: string; className?: string }`.
- `SegmentedOption`: `{ id: string; label: string }`.

## `primitives/Skeleton.tsx`
- **Props** `SkeletonProps extends React.HTMLAttributes<HTMLDivElement>`: `{ height?: string|number; width?: string|number; rounded?: string }`.
- `SkeletonText`: `{ lines?: number; className?: string }`; `SkeletonCard`: `{ className?: string }`.

## `primitives/Table.tsx`
- `Table/Thead/Tbody/Tr` — `React.HTMLAttributes<...>`; `Th`/`Td` — `React.Th/TdHTMLAttributes<HTMLTableCellElement> & { mono?: boolean }`.

## `primitives/Tabs.tsx`
- **Props** `TabsProps`: `{ tabs: Tab[]; activeTab: string; onTabChange: (id:string)=>void; className?: string }`; `Tab`: `{ id: string; label: string; disabled?: boolean }`.
- **Props** `TabPanelProps`: `{ id: string; activeTab: string; children: React.ReactNode; className?: string }`.
- ⚙ navegação por teclado (ArrowLeft/Right/Home/End).

---

# packages/ui/src — patterns (DTOs de domínio renderizados)

## `patterns/TrustHeader.tsx` 🌐
- **Props** `TrustHeaderProps`: `{ sources: TrustSource[]; score?: number; ciLow?: number; ciHigh?: number; modelStatus: ModelStatus; sourceNames: string[]; extraSourceCount?: number; onVerify?: ()=>void; className?: string }`.
- `TrustSource`: `{ name: string; lagDays: number; band: FreshnessBand }`.

## `patterns/FreshnessSeal.tsx`
- **Props** `FreshnessSealProps`: `{ source: string; lagDays: number; band: FreshnessBand; className?: string }`.
- ⚙ `bandLabels` (fresh→fresco, stale→defasado, very_stale→muito defasado); usa `FRESHNESS_COLORS`.

## `patterns/HeuristicBadge.tsx`
- **Props** `HeuristicBadgeProps`: `{ status: ModelStatus; size?: 'sm'|'md'; className?: string }`.

## `patterns/ScoreGauge.tsx`
- **Props** `ScoreGaugeProps`: `{ score: number; ciLow: number; ciHigh: number; size?: number; className?: string }`.
- ⚙ `SEGMENTS` (0–300 CRITICO … 700–1000 BAIXO); `scoreToAngle`, `polarToCartesian`, `describeArc`; usa `scoreToriskLevel`, `RISK_COLORS`.

## `patterns/ProbabilityDonut.tsx`
- **Props** `ProbabilityDonutProps`: `{ probability: number /*0–1*/; ciLow: number; ciHigh: number; size?: number; className?: string }`.

## `patterns/SettlementRangeBar.tsx`
- **Props** `SettlementRangeBarProps`: `{ min: number; suggested: number; max: number; pctOfCase?: number; className?: string }`.
- ⚙ `formatBRL` (Intl pt-BR), `suggestedPct`.

## `patterns/MerklePanel.tsx` 🔒
- **Props** `MerklePanelProps`: `{ requestId: string; leafHash: string 🔒; merkleRoot: string 🔒; proof: MerkleProof[]; isIntact: boolean; onReverify?: ()=>void; onExportPdf?: ()=>void; loading?: boolean; className?: string }`.
- `MerkleProof`: `{ position: 'L'|'R'; hash: string 🔒 }`.

## `patterns/VerifiableCitationChip.tsx`
- **Props** `VerifiableCitationChipProps`: `{ docId: string; href: string; label?: string; similarity?: number; className?: string }`.
- **Props** `AntiHallucinationGuardProps`: `{ count: number; threshold?: number; className?: string }` (oculta se `count >= threshold` default 3).

## `patterns/AlertList.tsx`
- **Props** `AlertListProps`: `{ alerts: AlertItem[]; filterSeverity?: AlertSeverity|null; filterChannel?: AlertChannel|null; filterStatus?: DeliveryStatus|null; className?: string }`.
- `AlertItem`: `{ id: string; severity: AlertSeverity; title: string; subjectRef: string; channels: AlertChannel[]; deliveryStatus: DeliveryStatus; createdAt: string }`.
- ⚙ `severityIcon` map; usa `DELIVERY_STATUS_COLORS`.

## `patterns/ProblemJsonError.tsx` 🌐
- **Props** `ProblemJsonErrorProps`: `{ error: ProblemJson; inline?: boolean; className?: string }`.
- `ProblemJson` 🌐 (RFC 7807): `{ type: string; title: string; status: number; detail: string; instance?: string; contract_version?: string; retry_after?: number }`.
- ⚙ `statusIcon`/`statusTheme` por status (429/501/503/5xx); mensagens especiais 429 (retry_after) e 501 (PD-06).

## `patterns/JobProgress.tsx`
- **Props** `JobProgressProps`: `{ status: JobStatus; progress: number /*0–100*/; steps: JobStep[]; onDownload?: ()=>void; label?: string; className?: string }`.
- `JobStep`: `{ id: string; label: string; status: 'pending'|'active'|'done'|'failed' }`.
- ⚙ `statusLabel(status)` (queued→'202 Aceito — na fila' etc.).

## `patterns/DegradationBanner.tsx`
- **Props** `DegradationBannerProps`: `{ message?: string; detail?: string; className?: string }` (default "Score parcial — circuit breaker ativo").

## `patterns/RbacGate.tsx` 🔒
- **Props** `RbacGateProps`: `{ role: RbacRole; requires: 'analyst'|'admin'; children: React.ReactNode; fallback?: React.ReactNode; showLockChip?: boolean; className?: string }`.
- **Props** `ViewerBannerProps`: `{ className?: string }`.
- ⚙ `ROLE_RANK { viewer:0, analyst:1, admin:2 }`; `hasAccess(role, required)`.

## `patterns/EmptyState.tsx`
- **Props** `EmptyStateProps`: `{ icon?: React.ReactNode; title: string; description?: string; action?: { label: string; onClick: ()=>void }; demoMode?: boolean; className?: string }`.

## `patterns/EventStatusDot.tsx`
- **Props** `EventStatusDotProps`: `{ status: EventStatus; size?: number; className?: string }`.
- `EventStatus = 'ok'|'running'|'pending'`; exporta `EVENT_STATUS_COLORS`/`EVENT_STATUS_LABELS`.

## `patterns/AgentLiveFeed.tsx` 🌐
- **Props** `AgentLiveFeedProps`: `{ events: AgentEvent[]; revealed?: number; treatment?: FeedTreatment; caseRef?: string; className?: string }`.
- `AgentEvent`: `{ ts: string; evento: string; detalhe: string; status: EventStatus; titulo?: string }` (espelha `EventoAgente` do defensorApi).
- `FeedTreatment = 'terminal'|'timeline'`.
- ⚙ `fmtTime(ts)`; sub-componentes `TerminalFeed`/`TimelineFeed`/`StatusSeal`.

## `patterns/ProtocolStatusCard.tsx` 🔒
- **Props** `ProtocolStatusCardProps`: `{ canal: string; status: ProtocolStatus; numero?: string|null; mensagem: string; modo: ProtocolMode; url?: string|null; enviadoEm?: string; className?: string }`.
- `ProtocolStatus = 'SIMULADO'|'AGUARDA_CREDENCIAIS'|'ENVIADO'|'FALHA'|'CANAL_NAO_SUPORTADO'`.
- `ProtocolMode = 'simulacao'|'real'|'na'`.
- ⚙ `STATUS_META`/`MODE_META` maps; fallback defensivo p/ união desconhecida.

## `patterns/ProvenanceTag.tsx`
- **Props** `ProvenanceTagProps`: `{ value: Provenance; className?: string }`.
- `Provenance = 'ia'|'parcial'|'template'`; `META` map.

## `patterns/StepIndicator.tsx`
- **Props** `StepIndicatorProps`: `{ steps: Step[]; current: number; maxReached: number; onNavigate?: (index:number)=>void; className?: string }`.
- `Step`: `{ id: string; label: string }`; exporta `DEFENSOR_STEPS` (Entrada/Execução/Resultado/Protocolo).

---

# packages/ui/src — hooks e utils

## `hooks/useStaggeredReveal.ts`
- **Entradas** `StaggerOptions`: `{ total: number; interval?: number /*620*/; auto?: boolean /*true*/ }`.
- **Saídas** `{ revealed: number; done: boolean; run: ()=>void }`; respeita `prefers-reduced-motion`.

## `lib/cn.ts`
- ⚙ `cn(...inputs: ClassValue[])` = `twMerge(clsx(inputs))`.

## `index.ts`
- Barrel: reexporta todos primitives/patterns + tipos (`TrustHeaderProps`, `TrustSource`, `MerklePanelProps`, `MerkleProof`, `AlertItem`, `ProblemJson`, `JobStep`, `EventStatus`, `AgentEvent`, `FeedTreatment`, `ProtocolStatus`, `ProtocolMode`, `ProtocolStatusCardProps`, `Provenance`, `Step`, `SegmentedOption`), `useStaggeredReveal`, `cn`, `RISK_COLORS`, `EVENT_STATUS_COLORS`, `EVENT_STATUS_LABELS`, `DEFENSOR_STEPS`, `AntiHallucinationGuard`, `ViewerBanner`.

---

# packages/tokens/src — uniões canônicas e helpers

## `constants.ts` (fonte canônica das uniões)
- `RISK_LEVELS = ['BAIXO','MODERADO','ALTO','CRITICO']` → `type RiskLevel`.
- `FRESHNESS_BANDS = ['fresh','stale','very_stale']` → `type FreshnessBand`.
- `DATA_CLASSES = ['publico','pessoal','sensivel']` → `type DataClass`.
- `DELIVERY_STATUSES = ['pending','claimed','done','failed']` → `type DeliveryStatus`.
- `ALERT_CHANNELS = ['webhook','email','slack','whatsapp']` → `type AlertChannel`.
- `ALERT_SEVERITIES = ['LOW','MEDIUM','HIGH','CRITICAL']` → `type AlertSeverity`.
- `RBAC_ROLES = ['admin','analyst','viewer']` → `type RbacRole`.
- `JOB_STATUSES = ['queued','running','done','failed']` → `type JobStatus`.
- `MODEL_STATUSES = ['heuristica','calibrado']` → `type ModelStatus`.
- **Helpers ⚙**
  - `scoreToriskLevel(score)` → `≥700 BAIXO · ≥500 MODERADO · ≥300 ALTO · else CRITICO`.
  - `lagToFreshnessBand(lagDays)` → `≤7 fresh · ≤90 stale · else very_stale`.
- `PRODUCT_CODES` (const): `{ legalscore:'LS', contabilia:'CT', complianceradar:'CR', taxpredict:'TP', licitawatch:'LW', danobot:'DB', petibot:'PB', concilia:'CC', tribuna:'TC', inicio:'IN', entidade:'EN', alertas:'AL', auditoria:'AU', conformidade:'CF', configuracoes:'CG' }`.

## `colors.ts`
- `colors` (paleta), `ColorToken = keyof typeof colors`.
- Maps semânticos: `RISK_COLORS` (por `RiskLevel`), `FRESHNESS_COLORS` (por `FreshnessBand`), `DATA_CLASS_COLORS`, `DELIVERY_STATUS_COLORS`. (Também exportam `RiskLevel`/`FreshnessBand`/`DataClass`/`DeliveryStatus` como keyof — desambiguados no `index.ts` a favor de `constants.ts`.)

## `typography.ts`
- `fonts` (sans IBM Plex Sans, mono IBM Plex Mono), `fontSizes` (scoreDisplay 52px, settlementDisplay 38px, kpiDisplay 28px…), `fontWeights`, `letterSpacing`.

## `spacing.ts`
- `spacing` (sidebarWidth 238px, topbarHeight 58px, contentMaxWidth 1180px…), `radii`, `shadows` (float, focusRing).

## `tailwind.preset.ts`
- `tailwindPreset: Partial<Config>` — mapeia `colors`/fontes/radii/shadows/maxWidth/width/height para o tema Tailwind.

## `index.ts`
- Reexporta tudo; reexport explícito de `RiskLevel`/`FreshnessBand`/`DataClass`/`DeliveryStatus` de `./constants` (vence TS2308).

---

## Notas de fronteira (resumo)

- Todo o tráfego browser→gateway passa por `lib/api/client.ts` com `credentials: 'include'` (cookie `jwt` httpOnly).
- Auth é **BFF same-origin**: `/api/auth/{login,logout,me}` — o JWT nunca é exposto ao JS; `login` mapeia `email→username`, `tenant→tenant_slug`.
- `demoMode` (default ON via `NEXT_PUBLIC_DEMO_MODE`) troca cada página entre fixtures locais e os DTOs reais do gateway; `ApiErrorBanner` só aparece fora do demo e com `ApiError`.
- Cada DTO de resposta carrega `contract_version` (exceto `LegalScoreResult`/`MeResponse`) — versionamento de contrato com o backend Python.
