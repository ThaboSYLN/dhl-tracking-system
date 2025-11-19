"""
Dependency injection utilities
Provides commonly used dependencies for FastAPI endpoints
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.utils.database import get_db
from app.repositories import TrackingRepository, APIUsageRepository, ExportRepository
from app.core.dhl_services import dhl_service, DHLAPIService
from app.core.file_processor import file_processor, FileProcessor
from app.core.export_services import export_service, ExportService
from app.core.batch_processor import BatchProcessor


# Repository dependencies
def get_tracking_repository(db: Session = Depends(get_db)) -> TrackingRepository:
    """Get tracking repository instance"""
    return TrackingRepository(db)


def get_api_usage_repository(db: Session = Depends(get_db)) -> APIUsageRepository:
    """Get API usage repository instance"""
    return APIUsageRepository(db)


def get_export_repository(db: Session = Depends(get_db)) -> ExportRepository:
    """Get export repository instance"""
    return ExportRepository(db)


# Service dependencies
def get_dhl_service() -> DHLAPIService:
    """Get DHL API service instance"""
    return dhl_service


def get_file_processor() -> FileProcessor:
    """Get file processor instance"""
    return file_processor


def get_export_service() -> ExportService:
    """Get export service instance"""
    return export_service


def get_batch_processor(
    dhl_svc: DHLAPIService = Depends(get_dhl_service)
) -> BatchProcessor:
    """Get batch processor instance"""
    return BatchProcessor(dhl_svc)

