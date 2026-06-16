"""
RAG (Retrieval-Augmented Generation) compartilhado
Usado por LegalScore, TaxPredict, PetiBot e ConciliaIA
"""

import hashlib
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Motor RAG com deduplicacao por hash de conteudo.
    Evita re-embedar documentos ja existentes.
    """

    def __init__(self, collection_name: str = "juridico"):
        self.collection_name = collection_name
        self._chroma_client = None

    def _get_client(self):
        if self._chroma_client is None:
            import chromadb
            from shared.config import settings
            self._chroma_client = chromadb.HttpClient(
                host=settings.CHROMA_URL.replace("http://", "").split(":")[0],
                port=int(settings.CHROMA_URL.split(":")[-1]),
            )
        return self._chroma_client

    def upsert_document(self, doc_id: str, content: str, metadata: Dict) -> bool:
        """Adiciona documento ao indice vetorial com deduplicacao."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        client = self._get_client()
        collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity para textos juridicos
        )

        # Verificar se ja existe (deduplicacao)
        existing = collection.get(ids=[doc_id])
        if existing["ids"]:
            if existing["metadatas"][0].get("content_hash") == content_hash:
                logger.debug(f"Documento {doc_id} ja indexado, pulando.")
                return False

        # TODO: gerar embedding via Ollama BGE-M3 na Fase 1
        embedding = None

        collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[{**metadata, "content_hash": content_hash}],
        )
        return True

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Dict | None = None,
    ) -> List[Dict[str, Any]]:
        """Busca semantica por similaridade."""
        client = self._get_client()
        collection = client.get_or_create_collection(name=self.collection_name)

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        return [
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            }
            for i in range(len(results["ids"][0]))
        ]
