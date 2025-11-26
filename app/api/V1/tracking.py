"""
FastAPI endpoints for DHL tracking system
Implements REST API following best practices
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import logging

from app.utils.database import get_db
from app.models.schemas import (
    TrackingNumberInput, TrackingResponse, BulkTrackingRequest,
    BulkTrackingResponse, ExportRequest, ExportResponse, APIUsageResponse
)
from app.repositories import TrackingRepository, APIUsageRepository, ExportRepository
from app.core.dhl_services import dhl_service
from app.core.file_processor import file_processor
from app.core.export_services import export_service
from app.core.batch_processor import BatchProcessor
from app.utils.config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/tracking", tags=["Tracking"])

# Initialize batch processor
batch_processor = BatchProcessor(dhl_service)




@router.get("/single/{tracking_number}", response_model=TrackingResponse, summary="Track Single Shipment")
async def track_single_shipment(
    tracking_number: str,
    db: Session = Depends(get_db)
):
    """
    Track a single DHL shipment by tracking number
    
    **Usage:** Simply add the tracking number to the URL
    
    **Example:** `/api/v1/tracking/single/1234567890`
    
    - **tracking_number**: DHL tracking/waybill number (in URL path)
    
    Returns detailed tracking information including:
    - Current status
    - Origin and destination
    - Tracking timeline
    """
    try:
        # Clean and validate tracking number
        tracking_number = tracking_number.strip().upper()
        
        if not tracking_number or len(tracking_number) < 5:
            raise HTTPException(
                status_code=400,
                detail="Invalid tracking number. Must be at least 5 characters."
            )
        
        tracking_repo = TrackingRepository(db)
        api_usage_repo = APIUsageRepository(db)
        
        # Check rate limits
        if not api_usage_repo.can_make_request(settings.DHL_DAILY_LIMIT):
            raise HTTPException(
                status_code=429,
                detail="Daily API limit reached. Please try again tomorrow."
            )
        
        # Check if we have recent cached data
        existing = tracking_repo.get_by_tracking_number(tracking_number)
        if existing and existing.last_checked:
            from datetime import datetime
            age_seconds = (datetime.utcnow() - existing.last_checked).seconds
            if age_seconds < 3600:  # Less than 1 hour old
                logger.info(f"Returning cached data for {tracking_number}")
                return existing
        
        # Fetch from DHL API
        result = await dhl_service.track_single(tracking_number)
        
        # Save to database
        record = tracking_repo.upsert(result)
        
        # Update API usage
        api_usage_repo.increment_usage(success=result.get('is_successful', False))
        
        return record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking single shipment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")






@router.post("/bulk", response_model=BulkTrackingResponse, summary="Track Multiple Shipments")
async def track_bulk_shipments(
    request: PlainTextBulkRequest,  # Changed from BulkTrackingRequest
    db: Session = Depends(get_db)
):
    """
    Track multiple DHL shipments in a single request
    
    **How to use:**
    - Enter tracking numbers in plain text
    - Put each tracking number on a new line
    - System automatically removes duplicates and empty lines
    
    **Example input:**
    ```
    1234567890
    0987654321
    1122334455
    ```
    
    - Maximum 1000 tracking numbers per request
    - Intelligently batches requests to optimize API usage
    - Uses caching to minimize API calls for recently checked shipments
    """
    try:
        tracking_repo = TrackingRepository(db)
        api_usage_repo = APIUsageRepository(db)
        
        # Get the parsed tracking numbers from the validator
        tracking_numbers = request.tracking_numbers_text
        
        # Check rate limits
        remaining = api_usage_repo.get_remaining_requests(settings.DHL_DAILY_LIMIT)
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Daily API limit reached. Please try again tomorrow."
            )
        
        # Process batch
        results = await batch_processor.process_batch(
            tracking_numbers,
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
    file: UploadFile = File(..., description="CSV or Excel file with tracking numbers"),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV or Excel file containing tracking numbers and process them
    
    - **file**: CSV or Excel file (.csv, .xlsx, .xls)
    - File should contain a column named 'tracking_number', 'waybill', or similar
    - If no matching column is found, the first column will be used
    
    The system will:
    1. Extract tracking numbers from the file
    2. Remove duplicates
    3. Batch process them intelligently
    4. Return detailed results
    """
    try:
        # Process file to extract tracking numbers
        tracking_numbers = await file_processor.process_file(file)
        
        if not tracking_numbers:
            raise HTTPException(status_code=400, detail="No valid tracking numbers found in file")
        
        logger.info(f"Extracted {len(tracking_numbers)} tracking numbers from {file.filename}")
        
        # Process as bulk request
        tracking_repo = TrackingRepository(db)
        api_usage_repo = APIUsageRepository(db)
        
        # Check rate limits
        remaining = api_usage_repo.get_remaining_requests(settings.DHL_DAILY_LIMIT)
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Daily API limit reached. Please try again tomorrow."
            )
        
        # Process batch
        results = await batch_processor.process_large_batch(
            tracking_numbers,
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
    request: PlainTextExportRequest,  # Changed from ExportRequest
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Export tracking data to PDF or DOCX format
    
    **How to use:**
    - Enter tracking numbers in plain text (one per line)
    - Select format (pdf or docx)
    - Choose whether to include detailed information
    
    **Example input:**
    ```
    1234567890
    0987654321
    1122334455
    ```
    
    Returns a downloadable file with the tracking information formatted in a table.
    """
    try:
        tracking_repo = TrackingRepository(db)
        export_repo = ExportRepository(db)
        
        # Get parsed tracking numbers from validator
        tracking_numbers = request.tracking_numbers_text
        
        # Get tracking records
        records = tracking_repo.get_multiple(tracking_numbers)
        
        if not records:
            raise HTTPException(status_code=404, detail="No tracking records found")
        
        # Generate export file
        if request.format == "pdf":
            file_path = export_service.generate_pdf(records, request.include_details)
        else:  # docx
            file_path = export_service.generate_docx(records, request.include_details)
        
        # Save export history
        export_repo.create({
            "export_type": request.format,
            "file_path": file_path,
            "tracking_numbers": tracking_numbers,
            "record_count": len(records)
        })
        
        # Schedule cleanup of old exports
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




@router.get("/download/{filename}", summary="Download Export File")
async def download_export_file(filename: str):
    """
    Download an exported tracking report
    
    - **filename**: Name of the file to download
    """
    import os
    file_path = os.path.join(settings.EXPORT_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type
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


@router.get("/history/{tracking_number}", response_model=TrackingResponse, summary="Get Tracking History")
async def get_tracking_history(tracking_number: str, db: Session = Depends(get_db)):
    """
    Get stored tracking history for a specific tracking number
    
    - **tracking_number**: DHL tracking/waybill number
    
    Returns cached tracking information without making a new API call.
    """
    tracking_repo = TrackingRepository(db)
    record = tracking_repo.get_by_tracking_number(tracking_number.upper())
    
    if not record:
        raise HTTPException(status_code=404, detail="Tracking number not found in database")
    
    return record


@router.get("/usage", response_model=APIUsageResponse, summary="Get API Usage Statistics")
async def get_api_usage(db: Session = Depends(get_db)):
    """
    Get current API usage statistics for today
    
    Shows:
    - Requests used today
    - Requests remaining
    - Daily limit
    - Percentage used
    """
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

