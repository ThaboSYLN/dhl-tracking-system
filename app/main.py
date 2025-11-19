"""
Main FastAPI application
Entry point for the DHL Tracking System
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from app.utils.config import settings
from app.utils.database import init_db
from app.api.V1 import tracking, export
from app.models.schemas import HealthCheckResponse
from app.core.dhl_services import dhl_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    Handles startup and shutdown tasks
    """
    # Startup
    logger.info("🚀 Starting DHL Tracking System...")
    
    # Initialize database
    init_db()
    logger.info("✅ Database initialized")
    
    # Test DHL API connection
    api_available = await dhl_service.test_connection()
    if api_available:
        logger.info("✅ DHL API connection successful")
    else:
        logger.warning("⚠️ DHL API connection failed - check API key")
    
    logger.info(f"🌐 API running at {settings.HOST}:{settings.PORT}")
    logger.info(f"📚 Documentation available at http://{settings.HOST}:{settings.PORT}/docs")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down DHL Tracking System...")


# Create FastAPI application
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
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "type": type(exc).__name__
        }
    )


# Include routers
app.include_router(tracking.router, prefix=settings.API_V1_PREFIX)
app.include_router(export.router, prefix=settings.API_V1_PREFIX)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "DHL Tracking System API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns system status and connectivity information
    """
    from app.utils.database import engine
    
    # Check database connection
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        db_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_connected = False
    
    # Check DHL API
    api_available = await dhl_service.test_connection()
    
    status = "healthy" if (db_connected and api_available) else "degraded"
    
    return HealthCheckResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=settings.APP_VERSION,
        database_connected=db_connected,
        api_available=api_available
    )


# Additional utility endpoints
@app.get("/api/v1/stats", tags=["Statistics"])
async def get_statistics():
    """
    Get overall system statistics
    """
    from app.utils.database import get_db_context
    from app.repositories import TrackingRepository, APIUsageRepository
    
    with get_db_context() as db:
        tracking_repo = TrackingRepository(db)
        api_usage_repo = APIUsageRepository(db)
        
        total_records = tracking_repo.count_all()
        usage = api_usage_repo.get_or_create_today()
        remaining = api_usage_repo.get_remaining_requests(settings.DHL_DAILY_LIMIT)
        
        return {
            "total_tracking_records": total_records,
            "api_requests_today": usage.request_count,
            "api_requests_remaining": remaining,
            "successful_requests_today": usage.successful_requests,
            "failed_requests_today": usage.failed_requests
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

