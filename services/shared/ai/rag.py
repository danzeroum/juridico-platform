"""
RAG (Retrieval-Augmented Generation) compartilhado.
Usado por LegalScore, TaxPredict, PetiBot e ConciliaIA.

Embeddings: BGE-M3 via Ollama (production). Fallback para o embedder padrão
do ChromaDB quando Ollama indisponível (development/CI).
"""

import hashlib
import json
import logging
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Motor RAG com deduplicação por hash de conteúdo e embeddings BGE-M3.
    """

    def __init__(self, collection_name: str = "juridico"):
        self.collection_name = collection_name
        self._chroma_client = None

    def _get_client(self):
        if self._chroma_client is None:
            import chromadb

            from services.shared.config import settings
            self._chroma_client = chromadb.HttpClient(
                host=settings.CHROMA_URL.replace("http://", "").split(":")[0],
                port=int(settings.CHROMA_URL.split(":")[-1]),
            )
        return self._chroma_client

    def _get_embedding(self, text: str) -> list[float] | None:
        """
        Gera embedding via Ollama BGE-M3.
        Retorna None se Ollama indisponível — ChromaDB usa embedder padrão.
        """
        try:
            from services.shared.config import settings
            payload = json.dumps({"model": "bge-m3", "prompt": text}).encode()
            req = urllib.request.Request(
                f"{settings.OLLAMA_URL}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data["embedding"]
        except Exception:
            logger.debug("Ollama BGE-M3 indisponível; usando embedder padrão do ChromaDB")
            return None

    def upsert_document(self, doc_id: str, content: str, metadata: dict) -> bool:
        """Indexa documento com deduplicação por hash de conteúdo."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        client = self._get_client()
        collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        existing = collection.get(ids=[doc_id])
        if existing["ids"]:
            if existing["metadatas"][0].get("content_hash") == content_hash:
                logger.debug("Documento %s já indexado, pulando.", doc_id)
                return False

        enriched_meta = {**metadata, "content_hash": content_hash}
        embedding = self._get_embedding(content)

        if embedding is not None:
            collection.upsert(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[enriched_meta],
            )
        else:
            collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[enriched_meta],
            )
        return True

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Busca semântica por similaridade usando BGE-M3 (ou embedder padrão)."""
        client = self._get_client()
        collection = client.get_or_create_collection(name=self.collection_name)

        embedding = self._get_embedding(query)
        kwargs: dict[str, Any] = {"n_results": n_results}
        if where is not None:
            kwargs["where"] = where

        if embedding is not None:
            results = collection.query(query_embeddings=[embedding], **kwargs)
        else:
            results = collection.query(query_texts=[query], **kwargs)

        return [
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            }
            for i in range(len(results["ids"][0]))
        ]
