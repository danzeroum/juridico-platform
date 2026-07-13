# 10 — Infra / Config / Scripts (compose, SQL schema, CI, env)

> Catálogo EXAUSTIVO, linha a linha, de todo dado/configuração que trafega pela camada de
> infraestrutura do repositório `juridico-platform`: Docker Compose, config de serviços,
> schema SQL (DDL + RLS + seeds), scripts Python, CI (GitHub Actions), `.env.example`,
> Makefile, pyproject e infra auxiliar.

**Legenda**
- ⚙ = **Intermediário** — dado de build-time ou init one-shot (não persiste como serviço).
- 🔒 = **Secret / senha / token** — credencial sensível.
- 🌐 = **Fronteira** — injeção de secret, wiring de rede, ponto de cruzamento entre confiança.
- Classificação por arquivo: **Entradas** (env vars, secrets, arquivos montados) / **Intermediário** (⚙) / **Saídas** (tabelas/roles/buckets criados, portas expostas, métricas) / **Fronteiras** (🌐).
- Nomes EXATOS e case-sensitive.

---

## Índice de arquivos

| # | Arquivo | Papel |
|---|---------|-------|
| 1 | `docker-compose.yml` | Agregador (include) + rede + volumes globais |
| 2 | `docker/compose/base.yml` | Stack de dados: postgres, pgbouncer, migrate, neo4j, opensearch, redis, minio, minio-init, chromadb |
| 3 | `docker/compose/monitoring.yml` | prometheus, grafana, loki, promtail, alertmanager, flower |
| 4 | `docker/compose/ingest.yml` | celery-worker, celery-beat |
| 5 | `docker/compose/fiscal.yml` | fiscal-worker, fiscal-beat |
| 6 | `docker/compose/ollama.yml` | ollama, ollama-init |
| 7 | `docker/compose/traefik.yml` | traefik (reverse proxy + TLS) |
| 8 | `docker/compose/frontend.yml` | platform (Next.js) |
| 9 | `docker/products/legalscore/compose.override.yml` | legalscore-api |
| 10 | `docker/config/prometheus.yml` | scrape targets |
| 11 | `docker/config/pgbouncer-init.sh` | gera userlist.txt + pgbouncer.ini |
| 12 | `docker/config/promtail.yml` | coleta de logs |
| 13 | `docker/config/neo4j.conf` | tuning Neo4j |
| 14 | `docker/config/alertmanager.yml` | rotas de alerta (Slack/email) |
| 15 | `docker/config/loki.yml` | armazenamento de logs |
| 16 | `scripts/bootstrap-db.sql` | schema inicial + RLS + role app_user + seeds |
| 17 | `scripts/migrations/001..004*.sql` | migrações incrementais |
| 18 | `scripts/migrate.py` | runner idempotente de migrações |
| 19 | `scripts/seed_fiscal.py` | seed ICMS interestadual/interno + categorias |
| 20 | `scripts/validate_schema.py` | valida schemas/alert.v1.json |
| 21 | `scripts/check_docker_security.py` | gate: portas de DB + MinIO anônimo |
| 22 | `scripts/scaffold_product.py` | gerador de scaffold SEAMS |
| 23 | `.env.example` | todas as variáveis de ambiente |
| 24 | `.github/workflows/ci.yml` | pipeline CI (7 jobs) |
| 25 | `Makefile` | alvos operacionais |
| 26 | `pyproject.toml` | pytest/coverage/ruff |
| 27 | `.gitignore` | exclusões |
| 28 | Dockerfiles (services/*, frontend, products) | imagens de build |
| 29 | `infra/scripts/*`, `infra/terraform/*`, `examples/*`, `data/*` | placeholders |

---

## 1 — `docker-compose.yml` (agregador)

Combina os arquivos de compose via `include:` e define a rede/volumes globais.

- **Entradas:** nenhuma env direta. `include:` → `docker/compose/base.yml`, `monitoring.yml`, `ingest.yml`, `ollama.yml`, `traefik.yml`, `frontend.yml`. (⚠ NÃO inclui `fiscal.yml` — o worker fiscal é subido à parte via `-f docker/compose/fiscal.yml`, que usa a rede `juridico-net` como `external: true`.)
- **Intermediário (⚙):** —
- **Saídas:**
  - Rede `juridico-net` — driver `bridge`, IPAM subnet `172.20.0.0/16`.
  - Volumes nomeados: `pg_data`, `neo4j_data`, `neo4j_logs`, `opensearch_data`, `redis_data`, `minio_data`, `chromadb_data`, `traefik_acme`, `prometheus_data`, `grafana_data`, `loki_data`, `ollama_data`.
- **Fronteiras (🌐):** define a subnet privada única onde todos os serviços se enxergam por nome DNS de container.

---

## 2 — `docker/compose/base.yml` (stack de dados)

> Regra de segurança do arquivo: **nenhuma porta de banco exposta no host**. Apenas Traefik expõe 80/443. Acesso admin via túnel SSH (`ssh -L 5432:postgres:5432 user@host`).

### 2.1 service `postgres` (postgres:16-alpine)

- **Entradas (env):**
  | var | valor | dado |
  |-----|-------|------|
  | `POSTGRES_USER` | `${POSTGRES_USER}` | usuário admin/owner do banco |
  | `POSTGRES_PASSWORD` 🔒 | `${POSTGRES_PASSWORD}` | senha do owner |
  | `POSTGRES_DB` | `${POSTGRES_DB}` | nome do banco (`juridico_platform`) |
- **Volumes:** `pg_data:/var/lib/postgresql/data`; `./scripts/bootstrap-db.sql:/docker-entrypoint-initdb.d/01-init.sql` (⚙ init one-shot no primeiro boot).
- **Healthcheck:** `pg_isready -U ${POSTGRES_USER}` (interval 10s, timeout 5s, retries 5).
- **Saídas:** SEM `ports` no host. Escuta interna `5432`. Deploy limits: 4G / 2 CPU.
- **Fronteiras (🌐):** único ponto de escrita relacional; bootstrap SQL roda como superuser aqui.

### 2.2 service `pgbouncer` (edoburu/pgbouncer:1.20)

- **Entrypoint:** `["/bin/sh","/docker-config/pgbouncer-init.sh"]` (⚙ gera userlist + ini em runtime).
- **Entradas (env):**
  | var | valor | dado |
  |-----|-------|------|
  | `POSTGRES_USER` | `${POSTGRES_USER}` | 1º usuário do userlist |
  | `POSTGRES_PASSWORD` 🔒 | `${POSTGRES_PASSWORD}` | hash MD5 no userlist |
  | `APP_USER_PASSWORD` 🔒 | `${APP_USER_PASSWORD}` | hash MD5 de `app_user` no userlist |
  | `POSTGRES_DB` | `${POSTGRES_DB}` | database roteado |
  | `PGBOUNCER_MAX_CLIENT_CONN` | `1000` | max clientes |
  | `PGBOUNCER_DEFAULT_POOL_SIZE` | `20` | pool size |
- **Volumes:** `./docker/config/pgbouncer-init.sh:/docker-config/pgbouncer-init.sh`.
- **depends_on:** `postgres` (service_healthy).
- **Healthcheck:** `pg_isready -h localhost -p 6432`.
- **Saídas:** SEM ports no host. Escuta interna `6432`. `pool_mode=transaction`.
- **Fronteiras (🌐):** ÚNICO caminho de conexão da aplicação ao Postgres; permite conectar como `app_user` (NOSUPERUSER) mantendo RLS ativa. Gera hash MD5 sem expor senha em texto claro.

### 2.3 service `migrate` (python:3.12-slim, one-shot ⚙)

- **restart:** `"no"` (roda uma vez).
- **Entradas (env):** `MIGRATIONS_DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}` 🔒 — conexão DIRETA ao Postgres (fora do PgBouncer) como OWNER, necessária para DDL.
- **Volumes:** `./scripts:/app/scripts:ro`.
- **depends_on:** `postgres` (service_healthy).
- **Intermediário (⚙):** `pip install "sqlalchemy>=2.0,<3" psycopg2-binary && python scripts/migrate.py`.
- **Fronteiras (🌐):** serviços de app dependem de `migrate: service_completed_successfully` antes de subir.

### 2.4 service `neo4j` (neo4j:5-community)

- **Entradas (env):** `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}` 🔒; `NEO4J_server_mode=SINGLE`.
- **Volumes:** `neo4j_data:/data`, `neo4j_logs:/logs`, `./docker/config/neo4j.conf:/etc/neo4j/neo4j.conf`.
- **Healthcheck:** `cypher-shell -u neo4j -p ${NEO4J_PASSWORD} 'RETURN 1'`.
- **Saídas:** SEM ports no host. Interno bolt `7687`, http `7474`. Limits: 8G / 4 CPU.

### 2.5 service `opensearch` (opensearchproject/opensearch:2.12.0)

- **Entradas (env):** `discovery.type=single-node`; `OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g`; `DISABLE_SECURITY_PLUGIN=true`.
- **Volumes:** `opensearch_data:/usr/share/opensearch/data`.
- **Healthcheck:** `curl -sf http://localhost:9200/_cluster/health`.
- **Saídas:** SEM ports. Interno `9200`. Limits: 4G / 2 CPU.

### 2.6 service `redis` (redis:7-alpine)

- **Command:** `redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru --appendonly yes --requirepass ${REDIS_PASSWORD}` 🔒.
- **Volumes:** `redis_data:/data`.
- **Healthcheck:** `redis-cli -a ${REDIS_PASSWORD} ping` 🔒.
- **Saídas:** SEM ports. Interno `6379`. Limits: 2G / 1 CPU.

### 2.7 service `minio` (minio/minio:latest)

- **Command:** `server /data --console-address ":9001"`.
- **Entradas (env):** `MINIO_ROOT_USER=${MINIO_USER}` 🔒; `MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}` 🔒.
- **Volumes:** `minio_data:/data`.
- **Healthcheck:** `mc ready local || curl -sf http://localhost:9000/minio/health/live`.
- **Saídas:** SEM ports. Interno API `9000`, console `9001`.

### 2.8 service `minio-init` (minio/mc:latest, one-shot ⚙)

- **depends_on:** `minio` (service_healthy).
- **Intermediário (⚙) — entrypoint:** `mc alias set local http://minio:9000 ${MINIO_USER} ${MINIO_PASSWORD}` 🔒 e cria buckets:
  - `mc mb local/bronze`, `local/silver`, `local/gold`, `local/documents`, `local/backups` (`--ignore-existing`).
  - `mc anonymous set none` em TODOS os 5 buckets (privados).
  - `mc version enable` em `bronze`, `silver`, `gold` (apenas 3 — versionamento).
- **Saídas:** 5 buckets MinIO criados PRIVADOS: **bronze, silver, gold, documents, backups**.
- **Fronteiras (🌐):** injeta credenciais root do MinIO para configurar o data lake.

### 2.9 service `chromadb` (chromadb/chroma:latest)

- **Volumes:** `chromadb_data:/chroma/chroma`.
- **Healthcheck:** `curl -sf http://localhost:8000/api/v1/heartbeat`.
- **Saídas:** SEM ports. Interno `8000`. Limits: 2G / 1 CPU.

---

## 3 — `docker/compose/monitoring.yml`

### 3.1 `prometheus` (prom/prometheus:v2.50.0)
- **Volumes:** `./docker/config/prometheus.yml:/etc/prometheus/prometheus.yml`; `prometheus_data:/prometheus`.
- **Command:** `--config.file`, `--storage.tsdb.retention.time=30d`, `--web.enable-lifecycle`.
- **Saídas:** porta host **`9090:9090`**.

### 3.2 `grafana` (grafana/grafana:10.3.0)
- **Entradas (env):** `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}` 🔒; `GF_USERS_ALLOW_SIGN_UP=false`; `GF_FEATURE_TOGGLES_ENABLE=publicDashboards`.
- **Volumes:** `grafana_data:/var/lib/grafana`; `./docker/config/grafana/provisioning:/etc/grafana/provisioning` (⚠ diretório de provisioning NÃO existe no repo — montagem vazia).
- **depends_on:** `prometheus`. **Saídas:** porta host **`3001:3000`**.

### 3.3 `loki` (grafana/loki:2.9.0)
- **Volumes:** `loki_data:/loki`; `./docker/config/loki.yml:/etc/loki/local-config.yaml`.
- **Saídas:** porta host **`3100:3100`**.

### 3.4 `promtail` (grafana/promtail:2.9.0)
- **Volumes:** `/var/log:/var/log:ro`; `/var/lib/docker/containers:/var/lib/docker/containers:ro`; `./docker/config/promtail.yml:/etc/promtail/config.yml`.
- **depends_on:** `loki`. Sem ports host.

### 3.5 `alertmanager` (prom/alertmanager:v0.27.0)
- **Volumes:** `./docker/config/alertmanager.yml:/etc/alertmanager/alertmanager.yml`.
- **Saídas:** porta host **`9093:9093`**.

### 3.6 `flower` (mher/flower:2.0)
- **Entradas (env):** `CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0` 🔒; `FLOWER_PORT=5555`.
- **Saídas:** porta host **`5555:5555`**. Limits: 128M.

---

## 4 — `docker/compose/ingest.yml`

### 4.1 `celery-worker` (build `services/ingest/Dockerfile`)
- **Command:** `celery -A services.ingest.celery_app worker --loglevel=info -Q daily,weekly,monthly,hourly,batch --concurrency=4`.
- **Entradas (env):**
  | var | valor | dado |
  |-----|-------|------|
  | `DATABASE_URL` 🔒 | `postgresql://app_user:${APP_USER_PASSWORD}@pgbouncer:6432/${POSTGRES_DB}` | conexão app via PgBouncer como app_user |
  | `REDIS_URL` 🔒 | `redis://:${REDIS_PASSWORD}@redis:6379/0` | broker/backend Celery |
  | `NEO4J_URI` | `bolt://neo4j:7687` | grafo |
  | `NEO4J_USER` | `neo4j` | |
  | `NEO4J_PASSWORD` 🔒 | `${NEO4J_PASSWORD}` | |
  | `OPENSEARCH_URL` | `http://opensearch:9200` | busca |
  | `CHROMA_URL` | `http://chromadb:8000` | vetorial |
  | `MINIO_URL` | `http://minio:9000` | data lake |
  | `MINIO_USER` 🔒 | `${MINIO_USER}` | |
  | `MINIO_PASSWORD` 🔒 | `${MINIO_PASSWORD}` | |
  | `DATAJUD_API_URL` | `${DATAJUD_API_URL}` | API pública CNJ |
  | `DATAJUD_TOKEN` 🔒 | `${DATAJUD_TOKEN}` | token DATAJUD |
- **depends_on:** `pgbouncer` (healthy), `redis` (healthy), `neo4j` (healthy). Limits: 4G / 2 CPU.

### 4.2 `celery-beat` (build `services/ingest/Dockerfile`)
- **Command:** `celery -A services.ingest.celery_app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler`.
- **Entradas (env):** `DATABASE_URL` 🔒, `REDIS_URL` 🔒 (mesmos valores acima).
- **depends_on:** `celery-worker` (service_started). Limits: 512M / 0.5 CPU.

---

## 5 — `docker/compose/fiscal.yml`

> Rede `juridico-net` como `external: true` (subido separadamente). Escala horizontal via `--scale fiscal-worker=N`.

### 5.1 `fiscal-worker` (build `services/fiscal/Dockerfile`)
- **Command:** `celery -A services.fiscal.celery_app worker --loglevel=info -Q fiscal,batch,fiscal_ingest --concurrency=4`.
- **Entradas (env):** `DATABASE_URL` 🔒 (`app_user@pgbouncer:6432`), `REDIS_URL` 🔒, `MINIO_URL=http://minio:9000`, `MINIO_USER` 🔒, `MINIO_PASSWORD` 🔒, `OLLAMA_URL=http://ollama:11434`.
- **depends_on:** `pgbouncer` (healthy), `redis` (healthy). Limits: 4G / 2 CPU.

### 5.2 `fiscal-beat` (build `services/fiscal/Dockerfile`)
- **Command:** `celery -A services.fiscal.celery_app beat --loglevel=info` (PersistentScheduler em arquivo, não usa DB).
- **Entradas (env):** apenas `REDIS_URL` 🔒.
- **depends_on:** `fiscal-worker` (service_started). Limits: 512M / 0.5 CPU.

---

## 6 — `docker/compose/ollama.yml`

### 6.1 `ollama` (ollama/ollama:latest)
- **Volumes:** `ollama_data:/root/.ollama`. **Saídas:** porta host **`11434:11434`**. Limits: 8G / 2 CPU.

### 6.2 `ollama-init` (one-shot ⚙)
- **depends_on:** `ollama`. **Env:** `OLLAMA_HOST=http://ollama:11434`.
- **Intermediário (⚙):** `sleep 10; ollama pull llama3:8b; ollama pull bge-m3` — baixa modelos LLM (`llama3:8b` classificação/NER) e embeddings (`bge-m3`).

---

## 7 — `docker/compose/traefik.yml`

- **Command (config estática):**
  - `--api=true` (SEM `--api.insecure`), `--api.dashboard=true`.
  - `--providers.docker=true`, `--providers.docker.exposedbydefault=false`.
  - entrypoints: `web=:80`, `websecure=:443`, `traefik=:8080` (dashboard interno).
  - redirect `web → websecure` (http→https).
  - `--certificatesresolvers.letsencrypt.acme.tlschallenge=true`.
  - `--certificatesresolvers.letsencrypt.acme.email=${LETSENCRYPT_EMAIL}`.
  - `--certificatesresolvers.letsencrypt.acme.storage=/data/acme/acme.json`.
  - `--accesslog=true`, `--accesslog.format=json`.
- **Entradas (env):** `LETSENCRYPT_EMAIL` (email ACME/Let's Encrypt).
- **Volumes:** `/var/run/docker.sock:/var/run/docker.sock:ro` 🌐 (descoberta de serviços); `traefik_acme:/data/acme` (certs 🔒).
- **Saídas:** portas host **`80:80`**, **`443:443`**, e **`127.0.0.1:8080:8080`** (dashboard só via localhost/túnel SSH). Limits: 256M / 0.5 CPU.
- **Fronteiras (🌐):** único serviço com portas públicas; termina TLS; roteia por labels dos containers.

---

## 8 — `docker/compose/frontend.yml`

### `platform` (build `frontend/apps/platform/Dockerfile`, Next.js 14)
- **Entradas (env):** `NODE_ENV=production`; `NEXT_PUBLIC_GATEWAY_URL=http://gateway:8000` (lido server-side em `/api/auth/login`).
- **Healthcheck:** `wget -qO- http://localhost:3000/` (start_period 40s).
- **Labels Traefik (🌐 roteamento):**
  - `traefik.enable=true`
  - `traefik.http.routers.platform.rule=Host(\`${DOMAIN}\`)`
  - `traefik.http.routers.platform.entrypoints=websecure`
  - `traefik.http.routers.platform.tls.certresolver=letsencrypt`
  - `traefik.http.services.platform.loadbalancer.server.port=3000`
  - `traefik.http.routers.platform-http.rule=Host(\`${DOMAIN}\`)`
  - `traefik.http.routers.platform-http.entrypoints=web`
  - `traefik.http.routers.platform-http.middlewares=redirect-to-https`
- **Saídas:** sem ports host (exposta só via Traefik em `https://${DOMAIN}`). Limits: 512M / 1 CPU.

---

## 9 — `docker/products/legalscore/compose.override.yml`

### `legalscore-api` (build `services/gateway/Dockerfile`)
- **depends_on:** `migrate` (**service_completed_successfully**) — sobe só após migrações.
- **Entradas (env):** `DATABASE_URL=postgresql://app_user:${APP_USER_PASSWORD}@pgbouncer:6432/${POSTGRES_DB}` 🔒 (app_user via PgBouncer, RLS ativa).
- **Saídas:** container `legalscore-api`, alvo do scrape Prometheus `legalscore-api:8000`.

`docker/products/legalscore/Dockerfile` (⚙ placeholder): `FROM python:3.12-slim`, `CMD print('placeholder')`.
Outros produtos (`compliance-radar`, `contabilia`, `taxpredict`) têm apenas `.gitkeep`.

---

## 10 — `docker/config/prometheus.yml`

- **Entradas (montado):** `/etc/prometheus/prometheus.yml`.
- **Global:** `scrape_interval: 15s`, `evaluation_interval: 15s`. external_labels: `environment=production`, `platform=juridico-platform`.
- **rule_files:** `/etc/prometheus/alerts/*.yml` (⚠ diretório não presente no repo).
- **alerting:** alertmanager em `alertmanager:9093`.
- **Saídas (scrape targets):**
  | job_name | target | metrics_path |
  |----------|--------|--------------|
  | `gateway` | `gateway:8000` | `/metrics` |
  | `legalscore-api` | `legalscore-api:8000` | (default `/metrics`) |
  | `postgres` | `postgres-exporter:9187` | default |
  | `redis` | `redis-exporter:9121` | default |
  | `celery` | `flower:5555` | `/metrics` |
  | `node` | `node-exporter:9100` | default |
  > ⚠ `postgres-exporter`, `redis-exporter`, `node-exporter` não estão definidos em nenhum compose — targets órfãos.

---

## 11 — `docker/config/pgbouncer-init.sh` (⚙ init runtime)

- **Entradas (env, com defaults):** `POSTGRES_USER` (def `juridico`), `POSTGRES_PASSWORD` 🔒, `APP_USER_PASSWORD` 🔒, `POSTGRES_DB` (def `juridico_platform`), `PGBOUNCER_MAX_CLIENT_CONN` (def 1000), `PGBOUNCER_DEFAULT_POOL_SIZE` (def 20).
- **Intermediário (⚙):**
  - `md5_pgpass()`: gera `"md5" + md5(senha+usuário)` em hex.
  - Escreve `/etc/pgbouncer/userlist.txt` com 2 usuários: `${POSTGRES_USER}` e `app_user` (hashes MD5).
  - Gera `/etc/pgbouncer/pgbouncer.ini`:
    - `[databases]`: `${POSTGRES_DB} = host=postgres port=5432 dbname=${POSTGRES_DB}`.
    - `[pgbouncer]`: `listen_addr=0.0.0.0`, `listen_port=6432`, `auth_type=md5`, `auth_file=/etc/pgbouncer/userlist.txt`, `pool_mode=transaction`, `max_client_conn=${...}`, `default_pool_size=${...}`, `server_reset_query=DISCARD ALL`, `ignore_startup_parameters=extra_float_digits`.
  - `exec pgbouncer /etc/pgbouncer/pgbouncer.ini`.
- **Fronteiras (🌐):** materializa credenciais de 2 roles em hash MD5 sem texto claro; habilita `app_user` a passar pelo pool preservando RLS.

---

## 12 — `docker/config/promtail.yml`

- **Entradas:** montado em `/etc/promtail/config.yml`. Fonte: `/var/lib/docker/containers/*/*log`.
- **server:** http `9080`, grpc `0`. **positions:** `/tmp/positions.yaml`.
- **clients:** push para `http://loki:3100/loki/api/v1/push`.
- **Intermediário (⚙):** pipeline_stages — parse JSON (`log`,`stream`,`attrs`), extrai `attrs.tag`, regex extrai `container_name`, timestamp RFC3339Nano, labels `stream`+`container_name`.
- **Saídas:** logs de containers enviados ao Loki com labels.

---

## 13 — `docker/config/neo4j.conf`

- **Intermediário (⚙, tuning):** `server.memory.heap.initial_size=2G`, `heap.max_size=4G`, `pagecache.size=2G`; `dbms.tx_log.rotation.retention_policy=100M size, 7 days`; `dbms.security.procedures.unrestricted=apoc.*` e `allowlist=apoc.*`; `bolt.advertised_address=neo4j:7687`, `http.advertised_address=neo4j:7474`.

---

## 14 — `docker/config/alertmanager.yml`

- **Entradas (env interpoladas):** `SLACK_WEBHOOK_URL` 🔒 (`slack_api_url`); `ALERT_EMAIL` (destino email crítico).
- **Global:** `resolve_timeout: 5m`.
- **route:** group_by `[alertname, severity]`, group_wait 30s, group_interval 5m, repeat_interval 12h, receiver `default`; sub-rota `severity=critical` → `critical-alerts`.
- **Saídas (receivers):**
  - `default`: Slack `#juridico-platform-alerts`.
  - `critical-alerts`: Slack `#juridico-platform-critical` + email para `${ALERT_EMAIL}` (`send_resolved: true`).
- **Fronteiras (🌐):** exfiltra alertas para Slack/email externos.

---

## 15 — `docker/config/loki.yml`

- **Intermediário (⚙):** `auth_enabled: false`; server http `3100`; ingester ring inmemory (replication_factor 1); schema `boltdb-shipper`/`filesystem` (schema v11, index period 24h, from 2024-01-01); storage `/loki/...`; `reject_old_samples_max_age: 168h`; `table_manager.retention_period: 720h` (30 dias).
- **Saídas:** armazenamento local de logs, retenção 30 dias.

---

## 16 — `scripts/bootstrap-db.sql` (schema inicial + RLS + seeds)

> Executado como **superuser** (`POSTGRES_USER`) no primeiro boot do Postgres via `/docker-entrypoint-initdb.d/01-init.sql`. Também roda no CI antes dos testes de integração.

### Extensões criadas
`uuid-ossp`, `pgcrypto`, `pg_trgm`.

### Schemas criados
`tenant`, `ledger`, `ingest` (+ objetos em `public`).

### Tabelas (ver tabela consolidada na seção "Schema DB completo" abaixo)
`tenant.tenants`, `tenant.users`, `tenant.idempotency_keys`, `ledger.entries`, `ledger.anchors`, `ingest.runs`, `public.alerts_outbox`, `public.tenant_isolation_probe`.

### Triggers / funções
- `ledger.prevent_modification()` (plpgsql) → RAISE EXCEPTION. Trigger `ledger_immutable` BEFORE UPDATE OR DELETE ON `ledger.entries` (append-only).

### RLS (Row-Level Security) — `current_setting('app.tenant_id')::uuid` (falha-fechado, sem missing_ok)
| Tabela | ENABLE | FORCE | Policies |
|--------|--------|-------|----------|
| `ledger.entries` | ✓ | ✓ | `ledger_tenant_isolation` (USING), `ledger_tenant_select` (SELECT), `ledger_tenant_insert` (INSERT WITH CHECK) |
| `ledger.anchors` | ✓ | ✓ | `ledger_anchors_tenant_isolation` (USING), `ledger_anchors_tenant_insert` (INSERT) |
| `tenant.idempotency_keys` | ✓ | ✓ | `idempotency_tenant_isolation` (USING) |
| `public.tenant_isolation_probe` | ✓ | ✓ | `probe_isolation` (USING + WITH CHECK) — tabela de sonda p/ testes CI |

`ALTER TABLE ledger.entries OWNER TO CURRENT_USER;`

### Role de aplicação (🔒)
```
CREATE ROLE app_user NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT LOGIN
  PASSWORD 'change_in_production';   -- 🔒 substituir por Docker Secret em prod
```
**Grants a `app_user`:**
- `USAGE` nos schemas `ledger`, `tenant`, `ingest`, `public`.
- `ledger.entries`: `SELECT, INSERT` (UPDATE/DELETE bloqueados por trigger).
- `ledger.anchors`: `SELECT, INSERT` + `USAGE ON SEQUENCE ledger.anchors_id_seq`.
- `tenant.tenants`: `SELECT`. `tenant.users`: `SELECT`. `tenant.idempotency_keys`: `SELECT, INSERT, UPDATE, DELETE`.
- `public.alerts_outbox`: `SELECT, INSERT, UPDATE`.
- `public.tenant_isolation_probe`: `SELECT, INSERT, UPDATE, DELETE`.

### Seed (⚙ dado inicial)
- `tenant.tenants`: **id `00000000-0000-0000-0000-000000000001`**, slug `dev-tenant`, name `Tenant de Desenvolvimento`, plan `enterprise` (`ON CONFLICT (slug) DO NOTHING`).

- **Fronteiras (🌐):** define a separação de privilégio superuser vs `app_user` que sustenta toda a garantia de RLS/multi-tenancy.

---

## 17 — `scripts/migrations/*.sql`

### 001 `001_ledger_entry_index_unique_and_anchors_rls.sql`
- Adiciona constraint `ledger_entries_tenant_idx_unique UNIQUE (tenant_id, entry_index)` (se ausente).
- `ALTER TABLE ledger.anchors ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant.tenants(id)`.
- Habilita RLS FORCE em `ledger.anchors` + policies `ledger_anchors_tenant_isolation`/`_insert`.
- Grants: `SELECT, INSERT ON ledger.anchors`, `USAGE ON SEQUENCE ledger.anchors_id_seq` a `app_user`.

### 002 `002_users_password_and_auth.sql`
- `ALTER TABLE tenant.users ADD COLUMN IF NOT EXISTS password_hash TEXT`.
- `ALTER TABLE tenant.users ADD COLUMN IF NOT EXISTS name VARCHAR(255)`.
- **Seed DEV (🔒 credencial conhecida):** insere em `tenant.users` para tenant `dev-tenant`:
  - email `admin@dev.com`, name `Admin de Desenvolvimento`, role `admin`, active TRUE.
  - **senha `dev12345`** (hash `pbkdf2_sha256$600000$g9gLadCiKMaLDkcSM5KIbg==$9d2VPknk/IesKc65jhIbV9KIvkm+9zyFd/YICkX9CXM=`). `ON CONFLICT (tenant_id, email) DO NOTHING`.

### 003 `003_fiscal_schema.sql` — schema `fiscal`
- `CREATE SCHEMA fiscal` + `GRANT USAGE ... app_user`; extensão `btree_gist`.
- Tabelas de REFERÊNCIA (globais, SEM RLS): `fiscal.ncm`, `fiscal.ncm_migracao`, `fiscal.ipi_aliquota`, `fiscal.icms_interestadual`, `fiscal.icms_interno`, `fiscal.categoria`, `fiscal.ncm_categoria`, `fiscal.doc_hash` — GRANT `SELECT, INSERT, UPDATE, DELETE`.
- Tabelas POR TENANT (RLS FORCE): `fiscal.triage_job`, `fiscal.triage_item` — policies `triage_job_tenant_isolation/_insert`, `triage_item_tenant_isolation/_insert`; GRANT `SELECT, INSERT, UPDATE`.
- Constraints EXCLUDE (não-sobreposição de vigência via GiST): `no_overlap_ncm`, `no_overlap_ipi`, `no_overlap_icms_inter`, `no_overlap_icms_interno`; UNIQUE `uq_ipi_ncm_excecao` (NULLS NOT DISTINCT), `uq_ncm_categoria`, `uq_doc_hash`.

### 004 `004_jurimetria_schema.sql` — schema `jurimetria`
- `CREATE SCHEMA jurimetria` + `GRANT USAGE`. Todas REFERÊNCIA (SEM RLS).
- Tabelas: `jurimetria.tpu_classe`, `jurimetria.tpu_assunto`, `jurimetria.indicador`, `jurimetria.abj_indicador_raw` — GRANT `SELECT, INSERT, UPDATE, DELETE`.
- Índice único por expressão `uq_abj_indicador (tribunal, COALESCE(classe_cnj,''), COALESCE(assunto_cnj,''), periodo)`.

---

## 18 — `scripts/migrate.py` (runner idempotente)

- **Entradas (env):** `MIGRATIONS_DATABASE_URL` **OU** `DATABASE_URL` 🔒 (deve ser owner/admin para DDL). Arg CLI `--status`.
- **Intermediário (⚙):**
  - `discover()`: lê `scripts/migrations/*.sql` ordenados; calcula `checksum = sha256(conteúdo)`.
  - `_ensure_control_table()`: cria tabela de controle (abaixo) + `GRANT SELECT ... app_user`.
  - Aplica pendentes cada uma em sua própria transação; registra em `schema_migrations`.
  - AVISO (não bloqueia) se checksum de migração aplicada mudou.
- **Saídas — tabela criada `public.schema_migrations`:**
  | coluna | tipo | chave |
  |--------|------|-------|
  | `version` | TEXT | PK |
  | `checksum` | TEXT | NOT NULL |
  | `applied_at` | TIMESTAMPTZ | DEFAULT now() |
- GRANT `SELECT ON public.schema_migrations TO app_user` (se role existir).

---

## 19 — `scripts/seed_fiscal.py`

- **Entradas (env):** `MIGRATIONS_DATABASE_URL` ou `DATABASE_URL` 🔒. Importa `UF` e `aliquota_interestadual` de `services.shared.contracts.fiscal`.
- **Intermediário (⚙):** idempotente por `source` — `DELETE ... WHERE source = :s` antes de reinserir.
- **Saídas (linhas inseridas):**
  - `fiscal.icms_interestadual` (source `SENADO-SEED`): matriz 27×27 origem≠destino = **702 linhas**, `importado=FALSE`, alíquota/fundamento vindos de `aliquota_interestadual(o,d)`.
  - `fiscal.icms_interno` (source `SEFAZ-SEED`, ncm_prefix NULL): **3 linhas** — SP 18.0 (FCP null), MG 18.0 (null), RJ 18.0 + FCP 2.0.
  - `fiscal.categoria` (`ON CONFLICT (slug) DO NOTHING`): **5 slugs** — `epi`, `maquinas`, `embalagens`, `material-escritorio`, `informatica`.
  - Retorno: `{"interestadual": 702, "interno": 3, "categorias": 5}`.

---

## 20 — `scripts/validate_schema.py` (CI job `schema-validation`)

- **Entradas:** arquivo `schemas/alert.v1.json`. Dep: `jsonschema`.
- **Valida:** é JSON Schema válido (Draft202012); contém campos obrigatórios `{alert_id, dedup_key, rule_id, severity, channels, occurred_at}`; `additionalProperties === false`. Sai 1 em falha.

---

## 21 — `scripts/check_docker_security.py` (CI job `docker-security`)

- **Entradas:** `docker/compose/base.yml`. Dep: `pyyaml`.
- **Valida:**
  - Nenhum DB (`postgres, pgbouncer, neo4j, opensearch, redis, minio, chromadb`) com porta publicada no host (exceto `host_ip=127.0.0.1`).
  - MinIO: nenhum `mc anonymous set` que não seja `set none`; cada bucket de `{bronze, silver, gold, documents, backups}` tem `anonymous set none`.
- Sai 1 em qualquer violação.

---

## 22 — `scripts/scaffold_product.py`

- **Entradas (CLI):** `<nome>` `<descrição>`. **Saídas (⚙ arquivos gerados, recusa sobrescrever):**
  - `services/shared/contracts/<name>.py` (contrato SEAMS + Protocol, `CONTRACT_VERSION=<name>/v1`).
  - `services/<name>/engine/factory.py` (factory).
  - `services/gateway/routers/<name>.py` (router FastAPI com `_get_tenant`, endpoint `/health`).
  - Imprime passos manuais 4-8 (registrar router, Ledger, migração, Celery, frontend).

---

## 23 — `.env.example` (tabela completa de variáveis)

| var | exemplo | segredo | consumidor(es) |
|-----|---------|:---:|----------------|
| `POSTGRES_USER` | `juridico` | | postgres, pgbouncer, migrate, Makefile |
| `POSTGRES_PASSWORD` | `TROQUE_SENHA_FORTE` | 🔒 | postgres, pgbouncer, migrate (MIGRATIONS_DATABASE_URL) |
| `POSTGRES_DB` | `juridico_platform` | | postgres, pgbouncer, migrate, DATABASE_URL de todos os workers/api |
| `APP_USER_PASSWORD` | `TROQUE_SENHA_FORTE` | 🔒 | pgbouncer (userlist), DATABASE_URL de celery-worker/beat, fiscal-worker, legalscore-api |
| `PGBOUNCER_POOL_SIZE` | `20` | | (declarado; base.yml usa `PGBOUNCER_DEFAULT_POOL_SIZE=20` hard-coded) |
| `PGBOUNCER_MAX_CLIENT_CONN` | `1000` | | pgbouncer |
| `NEO4J_PASSWORD` | `TROQUE_SENHA_FORTE` | 🔒 | neo4j (NEO4J_AUTH/healthcheck), celery-worker |
| `REDIS_PASSWORD` | `TROQUE_SENHA_FORTE` | 🔒 | redis, celery-worker/beat, fiscal-worker/beat, flower, Makefile redis-cli |
| `MINIO_USER` | `admin` | 🔒 | minio (ROOT_USER), minio-init, celery-worker, fiscal-worker |
| `MINIO_PASSWORD` | `TROQUE_SENHA_FORTE` | 🔒 | minio (ROOT_PASSWORD), minio-init, celery-worker, fiscal-worker |
| `LLM_API_KEY` | `sk-TROQUE_API_KEY` | 🔒 | serviços de IA (não referenciado em compose) |
| `LLM_MODEL_PRIMARY` | `gpt-4o` | | serviços de IA |
| `LLM_MODEL_FAST` | `gpt-4o-mini` | | serviços de IA |
| `LLM_MODEL_LOCAL` | `llama3:8b` | | ollama / IA local |
| `JWT_SECRET` | `TROQUE_SECRET_FORTE_256BITS` | 🔒 | gateway (auth JWT) |
| `JWT_EXPIRY_HOURS` | `24` | | gateway |
| `LETSENCRYPT_EMAIL` | `seu@email.com` | | traefik (ACME) |
| `DOMAIN` | `seudominio.com.br` | | frontend (labels Traefik Host) |
| `GRAFANA_PASSWORD` | `TROQUE_SENHA_FORTE` | 🔒 | grafana |
| `DATAJUD_API_URL` | `https://api-publica.datajud.cnj.jus.br` | | celery-worker |
| `DATAJUD_TOKEN` | `APIKeyPublica` | 🔒 | celery-worker |
| `ABJ_ENABLED` | `false` | | ingest ABJ (task) |
| `ABJ_DATA_URL` | (vazio) | | ingest ABJ |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/XXX/YYY/ZZZ` | 🔒 | alertmanager |
| `ALERT_EMAIL` | `ops@seudominio.com.br` | | alertmanager |
| `TIPI_CSV_URL` | `https://www.gov.br/.../tipi.csv` | | fiscal ingest (rfb_tipi) |
| `PLAYWRIGHT_EXECUTABLE` | `/opt/pw-browsers/chromium` (comentado) | | fiscal browser |

**Vars derivadas (compostas em compose, não em .env):** `DATABASE_URL`, `MIGRATIONS_DATABASE_URL`, `REDIS_URL`, `NEO4J_URI`, `NEO4J_USER`, `OPENSEARCH_URL`, `CHROMA_URL`, `MINIO_URL`, `OLLAMA_URL`, `CELERY_BROKER_URL`, `NEXT_PUBLIC_GATEWAY_URL`, `OLLAMA_HOST`, `GF_SECURITY_ADMIN_PASSWORD`, `GF_USERS_ALLOW_SIGN_UP`, `GF_FEATURE_TOGGLES_ENABLE`, `PGBOUNCER_DEFAULT_POOL_SIZE`. **CI-only:** `HMAC_KEY` 🔒, `ENV=test`.

---

## 24 — `.github/workflows/ci.yml` (7 jobs)

**Triggers:** push em `main`, `claude/**`, `feature/**`; PR para `main`.

| Job | Runner/timeout | Entradas relevantes | Valida |
|-----|----------------|---------------------|--------|
| `unit-tests` | ubuntu, 15min | env `HMAC_KEY=aaaa…(64 a's)` 🔒, `ENV=test` | pytest `tests/unit/`, `tests/e2e/`, `services/scoring/tests/contract/`, `services/shared/alerts/tests/`, `--cov=services --cov-fail-under=80`; upload `coverage.xml` |
| `lint` | ubuntu, 5min | — | `ruff check services/ tests/ --ignore E501,B008,UP007` (ruff 0.6.9) |
| `schema-validation` | ubuntu, 5min | — | `python scripts/validate_schema.py` |
| `docker-security` | ubuntu, 5min | — | `python scripts/check_docker_security.py` + grep de `api.insecure=true` em traefik.yml |
| `api-antipatterns` | ubuntu, 5min | — | grep: sem `hexdigest()[` em `lgpd.py`; sem `entries[-` em `merkle.py` |
| `integration-tests` | ubuntu, 10min | service `postgres:16-alpine` (`POSTGRES_USER=juridico`, `POSTGRES_PASSWORD=testpassword` 🔒, `POSTGRES_DB=juridico_platform`, porta 5432); env `MIGRATIONS_DATABASE_URL=postgresql://juridico:testpassword@localhost:5432/juridico_platform` 🔒, `DATABASE_URL=postgresql://app_user:testpassword@localhost:5432/...` 🔒, `HMAC_KEY` 🔒, `ENV=test` | bootstrap-db.sql → `ALTER ROLE app_user PASSWORD 'testpassword'` → `migrate.py` (×2, 2ª no-op) → `seed_fiscal.py` → `pytest tests/integration/ -m integration` (prova RLS/SET LOCAL) |
| `frontend-tests` | ubuntu, 10min | pnpm 9.12.3, node 20 | `pnpm --filter @juridico/ui test` (Vitest) |
| `frontend-build` | ubuntu, 15min | pnpm/node 20 | type-check `@juridico/tokens`,`@juridico/ui`,`platform` (tsc --noEmit) + `pnpm --filter platform build` |
| `container-scan` | ubuntu, 15min | — | `docker build -f services/gateway/Dockerfile` (gate); Trivy image + fs secret scan (report-only, exit-code 0) |

**Coverage threshold: 80% (`--cov-fail-under=80`).**

---

## 25 — `Makefile`

- **Env consumidas:** `POSTGRES_USER`, `POSTGRES_DB`, `REDIS_PASSWORD`, `MIGRATIONS_DATABASE_URL`; vars `UF` (def SP), `CONSUMIDOR_URL`, `SERVICE`, `COMPOSE_FILES=-f docker-compose.yml`.
- **Alvos:** `up/down/logs/logs-service`, `health` (curl gateway:8000/health, prometheus:9090, grafana:3001, minio:9000), `migrate`/`migrate-status`, `test`, `load-test` (Locust 500 users), `backup` (pg_dump + neo4j-admin dump), `ingest-datajud/-caged/-ibge/-consumidor/-abj/-all`, `jurimetria-aggregate`, `dash`, `neo4j-shell`, `pg-shell`, `redis-cli`, `clean` (down -v destrutivo).
- **`secrets-init` (⚙ 🔒):** cria `secrets/` com placeholders `db_password.txt`, `jwt_secret.txt`, `llm_api_key.txt`, `neo4j_password.txt`, `redis_password.txt`, `minio_password.txt` (chmod 600).

---

## 26 — `pyproject.toml`

- **pytest:** `pythonpath=["."]`, `testpaths=["tests","services"]`, markers `integration`/`e2e`, `--strict-markers`.
- **coverage:** `source=["services"]`, `fail_under=80`, extensa lista `omit` (tasks Celery, gateway, storage I/O, taxpredict, etc.).
- **ruff:** target `py312`, line-length 100, select `E,F,I,UP,B`, ignore `E501`.
- **build-system:** setuptools>=68.

---

## 27 — `.gitignore`

Exclui: `secrets/`, `.env`, `.env.*` (exceto `.env.example`), caches Python, `node_modules/`, `.next/`, `pnpm-lock.yaml`, `data/`, `*.log`, `*.tfstate*`, `.terraform/`, `bronze/silver/gold/`, `.coverage`, `**/next-env.d.ts`.

---

## 28 — Dockerfiles (build inputs ⚙)

- `services/ingest/Dockerfile`: python:3.12-slim, `PYTHONPATH=/app`, instala `requirements.txt`, copia `services/`, CMD celery worker.
- `services/fiscal/Dockerfile`: python:3.12-slim + **tesseract-ocr(-por)** + libs Chromium; `playwright install chromium`; CMD celery `-Q fiscal,batch`.
- `services/gateway/Dockerfile`: python:3.12-slim, `EXPOSE 8000`, CMD `uvicorn services.gateway.main:app --port 8000`.
- `frontend/apps/platform/Dockerfile`: node:20-alpine multi-stage (deps→builder→runner), pnpm 9.12.3, Next standalone, usuário não-root `nextjs:1001`, `EXPOSE 3000`, `PORT=3000 HOSTNAME=0.0.0.0`.
- `docker/products/legalscore/Dockerfile`: placeholder (`print('placeholder')`).

---

## 29 — Placeholders

- `infra/scripts/backup.sh`: `echo "Backup placeholder"`.
- `infra/scripts/setup-docker.sh`: `echo "Setup inicial Docker/Compose placeholder"`.
- `infra/terraform/README.md`: "Terraform IaC placeholder".
- `examples/README.md`: "Examples placeholder".
- `data/.gitkeep`, `.github/workflows/.gitkeep`, `docker/products/{compliance-radar,contabilia,taxpredict}/.gitkeep`: vazios.

---

## Schema DB completo (schema.table · colunas · chaves · RLS)

> Legenda colunas: PK=primary key, FK=foreign key, U=unique, NN=not null, D=default.

### schema `tenant`

**`tenant.tenants`**
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `id` | UUID | PK, D `uuid_generate_v4()` |
| `slug` | VARCHAR(64) | NN, **U** |
| `name` | VARCHAR(255) | NN |
| `plan` | VARCHAR(50) | NN, D `'starter'` |
| `active` | BOOLEAN | NN, D TRUE |
| `created_at` | TIMESTAMPTZ | NN, D NOW() |

RLS: não. Seed: id `…0001` `dev-tenant`.

**`tenant.users`** (colunas `password_hash`, `name` adicionadas na migração 002)
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `id` | UUID | PK, D `uuid_generate_v4()` |
| `tenant_id` | UUID | NN, FK→`tenant.tenants(id)` |
| `email` | VARCHAR(255) | NN |
| `role` | VARCHAR(50) | NN, D `'viewer'` (admin\|analyst\|viewer) |
| `active` | BOOLEAN | NN, D TRUE |
| `created_at` | TIMESTAMPTZ | NN, D NOW() |
| `password_hash` | TEXT | (m002) PBKDF2 |
| `name` | VARCHAR(255) | (m002) |
| — | — | **U (tenant_id, email)** |

RLS: não. Seed DEV (m002): `admin@dev.com` / senha `dev12345` / role admin.

**`tenant.idempotency_keys`**
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `key` | TEXT | NN |
| `tenant_id` | UUID | NN |
| `response` | JSONB | NN |
| `created_at` | TIMESTAMPTZ | NN, D NOW() |
| — | — | **PK (tenant_id, key)** |

Índice `idx_idempotency_created(created_at)`. **RLS: ENABLE+FORCE**, policy `idempotency_tenant_isolation`.

### schema `ledger`

**`ledger.entries`**
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `id` | UUID | PK, D `uuid_generate_v4()` |
| `request_id` | VARCHAR(64) | NN, **U** |
| `entry_index` | BIGINT | NN (posição Merkle) |
| `created_at` | TIMESTAMPTZ | NN, D NOW() |
| `product` | VARCHAR(50) | NN |
| `tenant_id` | UUID | FK→`tenant.tenants(id)` |
| `inputs_hash` | VARCHAR(64) | NN |
| `outputs_hash` | VARCHAR(64) | NN |
| `sources` | JSONB | NN, D `'[]'` |
| `weights_applied` | JSONB | NN, D `'{}'` |
| `subject_token` | TEXT | pseudônimo cifrado AES-256-GCM |
| `leaf_hash` | VARCHAR(64) | |
| `merkle_root` | VARCHAR(64) | |
| — | — | **U `ledger_entries_tenant_idx_unique (tenant_id, entry_index)`** |

Índices: product, created, request, tenant, index. Trigger `ledger_immutable` (bloqueia UPDATE/DELETE). **RLS: ENABLE+FORCE**, policies `ledger_tenant_isolation`, `ledger_tenant_select`, `ledger_tenant_insert`.

**`ledger.anchors`** (`tenant_id` adicionado na m001)
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `anchor_at_index` | BIGINT | NN |
| `merkle_root` | VARCHAR(64) | NN |
| `tenant_id` | UUID | FK→`tenant.tenants(id)` |
| `created_at` | TIMESTAMPTZ | NN, D NOW() |

**RLS: ENABLE+FORCE**, policies `ledger_anchors_tenant_isolation`, `ledger_anchors_tenant_insert`. Seq `ledger.anchors_id_seq`.

### schema `ingest`

**`ingest.runs`**
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `source` | VARCHAR(50) | NN |
| `started_at` | TIMESTAMPTZ | NN, D NOW() |
| `finished_at` | TIMESTAMPTZ | |
| `status` | VARCHAR(20) | NN, D `'running'` |
| `records_in` | INTEGER | D 0 |
| `records_out` | INTEGER | D 0 |
| `transform_version` | VARCHAR(20) | |
| `error_msg` | TEXT | |

Índices: source, status. RLS: não.

### schema `public`

**`public.alerts_outbox`**
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `alert_id` | TEXT | PK (UUID, idempotência) |
| `dedup_key` | TEXT | NN |
| `envelope` | JSONB | NN |
| `status` | TEXT | NN, D `'pending'` (pending\|claimed\|done\|failed) |
| `attempts` | INT | NN, D 0 |
| `available_at` | TIMESTAMPTZ | NN, D NOW() |
| `created_at` | TIMESTAMPTZ | NN, D NOW() |

Índices: `ix_outbox_dispatch(status, available_at)`, `ix_outbox_dedup_key(dedup_key)`. RLS: não.

**`public.tenant_isolation_probe`** (sonda de teste)
| coluna | tipo | chave/notas |
|--------|------|-------------|
| `id` | UUID | PK, D `uuid_generate_v4()` |
| `tenant_id` | UUID | NN |
| `payload` | TEXT | NN |

**RLS: ENABLE+FORCE**, policy `probe_isolation` (USING + WITH CHECK).

**`public.schema_migrations`** (criada por migrate.py)
| coluna | tipo | chave |
|--------|------|-------|
| `version` | TEXT | PK |
| `checksum` | TEXT | NN |
| `applied_at` | TIMESTAMPTZ | D now() |

### schema `fiscal` (migração 003)

**`fiscal.ncm`**: `id` UUID PK D gen_random_uuid; `ncm_codigo` CHAR(8) NN; `descricao` TEXT NN; `capitulo` CHAR(2); `vigencia` DATERANGE NN D daterange(CURRENT_DATE,NULL); `source` VARCHAR(50) NN D 'TIPI'; `ingested_at` TIMESTAMPTZ NN D NOW; `transform_version` VARCHAR(20) NN D '1.0.0'. Constraint **EXCLUDE `no_overlap_ncm` (ncm_codigo=, vigencia &&)** via gist. Índice `idx_ncm_codigo`. RLS: não.

**`fiscal.ncm_migracao`**: `id` UUID PK; `ncm_origem` CHAR(8) NN; `ncm_destino` CHAR(8); `vigencia_inicio` DATE NN; `vigencia_fim` DATE; `ato_legal` TEXT; `ingested_at` TIMESTAMPTZ NN D NOW. Índice `idx_ncm_migracao_origem`. RLS: não.

**`fiscal.ipi_aliquota`**: `id` UUID PK; `ncm_codigo` CHAR(8) NN; `excecao` VARCHAR(10); `aliquota_pct` NUMERIC(6,3) NN; `vigencia` DATERANGE NN D…; `fundamento_legal` TEXT; `source` VARCHAR(50) NN D 'TIPI'; `ingested_at`; `transform_version` D '1.0.0'. Constraints **U `uq_ipi_ncm_excecao (ncm_codigo, excecao)` NULLS NOT DISTINCT**; **EXCLUDE `no_overlap_ipi`**. RLS: não.

**`fiscal.icms_interestadual`**: `id` UUID PK; `uf_origem` CHAR(2) NN; `uf_destino` CHAR(2) NN; `aliquota_pct` NUMERIC(5,2) NN; `importado` BOOLEAN NN D FALSE; `fundamento_legal` TEXT; `vigencia` DATERANGE NN D…; `source` VARCHAR(50) NN D 'SENADO'; `ingested_at`. **EXCLUDE `no_overlap_icms_inter` (uf_origem=, uf_destino=, importado=, vigencia &&)**. RLS: não. Seed: 702 linhas (source SENADO-SEED).

**`fiscal.icms_interno`**: `id` UUID PK; `uf` CHAR(2) NN; `ncm_prefix` VARCHAR(8); `aliquota_pct` NUMERIC(5,2) NN; `fcp_pct` NUMERIC(5,2); `ibs_pct` NUMERIC(5,2); `cbs_pct` NUMERIC(5,2); `fundamento_legal` TEXT; `vigencia` DATERANGE NN D…; `source` VARCHAR(50) NN D 'SEFAZ'; `ingested_at`; `transform_version` D '1.0.0'. **EXCLUDE `no_overlap_icms_interno`**. Índice `idx_icms_interno_uf`. RLS: não. Seed: 3 linhas (SEFAZ-SEED).

**`fiscal.categoria`**: `id` UUID PK; `slug` VARCHAR(64) NN **U**; `nome` VARCHAR(120) NN; `descricao` TEXT. RLS: não. Seed: 5 slugs.

**`fiscal.ncm_categoria`**: `id` UUID PK; `ncm_prefix` VARCHAR(8) NN; `categoria_id` UUID NN FK→`fiscal.categoria(id)`; `confianca` NUMERIC(4,3) NN D 1.0. **U `uq_ncm_categoria (ncm_prefix, categoria_id)`**. RLS: não.

**`fiscal.doc_hash`**: `id` UUID PK; `fonte` VARCHAR(50) NN; `file_hash` CHAR(64) NN; `url` TEXT; `processed_at` TIMESTAMPTZ NN D NOW. **U `uq_doc_hash (fonte, file_hash)`**. RLS: não.

**`fiscal.triage_job`** (por tenant): `job_id` VARCHAR(64) PK; `tenant_id` UUID NN FK→tenant.tenants; `status` VARCHAR(20) NN D 'queued'; `total` INT NN D 0; `processed` INT NN D 0; `spreadsheet_key` TEXT; `result_key` TEXT; `batch_merkle_root` CHAR(64); `ledger_request_id` VARCHAR(64); `created_at`; `completed_at`. **RLS: ENABLE+FORCE**, policies `triage_job_tenant_isolation`/`_insert`.

**`fiscal.triage_item`** (por tenant): `id` UUID PK; `job_id` VARCHAR(64) NN FK→triage_job; `tenant_id` UUID NN FK→tenant.tenants; `leaf_index` INT NN; `sku_descricao` TEXT; `ncm_sugerido` CHAR(8); `confidence` NUMERIC(4,3); `fonte_regra` VARCHAR(20); `icms_interno_efetivo_pct` NUMERIC(5,2); `icms_inter_pct` NUMERIC(5,2); `difal_pct` NUMERIC(5,2); `categoria` VARCHAR(64); `conflito` BOOLEAN NN D FALSE; `observacoes` JSONB NN D '[]'. Índice `idx_triage_item_job`. **RLS: ENABLE+FORCE**, policies `triage_item_tenant_isolation`/`_insert`.

### schema `jurimetria` (migração 004, todas SEM RLS)

**`jurimetria.tpu_classe`**: `codigo` VARCHAR(20) PK; `label` TEXT NN; `parent_codigo` VARCHAR(20); `hierarchy_path` TEXT; `source` VARCHAR(50) NN D 'CNJ'; `ingested_at`; `transform_version` D '1.0.0'.

**`jurimetria.tpu_assunto`**: `codigo` VARCHAR(20) PK; `label` TEXT NN; `parent_codigo` VARCHAR(20); `ramo` VARCHAR(30); `source` D 'CNJ'; `ingested_at`; `transform_version`.

**`jurimetria.indicador`**: `tribunal` VARCHAR(20) NN; `classe_tpu` VARCHAR(20) NN D ''; `assunto_tpu` VARCHAR(20) NN D ''; `periodo` VARCHAR(10) NN; `fonte` VARCHAR(20) NN D 'DATAJUD'; `n_processos` INT NN D 0; `duracao_mediana_dias` NUMERIC; `duracao_p25_dias` NUMERIC; `duracao_p75_dias` NUMERIC; `taxa_congestionamento` NUMERIC(6,4); `taxa_litigiosidade` NUMERIC; `pct_provimento` NUMERIC(6,4); `source` D 'DATAJUD'; `ingested_at`; `transform_version`. **PK `(tribunal, classe_tpu, assunto_tpu, periodo, fonte)`**. Índices: tribunal+classe+assunto, classe, periodo.

**`jurimetria.abj_indicador_raw`**: `id` UUID PK; `tribunal` VARCHAR(20) NN; `classe_cnj` VARCHAR(20); `assunto_cnj` VARCHAR(20); `periodo` VARCHAR(10) NN; `tempo_medio_dias` NUMERIC; `taxa_congestionamento` NUMERIC(6,4); `casos_novos` INT; `casos_baixados` INT; `casos_pendentes` INT; `source` D 'ABJ'; `ingested_at`; `transform_version`. Índice único por expressão `uq_abj_indicador`.

---

## Portas expostas no host (consolidado)

| porta host | serviço | container port |
|-----------|---------|----------------|
| `80` | traefik | 80 |
| `443` | traefik | 443 |
| `127.0.0.1:8080` | traefik (dashboard) | 8080 |
| `9090` | prometheus | 9090 |
| `3001` | grafana | 3000 |
| `3100` | loki | 3100 |
| `9093` | alertmanager | 9093 |
| `5555` | flower | 5555 |
| `11434` | ollama | 11434 |
| `5432` (CI only) | postgres service (integration-tests) | 5432 |

Todos os bancos (postgres, pgbouncer, neo4j, opensearch, redis, minio, chromadb) e `platform`/`gateway`/`legalscore-api` NÃO expõem portas no host.
