"""
Decision Ledger com Merkle Tree
Garante imutabilidade e auditabilidade de todas as decisoes automatizadas.
Essencial para compliance com BACEN, CVM e LGPD.
"""

import hashlib
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MerkleNode:
    def __init__(self, left=None, right=None, data: Optional[str] = None):
        self.left = left
        self.right = right
        self.data = data
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        if self.data:
            return hashlib.sha256(self.data.encode()).hexdigest()
        if self.left and self.right:
            combined = self.left.hash + self.right.hash
            return hashlib.sha256(combined.encode()).hexdigest()
        if self.left:
            return hashlib.sha256((self.left.hash * 2).encode()).hexdigest()
        return hashlib.sha256(b"").hexdigest()


def build_merkle_tree(leaves: List[str]) -> str:
    """Constroi Merkle tree e retorna o root hash."""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()

    nodes = [MerkleNode(data=leaf) for leaf in leaves]

    while len(nodes) > 1:
        if len(nodes) % 2 != 0:
            nodes.append(nodes[-1])  # duplicar ultimo se impar
        new_level = []
        for i in range(0, len(nodes), 2):
            parent = MerkleNode(left=nodes[i], right=nodes[i + 1])
            new_level.append(parent)
        nodes = new_level

    return nodes[0].hash


class DecisionLedger:
    """
    Ledger append-only para audit trail de decisoes automatizadas.
    Cada entrada e imutavel e verificavel via Merkle proof.
    """

    def __init__(self, db_session):
        self.db = db_session
        self._entries_cache: List[Dict] = []

    def add_entry(
        self,
        product: str,
        request_id: str,
        user_hash: Optional[str],
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        sources: List[str],
        weights: Dict[str, float],
    ) -> str:
        """Adiciona entrada no ledger e retorna o Merkle root atualizado."""

        entry = {
            "product": product,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "user_hash": user_hash,
            "inputs_hash": hashlib.sha256(
                json.dumps(inputs, sort_keys=True).encode()
            ).hexdigest(),
            "outputs_hash": hashlib.sha256(
                json.dumps(outputs, sort_keys=True).encode()
            ).hexdigest(),
            "sources": sources,
            "weights_applied": weights,
        }

        self._entries_cache.append(entry)

        # Recalcular Merkle root com as ultimas 100 entradas
        recent_hashes = [
            hashlib.sha256(
                json.dumps(e, sort_keys=True).encode()
            ).hexdigest()
            for e in self._entries_cache[-100:]
        ]
        merkle_root = build_merkle_tree(recent_hashes)
        entry["merkle_root"] = merkle_root

        # Persistir no PostgreSQL (append-only via trigger)
        self._persist(entry)

        logger.info(f"Ledger entry adicionada: {request_id} | root: {merkle_root[:8]}...")
        return merkle_root

    def _persist(self, entry: Dict) -> None:
        """Persiste entrada no PostgreSQL."""
        # TODO: implementar com SQLAlchemy na Fase 1
        pass

    def verify_integrity(self, request_id: str) -> bool:
        """Verifica se um registro nao foi alterado desde sua criacao."""
        # TODO: implementar busca + verificacao de Merkle proof na Fase 1
        raise NotImplementedError
