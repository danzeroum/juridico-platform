.PHONY: help up down logs migrate test load-test backup health ingest-datajud ingest-caged ingest-ibge ingest-consumidor ingest-all dash secrets-init

COMPOSE_FILES := -f docker-compose.yml

help: ## Mostra este help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Levanta toda a plataforma
	docker compose $(COMPOSE_FILES) up -d --build
	@echo "\n✅ Plataforma iniciada. Verificando saúde em 30s..."
	@sleep 30
	@$(MAKE) health

down: ## Para toda a plataforma
	docker compose $(COMPOSE_FILES) down

logs: ## Logs de todos os serviços (follow)
	docker compose $(COMPOSE_FILES) logs -f

logs-service: ## Logs de um serviço específico: make logs-service SERVICE=legalscore-api
	docker compose $(COMPOSE_FILES) logs -f $(SERVICE)

health: ## Health check de todos os serviços
	@echo "=== Health Check ==="
	@docker compose $(COMPOSE_FILES) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "=== Endpoints ==="
	@curl -sf http://localhost:8000/health && echo "✅ Gateway: OK" || echo "❌ Gateway: FAIL"
	@curl -sf http://localhost:9090/-/healthy && echo "✅ Prometheus: OK" || echo "❌ Prometheus: FAIL"
	@curl -sf http://localhost:3001/api/health && echo "✅ Grafana: OK" || echo "❌ Grafana: FAIL"
	@curl -sf http://localhost:9000/minio/health/live && echo "✅ MinIO: OK" || echo "❌ MinIO: FAIL"

migrate: ## Aplica migrações de schema (runner idempotente; precisa de creds admin)
	@echo "Aplicando migrações… (defina MIGRATIONS_DATABASE_URL para a conexão de owner)"
	python scripts/migrate.py

migrate-status: ## Lista migrações aplicadas/pendentes
	python scripts/migrate.py --status

test: ## Roda todos os testes unitários e de integração
	docker compose $(COMPOSE_FILES) run --rm gateway pytest tests/ -v --tb=short

load-test: ## Load test Locust - 500 req/s por 5 min
	docker compose $(COMPOSE_FILES) run --rm locust \
		locust -f tests/load/locustfile.py \
		--host=http://gateway:8000 \
		--users=500 --spawn-rate=50 \
		--run-time=5m --headless \
		--html=tests/load/report.html

backup: ## Backup completo (PostgreSQL + Neo4j + MinIO)
	@echo "=== Backup PostgreSQL ==="
	docker compose $(COMPOSE_FILES) exec postgres \
		pg_dump -U $${POSTGRES_USER} $${POSTGRES_DB} | gzip > backups/pg_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "=== Backup Neo4j ==="
	docker compose $(COMPOSE_FILES) exec neo4j \
		neo4j-admin database dump neo4j --to-path=/backups/neo4j_$$(date +%Y%m%d_%H%M%S).dump
	@echo "✅ Backup concluído"

ingest-datajud: ## Dispara ingest manual do DATAJUD
	docker compose $(COMPOSE_FILES) exec celery-worker \
		celery -A ingest.celery_app call ingest.tasks.datajud.run_daily_ingest

ingest-caged: ## Dispara ingest manual do CAGED
	docker compose $(COMPOSE_FILES) exec celery-worker \
		celery -A ingest.celery_app call ingest.tasks.caged.run_monthly_ingest

UF ?= SP
ingest-ibge: ## Dispara ingest manual do IBGE (use UF=XX; padrão SP)
	docker compose $(COMPOSE_FILES) exec celery-worker \
		celery -A ingest.celery_app call ingest.tasks.ibge.run_ingest --args='["$(UF)"]'

CONSUMIDOR_URL ?=
ingest-consumidor: ## Dispara ingest do Consumidor.gov (use CONSUMIDOR_URL=<csv>)
	docker compose $(COMPOSE_FILES) exec celery-worker \
		celery -A ingest.celery_app call ingest.tasks.consumidor_gov.run_ingest --args='["$(CONSUMIDOR_URL)"]'

ingest-all: ## Dispara todos os ingests manualmente
	@$(MAKE) ingest-datajud
	@$(MAKE) ingest-caged
	@$(MAKE) ingest-ibge
	@echo "✅ Todos os ingests disparados"

dash: ## Abre Grafana + Prometheus + Flower no browser
	@open http://localhost:3001 || xdg-open http://localhost:3001
	@open http://localhost:9090 || xdg-open http://localhost:9090
	@open http://localhost:5555 || xdg-open http://localhost:5555

secrets-init: ## Inicializa estrutura de secrets (preencher manualmente depois)
	@mkdir -p secrets backups
	@echo 'TROQUE_POR_SENHA_FORTE' > secrets/db_password.txt
	@echo 'TROQUE_POR_SENHA_FORTE' > secrets/jwt_secret.txt
	@echo 'TROQUE_POR_API_KEY' > secrets/llm_api_key.txt
	@echo 'TROQUE_POR_SENHA_FORTE' > secrets/neo4j_password.txt
	@echo 'TROQUE_POR_SENHA_FORTE' > secrets/redis_password.txt
	@echo 'TROQUE_POR_SENHA_FORTE' > secrets/minio_password.txt
	@chmod 600 secrets/*
	@echo "✅ Estrutura de secrets criada em secrets/"
	@echo "⚠️  EDITE os arquivos em secrets/ antes de subir a plataforma!"

neo4j-shell: ## Abre shell Cypher no Neo4j
	docker compose $(COMPOSE_FILES) exec neo4j cypher-shell -u neo4j

pg-shell: ## Abre psql no PostgreSQL
	docker compose $(COMPOSE_FILES) exec postgres psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

redis-cli: ## Abre Redis CLI
	docker compose $(COMPOSE_FILES) exec redis redis-cli -a $${REDIS_PASSWORD}

clean: ## Remove volumes e dados (CUIDADO: destrutivo!)
	@read -p "⚠️  Isso vai apagar TODOS os dados. Confirmar? [y/N] " ans && [ $${ans:-N} = y ]
	docker compose $(COMPOSE_FILES) down -v --remove-orphans
