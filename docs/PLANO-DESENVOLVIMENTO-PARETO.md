# Plano de Desenvolvimento — Análise Pareto (20% esforço → 80% valor)

> Gerado em 2026-07-04 a partir de auditoria completa do repositório
> (suíte de testes executada, 20 serviços mapeados, frontend e infra avaliados).

## 1. Diagnóstico: a ferramenta é funcional?

**Veredito: o código é real e sólido; a orquestração era o elo quebrado.**

| Dimensão | Estado verificado |
|---|---|
| Testes | ✅ 811 passando, 4 pulados, cobertura 97,66% (gate 80%) |
| Backend | ✅ 19 superfícies de API registradas no gateway, com contratos SEAMS, problem+json, idempotência, rate limit, ledger Merkle, LGPD crypto |
| Gateway executável | ❌→✅ **Não subia**: (a) serviço `gateway` ausente de todos os composes; (b) bug de boot — instrumentação Prometheus no `lifespan` derrubava o uvicorn (`RuntimeError: Cannot add middleware after an application has started`). Ambos corrigidos nesta entrega e verificados com servidor real + curl. |
| Frontend | ⚠️ Next.js 14 real e compilável (19 telas, design system, camada de API tipada), mas a experiência default é `demoMode` (mock) e há ~0 testes no app |
| Infra | ⚠️ Compose modular OK, mas `fiscal.yml` estava fora do stack raiz (corrigido); Prometheus já esperava `gateway:8000` |
| DoD (Pendencia.md) | ⚠️ Nenhuma fase com DoD verde: SLA não medido (P0-1), restore não testado (P0-2), E2E Docker pendente (P0-4) |
| Modelos | ⚠️ LegalScore/Forecasting/Second Opinion são heurísticas sem validação (sem ground truth) — retornam `disclaimer` |

## 2. Quick wins implementados nesta entrega (o "20% de esforço")

| # | Item | Esforço | Valor entregue |
|---|---|---|---|
| 1 | Serviço `gateway` no compose (`docker/compose/gateway.yml`) + include no raiz | ~2h | **Crítico** — a plataforma passa a subir ponta a ponta com `make up`; frontend (`gateway:8000`), Prometheus e Traefik passam a resolver |
| 2 | Fix do boot do gateway (Prometheus fora do `lifespan`) | ~1h | **Crítico** — sem isso o container entraria em crashloop; bug invisível aos testes (TestClient não roda lifespan) |
| 3 | `fiscal.yml` incluído no stack raiz (rede corrigida) | ~0.5h | Alto — fiscal-worker/beat passam a subir com `make up` |
| 4 | `GET /api/v1/ready` (readiness real: ping Redis/Postgres) + `make health` corrigido (apontava para rota inexistente `/health`) | ~2h | Alto — probes confiáveis; fim do falso-verde |
| 5 | `/metrics` liberado do JWT (Prometheus não autentica) | ~0.5h | Alto — observabilidade prometida passa a funcionar |
| 6 | Validação por item de CNPJ no batch do LegalScore (422 em vez de 500 no worker) | ~1h | Alto — contrato de erro limpo |
| 7 | Stub score rotulado (`engine="stub"` + disclaimer "SINTÉTICO") | ~1h | **Muito alto (risco jurídico)** — cliente nunca confunde score sintético com real |
| 8 | Job CI `compose-validate` (config + presença dos serviços núcleo) | ~1h | Alto — teria detectado os itens 1 e 3 automaticamente |
| 9 | README honesto: DanoBot marcado como bloqueado (PD-06/501) + 9 módulos analíticos documentados | ~1h | Alto — metade do produto estava invisível; promessa falsa removida |
| 10 | Deps de produção no gateway (`redis`, `sqlalchemy`, `psycopg2`, `celery`) | ~0.5h | Alto — sem elas o container degradaria silenciosamente para stubs |

Total: **~10h de esforço** para destravar a executabilidade da plataforma inteira.

## 3. Backlog Pareto — próximos quick wins (ordenados por valor/esforço)

| Prioridade | Item | Esforço | Valor | Referência |
|---|---|---|---|---|
| P1 | Commitar `frontend/pnpm-lock.yaml` + `--frozen-lockfile` no CI | 0.5d | Builds determinísticos | CI `--no-frozen-lockfile` em 3 jobs |
| P1 | Persistir silver Receita/PGFN em OpenSearch/Neo4j (TODOs) | 1d | Destrava endpoints 501 do LegalScore e popula o grafo | `services/ingest/tasks/receita.py:134`, `pgfn.py:99` |
| P2 | Lint do frontend no CI (`next lint` já existe) | 0.5d | TSX hoje passa sem checagem | `.github/workflows/ci.yml` |
| P2 | `demoMode` desligável por env + smoke test de 2 telas contra gateway | 1-2d | UI real deixa de regredir silenciosamente | `frontend/apps/platform` |
| P2 | Remover código morto: `services/ai-engine/`, `LLMRouter` (`shared/ai/router.py`), `tenant.idempotency_keys`, 4 apps placeholder do frontend | 0.5d | Menos armadilhas de onboarding | vários |
| P3 | Implementar ou desagendar `transparencia.run_hourly_check` (no-op de hora em hora) | 0.5d | Honestidade da fonte "Horária" do README | `services/ingest/tasks/transparencia.py` |
| P3 | Guarda de retenção da outbox de alertas (dedup QT-10) | 0.5d | Evita alerta duplicado pós-poda | `Pendencia.md` QT-10 |
| P3 | OpenAPI examples nos 6 routers analíticos novos | 1d | Paridade de docs | `services/gateway/routers/*` |

## 4. Trabalho estrutural (o "80% de esforço" — planejar, não improvisar)

Estes itens NÃO são quick wins; exigem infra, decisão do dono ou dados externos:

1. **E2E Docker por produto (P0-4)** — agora desbloqueado: com o gateway no compose,
   um job de CI com `docker compose up` + smoke por produto fecha o último checkbox
   técnico do DoD. Esforço: ~1 semana. **Recomendado como próxima épica.**
2. **Load test válido (P0-1)** — semear dados, rodar Locust fora do CI, commitar
   `report.html` com p95. Depende do item 1. Esforço: 2-3 dias.
3. **Backup + restore testado (P0-2/PD-04)** — requer VM limpa. Esforço: 1-2 dias.
4. **Ground truth de desfechos** → validação AUC/Brier de LegalScore/Forecasting/
   Second Opinion (pendencias.md item 4). Depende de dados; sem isso os produtos
   permanecem heurísticas com disclaimer.
5. **Ledger MMR (QT-08)** — O(N) por inserção estoura SLA com N>10k entradas/tenant.
   Gatilho: p95 > 1s no load test. Esforço: 1-2 semanas (quebra formato de prova).
6. **Decisões do dono**: licença ABJ (destrava duração real), parecer DPO/PD-06
   (destrava DanoBot), IdP dedicado (PD-03), KMS real (PD-05), domínio/TLS (PD-02).
7. **10 telas do handoff fiscal** (`docs/design_handoff_plataforma_juridico_contabil/`)
   — especificação visual pronta, implementação pendente no frontend. Esforço: 2-4 semanas.

## 5. Sequência recomendada (roadmap de 4 sprints)

```
Sprint 1 (agora):   Quick wins desta entrega ✅ + lockfile + lint frontend
Sprint 2:           E2E Docker por produto (P0-4) + persistência silver Receita/PGFN
Sprint 3:           Load test SLA (P0-1) + backup/restore (P0-2) → primeiro DoD verde
Sprint 4:           demoMode off + smoke frontend + primeiras telas do handoff fiscal
Contínuo:           decisões do dono (ABJ, DPO, IdP, KMS) — nenhuma bloqueia sprints 1-4
```

**Critério de sucesso do trimestre:** `make up && make health` 100% verde em VM
limpa; ao menos LegalScore com DoD completo (SLA medido + E2E + restore testado).
