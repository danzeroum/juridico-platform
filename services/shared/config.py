"""
Configuracao centralizada da plataforma.
Usa Pydantic Settings para validar e tipificar variaveis de ambiente.
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


def load_secret(name: str) -> str:
    """Carrega secret do Docker Secrets ou variavel de ambiente."""
    path = Path("/run/secrets") / name
    if path.exists():
        return path.read_text().strip()
    import os
    return os.getenv(name.upper(), "")


class Settings(BaseSettings):
    # Banco de dados
    DATABASE_URL: str = ""
    POSTGRES_USER: str = "juridico"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "juridico_platform"

    # Neo4j
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # Redis
    REDIS_URL: str = ""
    REDIS_PASSWORD: str = ""

    # OpenSearch
    OPENSEARCH_URL: str = "http://opensearch:9200"

    # ChromaDB
    CHROMA_URL: str = "http://chromadb:8000"

    # MinIO
    MINIO_URL: str = "http://minio:9000"
    MINIO_USER: str = "admin"
    MINIO_PASSWORD: str = ""

    # LLM
    LLM_API_KEY: str = ""
    LLM_MODEL_PRIMARY: str = "gpt-4o"
    LLM_MODEL_FAST: str = "gpt-4o-mini"
    LLM_MODEL_LOCAL: str = "llama3:8b"
    OLLAMA_URL: str = "http://ollama:11434"

    # JWT
    JWT_SECRET: str = ""
    JWT_EXPIRY_HOURS: int = 24

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # DATAJUD
    DATAJUD_API_URL: str = "https://api-publica.datajud.cnj.jus.br"
    DATAJUD_TOKEN: str = "APIKeyPublica"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
