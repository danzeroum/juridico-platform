"""
Serviço de protocolo do Defensor.

protocolar(req) escolhe o driver conforme settings.PROTOCOLO_MODO (padrão
"simulacao") e o canal, submete (ou simula) e registra no log de auditoria.
Nunca submete de verdade sem PROTOCOLO_MODO=real + credenciais.
"""
from __future__ import annotations

import logging

from services.defensor.protocolo.factory import get_driver
from services.shared.config import settings
from services.shared.contracts.protocolo import ProtocoloRequest, ProtocoloResultado

logger = logging.getLogger(__name__)


def protocolar(req: ProtocoloRequest) -> ProtocoloResultado:
    """Protocola (ou simula) a defesa no canal informado."""
    modo = settings.PROTOCOLO_MODO
    driver = get_driver(req.canal, modo)
    resultado = driver.submit(req)
    logger.info(
        "Protocolo canal=%s modo=%s status=%s numero=%s",
        req.canal.value, resultado.modo, resultado.status, resultado.numero_protocolo,
    )
    return resultado
