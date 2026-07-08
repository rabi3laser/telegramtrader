"""
FASTAPI BACKEND - TELEGRAMTRADER
Point d'entrée principal de l'application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.core.config import settings
from app.api import telegram, channels, trading, market_data, dashboard, nt8_agent, ws_connector

# Créer l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API Backend pour TelegramTrader - Pipeline Trading Multi-Marchés",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure les routers
app.include_router(telegram.router, prefix="/api/telegram", tags=["Telegram"])
app.include_router(channels.router, prefix="/api/channels", tags=["Channels"])
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(market_data.router, prefix="/api/market-data", tags=["Market Data"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(nt8_agent.router, prefix="/api/nt8-agent", tags=["NT8 Agent"])
# WebSocket — pas de prefix /api car les WS ont leur propre namespace
app.include_router(ws_connector.router, tags=["WebSocket"])

# Route racine
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/api/docs",
    }

# Route de santé
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Gestionnaire d'erreurs global
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
