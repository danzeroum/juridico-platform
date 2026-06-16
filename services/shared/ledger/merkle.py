import hashlib
import json
from datetime import datetime
from typing import Any


class DecisionLedger:
    def __init__(self):
        self.entries = []
        self.merkle_root = None

    def add_entry(self, request_id: str, product: str, inputs: dict[str, Any], outputs: dict[str, Any], sources: list[str] | None = None, weights: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = {
            'request_id': request_id,
            'timestamp': datetime.utcnow().isoformat(),
            'product': product,
            'inputs_hash': hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            'outputs_hash': hashlib.sha256(json.dumps(outputs, sort_keys=True).encode()).hexdigest(),
            'sources': sources or [],
            'weights_applied': weights or {},
        }
        self.entries.append(entry)
        self.merkle_root = self._update_merkle_root()
        return entry

    def _update_merkle_root(self) -> str:
        leaves = [hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest() for e in self.entries[-100:]]
        if not leaves:
            return hashlib.sha256(b'').hexdigest()
        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])
            leaves = [hashlib.sha256((leaves[i] + leaves[i + 1]).encode()).hexdigest() for i in range(0, len(leaves), 2)]
        return leaves[0]
