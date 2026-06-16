from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
# TODO: implementar na Fase 3

router = APIRouter()


class TaxCase(BaseModel):
    descricao: str
    materia: str | None = None  # PIS_COFINS, IRPJ, CSLL, ICMS, IPI, ISS, SIMPLES
    valor: float | None = None
    orgao_autuante: str | None = None


@router.post("/taxpredict/predict")
async def predict(case: TaxCase):
    """Previsao probabilistica de desfecho tributario."""
    raise HTTPException(status_code=501, detail="TaxPredict em implementacao - Fase 3")
