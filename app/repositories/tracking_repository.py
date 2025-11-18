"""Repository Pattern---Data Access layer"""

from typing import List,Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import TrackingRecord,APIUsageLog,ExportHistory
from app.models.schemas import TrackingInfo

class TrackingRepository:
    """repo for tracking records
    trying to encapsulate  all database ops for tracking
    """

    def __init__(self,db:AsyncSession):
        self.db = db

    async def create_or_update_tracking(self,tracking_info:TrackingInfo)-> TrackingRecord:
        """Create or update and save then return the saved result :)"""
        #semantic method 
        stmt = select(TrackingRecord).where(
            TrackingRecord.waybill_number==tracking_info.waybill_number
        )    
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.status_code = tracking_info.status_code
            existing.status = tracking_info.status
            existing.origin = tracking_info.origin
            existing.destination = tracking_info.destination
            existing.last_updated = tracking_info.last_updated
            existing.error_message  = tracking_info.error_message
            existing.updated_at = datetime.utcnow()
            return existing
        else:
            """Make new record now """
            new_record = TrackingRecord(
                waybill_number = tracking_info.waybill_number,
                status_code = tracking_info.status_code,
                status = tracking_info.status,
                origin = tracking_info.origin,
                destination = tracking_info.destination,
                last_updated = tracking_info.last_updated,
                error_message = tracking_info.error_message
            )
            self.db.add(new_record) # adding new record to the database 
            await self.db.flush()
            return new_record
        
    async def get_tracking_by_waybill(self,waybill_number:str)->Optional[TrackingRecord]:
        """Get by waybill/Search by waybill"""
        stmt = select(TrackingRecord).where(
            TrackingRecord.waybill_number==waybill_number
        )    
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_trackings(self,limit:int =100, offset:int  = 10) -> List[TrackingRecord]:
        """We getting then app-- Processed """
        stmt = select(TrackingRecord).limit(limit).offset(offset).order_by(
           TrackingRecord.updated_at.desc() 
        )
        result = await self.db.execute(stmt)
        return result.scalar().all()
    
    async def bulk_create_or_update(self,tracking_list: List[TrackingInfo])->List[TrackingRecord]:
        """Bulk create or update tracking record---efficient for larger data sets"""

        records = []
        for tracking_info in tracking_list:
            records = await self.create_or_update_tracking(tracking_info)
            records.append(records)
        return records 


class APIUsageRepositiry:
    """Repo Loggin to keep track daily api limits"""

    def __init__(self,db:AsyncSession):
        self.db = db

    async def log_api_usage(
            self,
            endpoint:str,
            waybill_count:int = 1,
            success: bool = True,
            response_time_ms:Optional[int] = None,
            error_message:Optional[str] = None
    )->APIUsageLog:
      log = APIUsageLog(
      endpoint = endpoint,
      waybill_count = waybill_count,
      success = success,
     response_time_ms = response_time_ms,
     error_message = error_message
    )
      self.db.add(log)
      await self.db.flush()
      return log
    
    async def get_today_requests_count(self)-> int:
        """total api calls for the day"""
        today_start = datetime.utcnow().replace(hour=0,minute=0,second=0,microsecond=0)
        stmt = select(func.sum(APIUsageLog.waybill_count)).where(
            and_(
                APIUsageLog.created_at >=today_start,
                APIUsageLog.success==True
            )
        )
        result = await self.db.execute(stmt)
        count = result.scalar()
        return count or 0
    
    async def can_make_requests(self,count:int , daily_limit:int = 250)->bool:
        today_count = await self.get_today_requests_count()
        return (today_count+count)<=daily_limit
    
class ExportRepository:
    """Save history of export log"""

    def __init(self,db:AsyncSession):
        self.db = db

    async def log_export(
            self,
            export_format:str,
            waybill_count:int,
            file_path:Optional[str]=None,
            file_size_bytes:Optional[int]=None
    )-> ExportHistory:
        export_log=ExportHistory(
            export_format = export_format,
            waybill_count = waybill_count,
            file_path = file_path,
            file_size_bytes = file_size_bytes
        )
        self.db.add(export_log)
        await self.db.flush()
        return export_log
    
    async def get_recent_export(self,limit:int  = 10)-> List[ExportHistory]:
        stmt = select(ExportHistory).limit(limit).order_by(
            ExportHistory.created_at.desc()
        )
        result = await self.db.execute(stmt)
        return result.scaler().all()
    
    
        
    
        




