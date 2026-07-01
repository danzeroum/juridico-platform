# Checklist: adicionar um novo produto à plataforma

> Objetivo: tornar a criação de produtos **barata e uniforme**. Todo produto herda
> P2 (versionamento, problem+json, rate-limit, JWT) de graça pelo middleware global
> do gateway. Este checklist codifica a fiação SEAMS derivada do router de
> referência `services/gateway/routers/legalscore.py`.

Substitua `foo` pelo nome do produto (minúsculo) em tudo abaixo.

## 1. Contrato SEAMS — `services/shared/contracts/foo.py`
- `FooRequest` / `FooResult`: `BaseModel` com `model_config = {"extra": "forbid"}`.
- `FooEngine(Protocol)` com `@runtime_checkable`: `name`, `healthy() -> bool`, e o
  método de domínio (ex.: `evaluate(req) -> FooResult`).
- Exceções `FooError` / `FooUnavailable`.
- `CONTRACT_VERSION = "foo/v1"`.

## 2. Serviço — `services/foo/`
- `engine/__init__.py`, `engine/engines.py` (impl Python pura, sem I/O no cálculo),
  `engine/factory.py::get_foo_engine()` (retorna a impl default; em falha levanta
  `FooUnavailable`). Espelha `services/scoring/engine/factory.py`.
- Módulos de domínio finos; DB via `services.shared.tenant_db.tenant_transaction`
  (dados por tenant) ou `get_engine()` (dados globais).
- `tests/contract/test_foo_engine_contract.py`: equivalência comportamental do engine.

## 3. Router — `services/gateway/routers/foo.py`
Copie o esqueleto do `legalscore.py`:
- `_get_tenant(request)` para extrair `tenant_id` do state (injetado pelo JWT middleware).
- Span OTel opcional (`_tracer` com try/except ImportError) + `_noop_span`.
- Modelos request/response com `json_schema_extra` (exemplos reais na OpenAPI).
- `501` explícito onde ainda não implementado (nunca 500 silencioso).
- **Bloco Decision Ledger** para qualquer endpoint que produz decisão (ver §5).

## 4. Registro no gateway (2 edições em `services/gateway/main.py`)
- Adicione `foo` ao bloco `from services.gateway.routers import (...)`.
- Adicione `app.include_router(foo.router, prefix="/api/v1/foo")`.
- Nada mais: JWT, rate-limit, security headers e problem+json são globais.

## 5. Decision Ledger (copiar de `legalscore.py` §227-249)
```python
from services.shared.lgpd import hash_user_id
from services.shared.lgpd_crypto import encrypt_for_ledger

pseudonym = hash_user_id(subject_id)                 # se houver titular de dado pessoal
subject_token = encrypt_for_ledger(pseudonym, tenant_id)  # crypto-shredding
entry = _get_ledger(tenant_id).add_entry(
    request_id=request_id, product="foo",
    inputs=inputs_sem_pii, outputs=outputs_resumo,
    sources=[...], subject_token=subject_token,       # subject_token=None se agregado/sem PII
)
from services.shared.audit_log import log_ledger_write
log_ledger_write(request_id=request_id, product="foo", tenant_id=tenant_id,
                 entry_index=entry["entry_index"], has_subject_token=subject_token is not None)
```
`_get_ledger(tenant_id)` devolve `PostgresDecisionLedger(tenant_id)` se `DATABASE_URL`
estiver setado, senão o `DecisionLedger()` em memória (dev/testes).

## 6. Migração — `scripts/migrations/00N_foo_schema.sql` (só se persistir)
- **Dados por tenant** → copie o bloco RLS de `003_fiscal_schema.sql`
  (`ENABLE`+`FORCE ROW LEVEL SECURITY`, policies `USING`/`WITH CHECK` em
  `current_setting('app.tenant_id')::uuid`, `GRANT ... TO app_user`).
- **Dados de referência globais** → só `GRANT`, SEM RLS (como `jurimetria.indicador`).
- Numere após a última migração; o runner `scripts/migrate.py` aplica em ordem.

## 7. Celery (se async) — `services/foo/tasks.py`
- Registre o módulo no `app.conf.include` do `celery_app.py` correspondente
  (ingest / scoring / fiscal).

## 8. Frontend — `frontend/apps/foo/`
- Copie o scaffold de um app irmão sob Turbo; aponte o client para `/api/v1/foo`.

## Gerador
`python scripts/scaffold_product.py foo "Descrição do Foo"` estampa os arquivos de
§1-§3 (contrato, engine+factory, router) e imprime os passos manuais restantes
(§4-§8). Sempre revise o código gerado antes de commitar.
