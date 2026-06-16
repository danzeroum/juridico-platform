"""Tests for services/shared/config.py — verifica que cada propriedade retorna string."""
from __future__ import annotations


class TestSettings:
    def test_datajud_api_url_default(self):
        from services.shared.config import settings
        url = settings.DATAJUD_API_URL
        assert isinstance(url, str) and url.startswith("http")

    def test_datajud_token_default(self):
        from services.shared.config import settings
        val = settings.DATAJUD_TOKEN
        assert isinstance(val, str)

    def test_pgfn_api_url_default(self):
        from services.shared.config import settings
        url = settings.PGFN_API_URL
        assert isinstance(url, str) and url.startswith("http")

    def test_receita_api_url_default(self):
        from services.shared.config import settings
        url = settings.RECEITA_API_URL
        assert isinstance(url, str) and url.startswith("http")

    def test_redis_url_default(self):
        from services.shared.config import settings
        url = settings.REDIS_URL
        assert isinstance(url, str) and url.startswith("redis://")

    def test_opensearch_url_default(self):
        from services.shared.config import settings
        url = settings.OPENSEARCH_URL
        assert isinstance(url, str) and url.startswith("http")

    def test_neo4j_url_default(self):
        from services.shared.config import settings
        url = settings.NEO4J_URL
        assert isinstance(url, str) and url.startswith("bolt://")

    def test_neo4j_user_default(self):
        from services.shared.config import settings
        val = settings.NEO4J_USER
        assert isinstance(val, str) and val != ""

    def test_neo4j_password_default(self):
        from services.shared.config import settings
        val = settings.NEO4J_PASSWORD
        assert isinstance(val, str)

    def test_chroma_url_default(self):
        from services.shared.config import settings
        url = settings.CHROMA_URL
        assert isinstance(url, str) and url.startswith("http")

    def test_database_url_default(self):
        from services.shared.config import settings
        url = settings.DATABASE_URL
        assert isinstance(url, str) and "postgresql" in url

    def test_hmac_key_default(self):
        from services.shared.config import settings
        val = settings.HMAC_KEY
        assert isinstance(val, str)

    def test_minio_url_default(self):
        from services.shared.config import settings
        url = settings.MINIO_URL
        assert isinstance(url, str) and url.startswith("http")

    def test_minio_access_key_default(self):
        from services.shared.config import settings
        val = settings.MINIO_ACCESS_KEY
        assert isinstance(val, str) and val != ""

    def test_minio_secret_key_default(self):
        from services.shared.config import settings
        val = settings.MINIO_SECRET_KEY
        assert isinstance(val, str) and val != ""

    def test_ollama_url_default(self):
        from services.shared.config import settings
        url = settings.OLLAMA_URL
        assert isinstance(url, str) and url.startswith("http")

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("DATAJUD_API_URL", "https://custom.datajud.example")
        from services.shared.config import _Settings
        s = _Settings()
        assert s.DATAJUD_API_URL == "https://custom.datajud.example"
