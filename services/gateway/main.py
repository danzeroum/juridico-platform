"""
API Gateway - Ponto de entrada da plataforma
Roteia requests para os microservicos de cada produto
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import logging

from gateway.routers import health, auth, legalscore, contabilia, taxpredict, compliance
from gateway.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from shared.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Juridico Platform Gateway iniciando...")
    yield
    logger.info("Gateway encerrando...")


app = FastAPI(
    title="Juridico Platform API",
    description="Plataforma Juridico-Contabil Docker-First - 8 produtos de IA",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# --- Middlewares ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# --- Prometheus metrics ---
Instrumentator().instrument(app).expose(app)

# --- Routers ---
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(legalscore.router, prefix="/v1", tags=["LegalScore PJ"])
app.include_router(contabilia.router, prefix="/v1", tags=["ContabilIA"])
app.include_router(taxpredict.router, prefix="/v1", tags=["TaxPredict"])
app.include_router(compliance.router, prefix="/v1", tags=["ComplianceRadar"])
