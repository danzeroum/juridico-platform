"""Seleção do driver de protocolo por modo + canal."""
from __future__ import annotations

from services.defensor.protocolo.base import ProtocoloDriver
from services.defensor.protocolo.real import ConsumidorGovDriver, ProconSPDriver
from services.defensor.protocolo.simulacao import SimulacaoDriver
from services.shared.contracts.defensor import Canal
from services.shared.contracts.protocolo import ProtocoloModo

# Canais com driver real disponível.
_DRIVERS_REAIS: dict[Canal, type[ProtocoloDriver]] = {
    Canal.CONSUMIDOR_GOV: ConsumidorGovDriver,
    Canal.PROCON: ProconSPDriver,
}


def get_driver(canal: Canal, modo: str) -> ProtocoloDriver:
    """
    Devolve o driver adequado.

    - modo != "real"  → SimulacaoDriver (padrão seguro).
    - modo == "real"  → driver real do canal, se existir; senão simula
      (canais como OUVIDORIA/CONTENCIOSO ainda não têm automação).
    """
    if modo != ProtocoloModo.REAL.value:
        return SimulacaoDriver()
    driver_cls = _DRIVERS_REAIS.get(canal)
    return driver_cls() if driver_cls else SimulacaoDriver()
