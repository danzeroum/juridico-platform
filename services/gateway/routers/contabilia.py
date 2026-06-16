from fastapi import APIRouter, UploadFile, File, HTTPException
# TODO: implementar na Fase 2

router = APIRouter()


@router.post("/audit/upload")
async def upload_financials(file: UploadFile = File(...)):
    """Upload de demonstracoes financeiras (PDF/Excel/XBRL)."""
    allowed = {"application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
               "application/vnd.ms-excel", "text/csv"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Formato nao suportado: {file.content_type}")
    raise HTTPException(status_code=501, detail="ContabilIA em implementacao - Fase 2")


@router.get("/audit/{report_id}")
async def get_report(report_id: str):
    """Recupera relatorio de auditoria gerado."""
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 2")
