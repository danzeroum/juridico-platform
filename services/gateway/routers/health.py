from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "platform": "juridico-platform",
    }


@router.get("/")
async def root():
    return {"message": "Juridico Platform API v1.0", "docs": "/docs"}
