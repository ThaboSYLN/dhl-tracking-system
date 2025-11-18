"""
Tracking API Endpoints
Follows Interface Segregation Principle - clean, focused API interface
"""
import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.config import get_settings, Settings
from app.models.schemas import (
    WaybillRequest,
    TrackingInfo,
    BulkTrackingResponse,
    HealthResponse
)
from app.core.dhl_services import DHLAPIService
from app.core.file_processor import FileProcessorService
from app.repositories.tracking_repository import (
    TrackingRepository,
    APIUsageRepository
)

router = APIRouter(prefix="/tracking", tags=["Tracking"])


@router.post(
    "/single",
    response_model=TrackingInfo,
    summary="Track single shipment",
    description="Track a single shipment using waybill/tracking number"
)
async def track_single_shipment(
    request: WaybillRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Track a single DHL shipment
    
    - *waybill_number*: DHL tracking or waybill number
    """
    start_time = time.time()
    
    # Check API usage limits
    usage_repo = APIUsageRepository(db)
    can_request = await usage_repo.can_make_requests(1, settings.DHL_DAILY_LIMIT)
    
    if not can_request:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily API limit reached. Please try again tomorrow."
        )
    
    # Track shipment
    async with DHLAPIService(settings) as dhl_service:
        tracking_info = await dhl_service.track_single_shipment(request.waybill_number)
    
    # Save to database
    tracking_repo = TrackingRepository(db)
    await tracking_repo.create_or_update_tracking(tracking_info)
    
    # Log API usage
    response_time = int((time.time() - start_time) * 1000)
    await usage_repo.log_api_usage(
        endpoint="/tracking/single",
        waybill_count=1,
        success=not tracking_info.error_message,
        response_time_ms=response_time,
        error_message=tracking_info.error_message
    )
    
    await db.commit()
    
    return tracking_info


@router.post(
    "/bulk",
    response_model=BulkTrackingResponse,
    summary="Track multiple shipments",
    description="Track multiple shipments by uploading CSV or Excel file"
)
async def track_bulk_shipments(
    file: UploadFile = File(..., description="CSV or Excel file with waybill numbers"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Track multiple DHL shipments from uploaded file
    
    - *file*: CSV or Excel file containing waybill numbers
    - File must have a column named: 'waybill', 'tracking_number', 'tracking', or 'awb'
    - Maximum 250 waybills per file (DHL daily limit)
    """
    start_time = time.time()
    
    # Extract waybills from file
    waybill_numbers = await FileProcessorService.extract_waybills_from_file(file)
    
    # Check API usage limits
    usage_repo = APIUsageRepository(db)
    can_request = await usage_repo.can_make_requests(
        len(waybill_numbers),
        settings.DHL_DAILY_LIMIT
    )
    
    if not can_request:
        requests_used = await usage_repo.get_today_request_count()
        remaining = settings.DHL_DAILY_LIMIT - requests_used
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Not enough API quota. Requested: {len(waybill_numbers)}, Remaining: {remaining}"
        )
    
    # Track all shipments with batching
    async with DHLAPIService(settings) as dhl_service:
        results = await dhl_service.track_multiple_shipments(
            waybill_numbers,
            batch_size=settings.BATCH_SIZE,
            delay_between_batches=settings.BATCH_DELAY
        )
    
    # Save to database
    tracking_repo = TrackingRepository(db)
    await tracking_repo.bulk_create_or_update(results)
    
    # Log API usage
    successful = sum(1 for r in results if not r.error_message)
    failed = len(results) - successful
    response_time = int((time.time() - start_time) * 1000)
    
    await usage_repo.log_api_usage(
        endpoint="/tracking/bulk",
        waybill_count=len(results),
        success=True,
        response_time_ms=response_time
    )
    
    await db.commit()
    
    # Prepare response
    return BulkTrackingResponse(
        total_processed=len(results),
        successful=successful,
        failed=failed,
        results=results,
        processing_time_seconds=round(time.time() - start_time, 2)
    )


@router.get(
    "/history/{waybill_number}",
    response_model=TrackingInfo,
    summary="Get tracking history",
    description="Retrieve tracking information from database"
)
async def get_tracking_history(
    waybill_number: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get tracking history from database (no API call)
    
    - *waybill_number*: DHL tracking or waybill number
    """
    tracking_repo = TrackingRepository(db)
    record = await tracking_repo.get_tracking_by_waybill(waybill_number.upper())
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tracking history found for waybill: {waybill_number}"
        )
    
    return TrackingInfo(
        waybill_number=record.waybill_number,
        status_code=record.status_code,
        status=record.status,
        origin=record.origin,
        destination=record.destination,
        last_updated=record.last_updated,
        error_message=record.error_message
    )


@router.get(
    "/history",
    response_model=List[TrackingInfo],
    summary="Get all tracking history",
    description="Retrieve all tracking records from database"
)
async def get_all_tracking_history(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all tracking history with pagination
    
    - *limit*: Maximum number of records to return (default: 100)
    - *offset*: Number of records to skip (default: 0)
    """
    tracking_repo = TrackingRepository(db)
    records = await tracking_repo.get_all_trackings(limit, offset)
    
    return [
        TrackingInfo(
            waybill_number=record.waybill_number,
            status_code=record.status_code,
            status=record.status,
            origin=record.origin,
            destination=record.destination,
            last_updated=record.last_updated,
            error_message=record.error_message
        )
        for record in records
    ]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check API health and usage statistics"
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Health check endpoint
    
    Returns system status and API usage information
    """
    usage_repo = APIUsageRepository(db)
    requests_today = await usage_repo.get_today_request_count()
    
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        timestamp=time.time(),
        database_connected=True,
        api_requests_today=requests_today,
        api_limit_remaining=settings.DHL_DAILY_LIMIT - requests_today
    )