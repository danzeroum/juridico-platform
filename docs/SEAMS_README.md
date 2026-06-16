# Fronteiras para migração plug-in (Rust e Elixir)

Estas fronteiras aplicam à camada de **linguagens** a mesma filosofia que o plano
já aplica à infraestrutura ("Compose today, K8s tomorrow"): **desenhe a costura
agora, adie a implementação**. Você fica pronto para a migração sem pagar por ela
antes de a carga justificar.

A regra única: nenhum chamador depende de uma implementação concreta. Todos
dependem de uma **interface** + um **contrato de dados** serializável. A migração
vira troca de configuração, guardada por uma suíte de contrato.

---

## 1. Scorer — fronteira Python ↔ Rust (PyO3)

**Arquivos**
- `services/shared/contracts/scoring.py` — `ScoreRequest`, `ScoreResult`, `ScoreEngine` (Protocol). A única língua falada na fronteira.
- `services/scoring/engine/engines.py` — `PythonScoreEngine` (hoje) e `RustScoreEngine` (adapter sobre o crate PyO3 `rust_scorer`).
- `services/scoring/engine/factory.py` — seleção por config + fallback automático.
- `services/scoring/tests/contract/test_score_engine_contract.py` — a suíte que **toda** implementação tem de passar, incluindo equivalência Python vs Rust.

**Como funciona hoje**

```python
from services.scoring.engine.factory import get_score_engine
engine = get_score_engine(settings.SCORING_BACKEND)  # "python" por enquanto
result = engine.score(request)   # ScoreResult; result.engine == "python"
```

**O dia da migração** (gatilho do plano: MLR > 2s para 1k CNPJs em load test)
1. Escreva o crate `pyo3-scorer` que expõe `score(cnae, features) -> dict`.
2. `maturin develop --release` deixa `rust_scorer` importável.
3. Rode `pytest .../test_score_engine_contract.py` — o teste de **equivalência
   cruzada** exige que Rust e Python devolvam o mesmo score para os mesmos
   inputs. Se divergir, o CI quebra antes de produção.
4. Vire a config: `SCORING_BACKEND=auto` (usa Rust se saudável, senão Python).
   **Nenhum chamador muda.**

**Trilho de segurança**
- O factory envolve o Rust com fallback: erro recuperável (`ScoringUnavailable`)
  cai para Python em runtime.
- Fallback cobre *erro*. Um *segfault* do Rust derruba o processo — para isso
  ficam as outras duas defesas do plano: health check antes de aceitar tráfego
  e supervisor que reinicia o worker. São complementares.

---

## 2. Alertas — fronteira Python ↔ Elixir (Oban)

**Arquivos**
- `services/shared/contracts/alerts.py` — `AlertEnvelope` (versionado), `AlertPublisher` (Protocol).
- `schemas/alert.v1.json` — o contrato **neutro de linguagem**, validado pelos dois lados.
- `services/shared/alerts/publishers.py` — `OutboxAlertPublisher` (hoje) e `HttpAlertPublisher` (depois).
- `services/shared/alerts/tests/test_alert_contract.py` — garante que o envelope Python valida contra o schema que o Elixir vai usar.

**A costura é a tabela, não o código.** O padrão é *transactional outbox*: o
Python grava o alerta na tabela Postgres `alerts_outbox` **dentro da transação
de negócio** (o alerta só existe se a transação que o gerou commitou). A entrega
é um processo separado que faz polling dessa tabela.

```
HOJE:    aplicação → publish() → alerts_outbox (Postgres) → worker Celery → canais
DEPOIS:  aplicação → publish() → alerts_outbox (Postgres) → Oban (Elixir)   → canais
                                  └──────── mesma tabela ─────────┘
```

**O dia da migração** (gatilho do plano: cliente exige SLA de 99% de entrega)
1. Suba o app Elixir com Oban configurado para ler a fila a partir de
   `alerts_outbox` (Oban é PostgreSQL-nativo — é literalmente a mesma tabela).
2. O Oban valida cada linha contra `alert.v1.json` (mesmo schema do Python).
3. Desligue o worker Celery de entrega.
4. **`publish()` da aplicação não muda em nada.** Idempotência (`alert_id`) e
   cooldown de 24h (`dedup_key`) já estão no banco, então não há entrega dupla
   durante a transição.

A alternativa `HttpAlertPublisher` (POST para o Elixir, header
`X-Contract-Version`) serve quando produtor e consumidor já são serviços
separados; para a *transição*, o outbox é mais simples e transacional.

---

## 3. O que permanece Python (não tem costura porque não migra)

Inteligência: IA/ML, RAG consensual, modelo Bayesiano (PyMC), orquestração,
regras de negócio dos produtos. Não há ganho mensurável em reescrever isso em
Rust/Elixir — então não se cria fronteira para essa migração. Escala dessa
camada é horizontal (mais réplicas dos containers FastAPI), exatamente o caminho
de escala que o plano já descreve.

---

## Princípio que mantém isso barato

| Decisão | Por quê |
|---|---|
| Dados na fronteira são modelos serializáveis (Pydantic / JSON Schema) | A implementação pode ser em qualquer linguagem; a fronteira não sabe nem se importa. |
| `extra="forbid"` + `additionalProperties:false` | Os dois lados recusam campos não previstos → nada de drift silencioso de schema. |
| Contrato versionado (`scoring/v1`, `alerts/v1`) | Mudança incompatível cria `v2`; evolução sem breaking change. |
| Suíte de contrato roda contra todas as implementações | A troca só é permitida se o comportamento for idêntico. É isso que torna a migração um *plug-in* e não uma reescrita. |
