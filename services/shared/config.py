import os
from pathlib import Path


def load_secret(name: str) -> str:
    path = Path('/run/secrets') / name
    if path.exists():
        return path.read_text().strip()
    return os.getenv(name.upper(), '')


class _Settings:
    """App settings from env vars / Docker Secrets. Properties are lazy-evaluated."""

    @property
    def DATAJUD_API_URL(self) -> str:
        return os.getenv("DATAJUD_API_URL", "https://api-publica.datajud.cnj.jus.br")

    @property
    def DATAJUD_TOKEN(self) -> str:
        return load_secret("datajud_token") or os.getenv("DATAJUD_TOKEN", "")

    @property
    def PGFN_API_URL(self) -> str:
        return os.getenv("PGFN_API_URL", "https://www.regularize.pgfn.gov.br/api")

    @property
    def RECEITA_API_URL(self) -> str:
        return os.getenv("RECEITA_API_URL", "https://publica.cnpj.ws/cnpj")

    # --- ABJ (Associação Brasileira de Jurimetria) ---
    # Desligada por padrão: confirmar licença de redistribuição dos datasets
    # abjData antes de habilitar em produção (ver ROPA / base legal por fonte).
    @property
    def ABJ_ENABLED(self) -> bool:
        return os.getenv("ABJ_ENABLED", "false").lower() in ("1", "true", "yes")

    @property
    def ABJ_DATA_URL(self) -> str:
        # CSV de indicadores (abjData / observatório). Vazio = usa semente local.
        return os.getenv("ABJ_DATA_URL", "")

    @property
    def REDIS_URL(self) -> str:
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @property
    def OPENSEARCH_URL(self) -> str:
        return os.getenv("OPENSEARCH_URL", "http://opensearch:9200")

    @property
    def NEO4J_URL(self) -> str:
        return os.getenv("NEO4J_URL", "bolt://neo4j:7687")

    @property
    def NEO4J_USER(self) -> str:
        return os.getenv("NEO4J_USER", "neo4j")

    @property
    def NEO4J_PASSWORD(self) -> str:
        return load_secret("neo4j_password") or os.getenv("NEO4J_PASSWORD", "")

    @property
    def CHROMA_URL(self) -> str:
        return os.getenv("CHROMA_URL", "http://chromadb:8001")

    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@pgbouncer:6432/juridico")

    @property
    def HMAC_KEY(self) -> str:
        return load_secret("hmac_key") or os.getenv("HMAC_KEY", "")

    @property
    def MINIO_URL(self) -> str:
        return os.getenv("MINIO_URL", "http://minio:9000")

    @property
    def MINIO_ACCESS_KEY(self) -> str:
        return load_secret("minio_access_key") or os.getenv("MINIO_ACCESS_KEY", "minioadmin")

    @property
    def MINIO_SECRET_KEY(self) -> str:
        return load_secret("minio_secret_key") or os.getenv("MINIO_SECRET_KEY", "minioadmin")

    @property
    def OLLAMA_URL(self) -> str:
        return os.getenv("OLLAMA_URL", "http://ollama:11434")

    # --- LLM (geração de texto) ---
    @property
    def LLM_PROVIDER(self) -> str:
        return os.getenv("LLM_PROVIDER", "ollama")  # ollama | openai

    @property
    def LLM_API_KEY(self) -> str:
        return load_secret("llm_api_key") or os.getenv("LLM_API_KEY", "")

    @property
    def LLM_BASE_URL(self) -> str:
        return os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

    @property
    def LLM_MODEL(self) -> str:
        return os.getenv("LLM_MODEL", "gpt-4o")

    @property
    def LLM_MODEL_LOCAL(self) -> str:
        return os.getenv("LLM_MODEL_LOCAL", "llama3:8b")

    # --- Automação de protocolo (Defensor) ---
    # Padrão "simulacao": nunca submete de verdade. "real" exige credenciais + host liberado.
    @property
    def PROTOCOLO_MODO(self) -> str:
        return os.getenv("PROTOCOLO_MODO", "simulacao")

    @property
    def CONSUMIDOR_GOV_USER(self) -> str:
        return load_secret("consumidor_gov_user") or os.getenv("CONSUMIDOR_GOV_USER", "")

    @property
    def CONSUMIDOR_GOV_PASSWORD(self) -> str:
        return load_secret("consumidor_gov_password") or os.getenv("CONSUMIDOR_GOV_PASSWORD", "")

    @property
    def PROCON_SP_USER(self) -> str:
        return load_secret("procon_sp_user") or os.getenv("PROCON_SP_USER", "")

    @property
    def PROCON_SP_PASSWORD(self) -> str:
        return load_secret("procon_sp_password") or os.getenv("PROCON_SP_PASSWORD", "")


settings = _Settings()
