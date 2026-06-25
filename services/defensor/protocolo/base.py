"""Interface dos drivers de protocolo e utilidades comuns."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from services.shared.contracts.protocolo import ProtocoloRequest, ProtocoloResultado


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def numero_simulado(req: ProtocoloRequest) -> str:
    """Número de protocolo determinístico (estável p/ o mesmo caso) — modo simulação."""
    base = f"{req.canal.value}|{req.reclamante}|{req.reclamada}|{req.resumo}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:10].upper()
    return f"SIM-{req.canal.value}-{digest}"


class ProtocoloDriver(ABC):
    """Driver que submete (ou simula) o protocolo de uma defesa em um canal."""

    canal: str

    @abstractmethod
    def submit(self, req: ProtocoloRequest) -> ProtocoloResultado:
        """Submete o protocolo. NUNCA deve levantar — devolve um ProtocoloResultado."""
        raise NotImplementedError
