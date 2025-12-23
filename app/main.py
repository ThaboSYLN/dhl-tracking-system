"""
Main FastAPI application
Entry point for the DHL Tracking System
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import os

# Local imports
from app.utils.config import settings
from app.utils.database import init_db
from app.api.V1 import tracking, export, automation_api
from app.models.schemas import HealthCheckResponse
from app.core.dhl_services import dhl_service


# =====================================================================
# 1. CREATE ONE (1) FASTAPI APP — this must appear only once
# =====================================================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## DHL Tracking System API
    
    A professional tracking system for DHL shipments with the following features:
    
    ### Features
    * 🔍 **Single Tracking**: Track individual shipments
    * 📦 **Bulk Tracking**: Track multiple shipments at once
    * 📁 **File Upload**: Process CSV/Excel files with tracking numbers
    * 📄 **Export**: Generate PDF and DOCX reports
    * 💾 **Smart Caching**: Minimize API calls with intelligent caching
    * 📊 **Usage Tracking**: Monitor API usage and rate limits
    * ⚡ **Batch Processing**: Intelligent batching for optimal performance
    
    ### Rate Limits
    - DHL API: 250 requests per day
    - Batch size: 25 tracking numbers per batch
    - Smart caching: Reuses data less than 1 hour old
    
    ### Getting Started
    1. Configure your DHL API key in `.env` file
    2. Use `/docs` for interactive API documentation
    3. Start with `/api/v1/tracking/single` for single tracking
    4. Use `/api/v1/tracking/upload` for bulk file processing
    
    ### Support
    For issues or questions, please refer to the documentation.
    """,
    #lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# =====================================================================
# 2. SERVE UI (HTML/CSS/JS)
# =====================================================================

# Path to UI directory
UI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "UI")

# Serve static files under /ui/*
app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

# Serve index.html at root "/"
@app.get("/")
def serve_index():
    return FileResponse(os.path.join(UI_DIR, "index.html"))


# =====================================================================
# 3. LOGGING CONFIG
# =====================================================================
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =====================================================================
# 4. APPLICATION LIFESPAN (startup + shutdown)
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting DHL Tracking System...")

    # Initialize DB
    init_db()
    logger.info("✅ Database initialized")

    # Test DHL connection
    api_available = await dhl_service.test_connection()
    if api_available:
        logger.info("✅ DHL API connection successful")
    else:
        logger.warning("⚠️ DHL API connection failed")

    logger.info(f"🌐 API running at {settings.HOST}:{settings.PORT}")
    logger.info(f"📚 Docs: http://{settings.HOST}:{settings.PORT}/docs")

    yield

    logger.info("👋 Shutting down DHL Tracking System...")


app.router.lifespan_context = lifespan


# =====================================================================
# 5. CORS
# =====================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# 6. API ROOT ENDPOINT (MOVED TO /api)
# =====================================================================
@app.get("/api", tags=["Root"])
async def api_root(request: Request):
    base = str(request.base_url).rstrip("/")
    return {
        "message": "DHL Tracking System API",
        "version": settings.APP_VERSION,
        "docs": f"{base}/docs",
        "redoc": f"{base}/redoc",
        "health": f"{base}/health",
        "openapi": f"{base}/openapi.json"
    }


# =====================================================================
# 7. HEALTH CHECK
# =====================================================================
@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    from app.utils.database import engine

    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception as e:
        logger.error(f"DB health check failed: {str(e)}")
        db_ok = False

    dhl_ok = await dhl_service.test_connection()

    status = "healthy" if (db_ok and dhl_ok) else "degraded"

    return HealthCheckResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=settings.APP_VERSION,
        database_connected=db_ok,
        api_available=dhl_ok
    )


# =====================================================================
# 8. ROUTERS
# =====================================================================
app.include_router(automation_api.router, prefix=settings.API_V1_PREFIX)
app.include_router(tracking.router, prefix=settings.API_V1_PREFIX)
app.include_router(export.router, prefix=settings.API_V1_PREFIX)


# =====================================================================
# 9. ERROR HANDLER
# =====================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "type": type(exc).__name__
        }
    )
