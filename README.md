# juridico-platform

> **Plataforma Jurídico-Contábil Docker-First** — IA aplicada ao direito e contabilidade brasileira

[![SLA](https://img.shields.io/badge/SLA-99.5%25-brightgreen)](#)
[![Produtos](https://img.shields.io/badge/produtos-8-blue)](#)
[![Stack](https://img.shields.io/badge/stack-Docker%20Compose-2496ED)](#)
[![License](https://img.shields.io/badge/license-Proprietary-red)](#)

## Produtos

| # | Produto | Descrição | SLA |
|---|---------|-----------|-----|
| 1 | **LegalScore PJ** | Rating de risco jurídico-financeiro de PJ | p95 < 1.5s |
| 2 | **ContabilIA** | Auditoria contábil automatizada | p95 < 60s |
| 3 | **ComplianceRadar** | Monitoramento municipal com alertas | 99% alertas |
| 4 | **TaxPredict** | Previsão bayesiana de desfecho tributário | p95 < 3s |
| 5 | **LicitaWatch** | Monitoramento de licitações (PNCP) | Diário |
| 6 | **DanoBot** | Laudo de danos socioeconômicos automatizado | p95 < 5s |
| 7 | **PetiBot** | Gerador de peças processuais com jurisprudência | p95 < 10s |
| 8 | **ConciliaIA** | Análise de viabilidade de acordos | p95 < 3s |

## Stack Tecnológico

```
Infrastrutura:  Docker Compose → Kubernetes (Helm)
Banco Relacional: PostgreSQL 16 + PgBouncer
Grafo:          Neo4j 5 Enterprise
Busca:          OpenSearch 2.12
Cache/Broker:   Redis 7 + Sentinel
Data Lake:      MinIO (S3-compatível)
Vetorial/RAG:   ChromaDB
LLM Local:      Ollama (Llama3:8b + BGE-M3)
Proxy:          Traefik v3 + Let's Encrypt
Orquestração:   Celery + Beat
Monitoramento:  Prometheus + Grafana + Loki
API:            FastAPI + Uvicorn
Frontend:       Next.js 14 + TanStack Query
Compliance:     Decision Ledger (Merkle tree + SHA-256)
```

## Início Rápido

```bash
# 1. Clonar e configurar
git clone https://github.com/danzeroum/juridico-platform.git
cd juridico-platform
cp .env.example .env
# Editar .env com suas credenciais

# 2. Criar secrets de produção
mkdir -p secrets
echo 'SENHA_FORTE' > secrets/db_password.txt
echo 'SENHA_FORTE' > secrets/jwt_secret.txt
echo 'sk-SUA_KEY' > secrets/llm_api_key.txt
echo 'SENHA_FORTE' > secrets/neo4j_password.txt
echo 'SENHA_FORTE' > secrets/redis_password.txt
chmod 600 secrets/*

# 3. Subir toda a plataforma
make up

# 4. Verificar saúde
make health

# 5. Rodar migrações
make migrate

# 6. Iniciar ingest inicial (DATAJUD últimos 30 dias)
make ingest-datajud
```

## Comandos Make

```bash
make up           # Levanta toda a plataforma
make down         # Para toda a plataforma
make health       # Health check de todos os serviços
make logs         # Logs de todos os serviços
make migrate      # Roda migrações Alembic
make test         # Roda todos os testes
make load-test    # Load test Locust (500 req/s, 5min)
make backup       # Backup completo (PG + Neo4j + MinIO)
make ingest-all   # Dispara todos os ingests
make dash         # Abre Grafana + Prometheus + Flower
```

## Fontes de Dados (14)

| Fonte | Domínio | Cadência |
|-------|---------|----------|
| Receita Federal | CNPJ/Cadastro | Diária |
| DATAJUD (CNJ) | Processos/Jurisprudência | Diária |
| PGFN | Dívida ativa | Semanal |
| CAGED (MTE) | Emprego | Mensal |
| SICONFI (STN) | Execução orçamentária | Mensal |
| PNCP | Licitações | Diária |
| DATASUS/SIH | Saúde | Mensal |
| SNIS (MDR) | Saneamento | Anual |
| INEP | Educação | Anual |
| ComexStat | Comércio exterior | Mensal |
| Portal Transparência | Receitas/Despesas | Horária |
| Câmara Deputados | Legislação | On-demand |
| BCB/ESTBAN | Indicadores bancários | Mensal |
| IBGE | Dados municipais | Anual |

## Roadmap

| Fase | Semanas | Produto | Milestone |
|------|---------|---------|----------|
| 0 | 1-3 | Infra | Setup, bootstrap, health checks |
| 1 | 4-13 | LegalScore PJ | v1.0 com SLA 99.5% |
| 2 | 14-23 | ContabilIA | v1.0 com 8 cross-checks |
| 3 | 24-39 | ComplianceRadar + TaxPredict | v1.0 |
| 4 | 40-52 | Produtos secundários + K8s | Deploy produção |

## Compliance

- **LGPD by design**: pseudonimização no ingest, k-anonymity, right-to-erasure
- **Decision Ledger**: audit trail imutável com Merkle tree para BACEN/CVM
- **TLS 1.3**: em todas as conexões (Traefik + Let's Encrypt)
- **Docker Secrets**: credenciais nunca em variáveis de ambiente

---

*Confidencial — uso interno do time de desenvolvimento*
