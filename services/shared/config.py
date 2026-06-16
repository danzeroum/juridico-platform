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


settings = _Settings()
