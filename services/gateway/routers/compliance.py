from fastapi import APIRouter, HTTPException

# TODO: implementar na Fase 3

router = APIRouter()


@router.get("/compliance/municipalities")
async def list_municipalities(uf: str | None = None):
    """Lista municipios monitorados com indicadores."""
    raise HTTPException(status_code=501, detail="ComplianceRadar em implementacao - Fase 3")


@router.get("/compliance/municipality/{ibge_code}")
async def municipality_detail(ibge_code: str):
    """Indicadores detalhados de um municipio."""
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 3")


@router.get("/compliance/alerts")
async def list_alerts(severity: str | None = None, page: int = 1):
    """Alertas ativos do ComplianceRadar."""
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 3")
