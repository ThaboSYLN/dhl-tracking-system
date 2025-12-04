"""
FastAPI endpoints for DHL tracking system
FINAL VERSION - Simple text area input
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks,Query,Path
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import logging
from pydantic import BaseModel


from app.utils.database import get_db
from app.models.schemas import (
    PlainTextBulkRequest, PlainTextExportRequest, TrackingNumberInput, TrackingResponse, BulkTrackingRequest,
    BulkTrackingResponse, ExportRequest, ExportResponse, APIUsageResponse
)
from app.repositories import TrackingRepository, APIUsageRepository, ExportRepository
from app.core.dhl_services import dhl_service
from app.core.file_processor import file_processor
from app.core.export_services import export_service
from app.core.batch_processor import BatchProcessor
from app.utils.config import settings

class ExportFileInfo(BaseModel):
    """Information about an exported file"""
    filename: str
    file_path: str
    created_at: str
    file_size: str
    record_count: int
    export_type: str
    download_url: str

class Config:
     json_schema_extra = {
        "example": {
            "filename": "tracking_report_20240115_103000.pdf",
            "file_path": "./exports/tracking_report_20240115_103000.pdf",
            "created_at": "2024-01-15 10:30:00",
             "file_size": "245 KB",
            "record_count": 5,
            "export_type": "pdf",
            "download_url": "/api/v1/tracking/download/tracking_report_20240115_103000.pdf"
            }
        }


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking", tags=["Tracking"])
batch_processor = BatchProcessor(dhl_service)




@router.get("/single/{tracking_number}", response_model=TrackingResponse, summary="Track Single Shipment")
async def track_single_shipment(
    tracking_number: str,
    bin_id: str = Query(None, description="Optional binID to associate with tracking"),
    db: Session = Depends(get_db)
):
    """
    Track a single DHL shipment by tracking number
    
    **Usage:** `/api/v1/tracking/single/1234567890?bin_id=BIN001`
    
    - **tracking_number**: DHL tracking/waybill number (in URL path)
    - **bin_id**: Optional binID to associate (query parameter)
    """
    try:
        tracking_number = tracking_number.strip().upper()
        
        if not tracking_number or len(tracking_number) < 5:
            raise HTTPException(
                status_code=400,
                detail="Invalid tracking number. Must be at least 5 characters."
            )
        
        tracking_repo = TrackingRepository(db)
        api_usage_repo = APIUsageRepository(db)
        
        if not api_usage_repo.can_make_request(settings.DHL_DAILY_LIMIT):
            raise HTTPException(
                status_code=429,
                detail="Daily API limit reached. Please try again tomorrow."
            )
        
        existing = tracking_repo.get_by_tracking_number(tracking_number)
        if existing and existing.last_checked:
            from datetime import datetime
            age_seconds = (datetime.utcnow() - existing.last_checked).seconds
            if age_seconds < 3600:
                if bin_id and bin_id != existing.bin_id:
                    tracking_repo.update(tracking_number, {'bin_id': bin_id})
                    existing.bin_id = bin_id
                logger.info(f"Returning cached data for {tracking_number}")
                return existing
        
        result = await dhl_service.track_single(tracking_number, bin_id)
        record = tracking_repo.upsert(result)
        api_usage_repo.increment_usage(success=result.get('is_successful', False))
        
        return record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking single shipment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")






@router.post("/bulk", response_model=BulkTrackingResponse, summary="Track Multiple Shipments")
async def track_bulk_shipments(
    request: PlainTextBulkRequest,
    db: Session = Depends(get_db)
):
    """
    Track multiple DHL shipments in a single request
    
    **Simple input - one text area:**
    - Enter one record per line
    - Format: waybill,binID
    - Example:
      ```
      5859187246,BI01FSTD00001002
      2079797893,BI01FSTS00010573
      1010019043,BI01FSTD00001003
      ```
    
    - Maximum 1000 records per request
    """
    try:
        tracking_repo = TrackingRepository(db)
        api_usage_repo = APIUsageRepository(db)
        
        # Get parsed data (already tuples from validator)
        tracking_data = request.tracking_data
        
        remaining = api_usage_repo.get_remaining_requests(settings.DHL_DAILY_LIMIT)
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Daily API limit reached. Please try again tomorrow."
            )
        
        results = await batch_processor.process_batch(
            tracking_data,
            tracking_repo,
            api_usage_repo
        )
        
        return BulkTrackingResponse(
            total_requested=results["total_requested"],
            successful=results["successful"],
            failed=results["failed"],
            results=results["results"],
            batch_id=results["batch_id"],
            processing_time=results["processing_time"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking bulk shipments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



@router.post("/upload", response_model=BulkTrackingResponse, summary="Upload and Track from File")
async def upload_and_track(
    file: UploadFile = File(..., description="CSV or Excel file with tracking numbers and binIDs"),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV or Excel file containing tracking numbers and binIDs
    
    **File Format:**
    - Column A: waybill/tracking_number (required)
    - Column B: binID/bin_id (optional)
    
    **Supported file types:** .csv, .xlsx, .xls
    """
    try:
        tracking_data = await file_processor.process_file(file)
        
        if not tracking_data:
            raise HTTPException(status_code=400, detail="No valid tracking data found in file")
        
        logger.info(f"Extracted {len(tracking_data)} tracking records from {file.filename}")
        
        tracking_repo = TrackingRepository(db)
        api_usage_repo = APIUsageRepository(db)
        
        remaining = api_usage_repo.get_remaining_requests(settings.DHL_DAILY_LIMIT)
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Daily API limit reached. Please try again tomorrow."
            )
        
        results = await batch_processor.process_large_batch(
            tracking_data,
            tracking_repo,
            api_usage_repo
        )
        
        return BulkTrackingResponse(
            total_requested=results["total_requested"],
            successful=results["successful"],
            failed=results["failed"],
            results=results["results"],
            batch_id=results.get("batch_ids", [None])[0],
            processing_time=results["processing_time"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



@router.post("/export", response_model=ExportResponse, summary="Export Tracking Data")
async def export_tracking_data(
    request: PlainTextExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Export tracking data to PDF or DOCX format
    
    **Simple input - one text area:**
    - Enter one record per line
    - Format: waybill,binID
    - Select format from dropdown (PDF or DOCX)
    - Choose whether to include details
    
    Example:
    ```
    5859187246,BI01FSTD00001002
    2079797893,BI01FSTS00010573
    1010019043,BI01FSTD00001003
    ```
    """
    try:
        tracking_repo = TrackingRepository(db)
        export_repo = ExportRepository(db)
        
        # Get parsed data (already tuples from validator)
        tracking_data = request.tracking_data
        
        # Extract waybills for querying
        tracking_numbers = [waybill for waybill, _ in tracking_data]
        
        records = tracking_repo.get_multiple(tracking_numbers)
        
        if not records:
            raise HTTPException(status_code=404, detail="No tracking records found")
        
        # Update binIDs if provided
        records_dict = {r.tracking_number: r for r in records}
        for waybill, bin_id in tracking_data:
            if bin_id and waybill in records_dict:
                record = records_dict[waybill]
                if not record.bin_id or record.bin_id != bin_id:
                    tracking_repo.update(waybill, {'bin_id': bin_id})
                    record.bin_id = bin_id
        
        # Generate export
        if request.format.value == "pdf":
            file_path = export_service.generate_pdf(records, request.include_details)
        else:
            file_path = export_service.generate_docx(records, request.include_details)
        
        export_repo.create({
            "export_type": request.format.value,
            "file_path": file_path,
            "tracking_numbers": tracking_numbers,
            "record_count": len(records)
        })
        
        background_tasks.add_task(export_service.cleanup_old_exports, days=7)
        
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
        logger.error(f"Error exporting tracking data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")





@router.get("/exports/recent", summary="List Recent Export Files")
async def list_recent_exports(
    limit: int = Query(default=10, ge=1, le=50, description="Number of files to show"),
    db: Session = Depends(get_db)
):
    """Get a list of recently exported files"""
    try:
        export_repo = ExportRepository(db)
        recent_exports = export_repo.get_recent(limit)
        
        if not recent_exports:
            return {
                "total": 0,
                "exports": [],
                "message": "No export files found"
            }
        
        export_files = []
        for export in recent_exports:
            import os
            file_path = export.file_path
            
            if not os.path.exists(file_path):
                continue
            
            file_stats = os.stat(file_path)
            file_size_bytes = file_stats.st_size
            
            if file_size_bytes < 1024:
                file_size = f"{file_size_bytes} B"
            elif file_size_bytes < 1024 * 1024:
                file_size = f"{file_size_bytes / 1024:.1f} KB"
            else:
                file_size = f"{file_size_bytes / (1024 * 1024):.1f} MB"
            
            filename = os.path.basename(file_path)
            
            export_files.append(ExportFileInfo(
                filename=filename,
                file_path=file_path,
                created_at=export.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                file_size=file_size,
                record_count=export.record_count,
                export_type=export.export_type,
                download_url=f"/api/v1/tracking/download/{filename}"
            ))
        
        return {
            "total": len(export_files),
            "exports": export_files,
            "message": f"Found {len(export_files)} export file(s)"
        }
        
    except Exception as e:
        logger.error(f"Error listing exports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list exports: {str(e)}")


@router.get("/download/{filename}", summary="Download Export File")
async def download_export_file(filename: str):
    """Download an exported tracking report"""
    import os
    file_path = os.path.join(settings.EXPORT_DIR, filename)
    
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404, 
            detail=f"File not found. Use /api/v1/tracking/exports/recent to see available files."
        )
    
    if filename.endswith('.pdf'):
        media_type = 'application/pdf'
    elif filename.endswith('.docx'):
        media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


@router.get("/download/latest/{export_type}", summary="Download Most Recent Export")
async def download_latest_export(
    export_type: str = Path(..., regex="^(pdf|docx)$", description="File type to download"),
    db: Session = Depends(get_db)
):
    """Download the most recently created export file of specified type"""
    try:
        export_repo = ExportRepository(db)
        exports = export_repo.get_by_type(export_type)
        
        if not exports:
            raise HTTPException(
                status_code=404,
                detail=f"No {export_type.upper()} exports found"
            )
        
        latest_export = exports[0]
        
        import os
        file_path = latest_export.file_path
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail="File was deleted or moved"
            )
        
        filename = os.path.basename(file_path)
        
        if export_type == 'pdf':
            media_type = 'application/pdf'
        else:
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading latest export: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{tracking_number}", response_model=TrackingResponse, summary="Get Tracking History")
async def get_tracking_history(tracking_number: str, db: Session = Depends(get_db)):
    """Get stored tracking history for a specific tracking number"""
    tracking_repo = TrackingRepository(db)
    record = tracking_repo.get_by_tracking_number(tracking_number.upper())
    
    if not record:
        raise HTTPException(status_code=404, detail="Tracking number not found in database")
    
    return record


@router.get("/usage", response_model=APIUsageResponse, summary="Get API Usage Statistics")
async def get_api_usage(db: Session = Depends(get_db)):
    """Get current API usage statistics for today"""
    api_usage_repo = APIUsageRepository(db)
    usage = api_usage_repo.get_or_create_today()
    remaining = api_usage_repo.get_remaining_requests(settings.DHL_DAILY_LIMIT)
    percentage = (usage.request_count / settings.DHL_DAILY_LIMIT) * 100
    
    return APIUsageResponse(
        date=usage.date,
        requests_used=usage.request_count,
        requests_remaining=remaining,
        daily_limit=settings.DHL_DAILY_LIMIT,
        percentage_used=round(percentage, 2)
    )

