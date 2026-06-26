"""Driver de simulação — padrão. Nunca submete nada de verdade."""
from __future__ import annotations

from services.defensor.protocolo.base import ProtocoloDriver, now_iso, numero_simulado
from services.shared.contracts.protocolo import (
    ProtocoloModo,
    ProtocoloRequest,
    ProtocoloResultado,
    ProtocoloStatus,
)


class SimulacaoDriver(ProtocoloDriver):
    """Gera um protocolo simulado (determinístico) sem qualquer chamada externa."""

    canal = "*"

    def submit(self, req: ProtocoloRequest) -> ProtocoloResultado:
        return ProtocoloResultado(
            canal=req.canal.value,
            modo=ProtocoloModo.SIMULACAO.value,
            status=ProtocoloStatus.SIMULADO.value,
            numero_protocolo=numero_simulado(req),
            url=None,
            mensagem=(
                "Protocolo SIMULADO — nenhuma submissão real foi feita. "
                "Configure PROTOCOLO_MODO=real + credenciais do portal para submeter."
            ),
            enviado_em=now_iso(),
        )
