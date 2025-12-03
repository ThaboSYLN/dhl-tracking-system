"""
Additional export endpoints for flexibility

CHANGES MADE (MINIMAL):
1. export_recent_records: Changed format from regex string to ExportFormat enum (Line 18)
2. export_batch_results: Changed format from regex string to ExportFormat enum (Line 73)
   Now users see DROPDOWN instead of typing text
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from app.utils.database import get_db
from app.models.schemas import ExportResponse, ExportFormat  # Import ExportFormat enum
from app.repositories import TrackingRepository, ExportRepository
from app.core.export_services import export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/recent", summary="Export Recent Tracking Records")
async def export_recent_records(
    limit: int = Query(default=50, ge=1, le=500, description="Number of recent records"),
    format: ExportFormat = Query(default=ExportFormat.PDF, description="Export format"),  # CHANGED: Now enum dropdown
    db: Session = Depends(get_db)
):
    """
    Export the most recent tracking records
    
    - **limit**: Number of records to export (1-500)
    - **format**: Export format (select from dropdown)
    """
    try:
        tracking_repo = TrackingRepository(db)
        export_repo = ExportRepository(db)
        
        # Get recent records
        records = tracking_repo.get_recent(limit)
        
        if not records:
            raise HTTPException(status_code=404, detail="No tracking records found")
        
        # Generate export (format.value gives "pdf" or "docx")
        if format == ExportFormat.PDF:
            file_path = export_service.generate_pdf(records, include_details=True)
        else:
            file_path = export_service.generate_docx(records, include_details=True)
        
        # Save export history
        tracking_numbers = [r.tracking_number for r in records]
        export_repo.create({
            "export_type": format.value,  # .value converts enum to string
            "file_path": file_path,
            "tracking_numbers": tracking_numbers,
            "record_count": len(records)
        })
        
        import os
        file_name = os.path.basename(file_path)
        
        return ExportResponse(
            success=True,
            file_path=file_path,
            file_name=file_name,
            download_url=f"/api/v1/tracking/download/{file_name}",
            record_count=len(records)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting recent records: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_id}", summary="Export Batch Results")
async def export_batch_results(
    batch_id: str,
    format: ExportFormat = Query(default=ExportFormat.PDF, description="Export format"),  # CHANGED: Now enum dropdown
    db: Session = Depends(get_db)
):
    """
    Export all records from a specific batch
    
    - **batch_id**: Batch ID from bulk tracking operation
    - **format**: Export format (select from dropdown)
    """
    try:
        tracking_repo = TrackingRepository(db)
        export_repo = ExportRepository(db)
        
        # Get batch records
        records = tracking_repo.get_by_batch_id(batch_id)
        
        if not records:
            raise HTTPException(status_code=404, detail=f"No records found for batch {batch_id}")
        
        # Generate export
        if format == ExportFormat.PDF:
            file_path = export_service.generate_pdf(records, include_details=True)
        else:
            file_path = export_service.generate_docx(records, include_details=True)
        
        # Save export history
        tracking_numbers = [r.tracking_number for r in records]
        export_repo.create({
            "export_type": format.value,
            "file_path": file_path,
            "tracking_numbers": tracking_numbers,
            "record_count": len(records)
        })
        
        import os
        file_name = os.path.basename(file_path)
        
        return ExportResponse(
            success=True,
            file_path=file_path,
            file_name=file_name,
            download_url=f"/api/v1/tracking/download/{file_name}",
            record_count=len(records)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

