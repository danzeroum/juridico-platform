# Deploy & Release

Runbook do pipeline de build/scan e do que falta para um deploy real (P0-10).

## O que já está automatizado (CI, sem secrets)

- **Build da imagem do gateway** (`container-scan` job) — `docker build` é gate real:
  quebra se o `Dockerfile` regredir.
- **Scan de vulnerabilidades + segredos (Trivy)** — hoje **report-only**
  (`exit-code: 0`) para não bloquear no backlog de CVEs existente. Para endurecer
  após triagem, troque para `exit-code: 1` (e remova `ignore-unfixed` se quiser
  falhar em CVEs ainda sem correção) no `.github/workflows/ci.yml`.
- **Migrações no startup** — serviço one-shot `migrate` em `docker/compose/base.yml`
  roda `scripts/migrate.py` como **owner** (POSTGRES_USER, direto no Postgres)
  antes do `legalscore-api` subir (`depends_on: service_completed_successfully`).

## O que falta (decisão de plataforma + secrets)

O **destino do deploy** (registry + host) é uma escolha de plataforma. Nada é
publicado sem você configurar isto.

### Opção A — GHCR (recomendado, usa GITHUB_TOKEN)

Publica imagens em `ghcr.io/<owner>/<repo>` no merge à `main`. Crie
`.github/workflows/release.yml`:

```yaml
name: Release
on:
  push:
    branches: [main]
permissions:
  contents: read
  packages: write
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: services/gateway/Dockerfile
          push: true
          tags: ghcr.io/${{ github.repository }}/gateway:latest,ghcr.io/${{ github.repository }}/gateway:${{ github.sha }}
```

(Repita o passo `build-push-action` para `frontend/apps/platform/Dockerfile` e
`services/ingest/Dockerfile`.)

### Opção B — Docker Hub / registry privado

Igual à Opção A, mas com `registry:` próprio e secrets `DOCKER_USERNAME` /
`DOCKER_TOKEN` configurados em **Settings → Secrets and variables → Actions**.

### Opção C — Deploy por SSH (host com docker compose)

Após o push das imagens, um passo `appleboy/ssh-action` puxa as imagens e roda
`docker compose ... up -d` no host. Exige secrets `SSH_HOST`, `SSH_USER`,
`SSH_KEY`.

## Variáveis/secrets obrigatórios para produção

Ver `docs/PRODUCTION-READINESS.md` (seção "Receita mínima"): `ENV=production`,
`REQUIRE_AUTH=true`, `NEXT_PUBLIC_DEMO_MODE=false`, `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`
(Docker Secret/Vault), `APP_USER_PASSWORD`, `HMAC_KEY`, `RATE_LIMIT_FAIL_CLOSED`
conforme a política desejada.

## Migrações em deploy

`scripts/migrate.py` é idempotente e rastreia estado em `public.schema_migrations`.
No compose, o serviço `migrate` já roda no boot. Em deploy gerenciado (K8s),
rode-o como um **init job** com credenciais de **owner** antes de subir o gateway:

```bash
MIGRATIONS_DATABASE_URL=postgresql://<owner>:<senha>@<host>:5432/<db> \
  python scripts/migrate.py
```
