"""
Repository package
Exports all repository classes for easy importing
"""
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from app.models.database import TrackingRecord, APIUsage, ExportHistory


class TrackingRepository:
    """Repository for TrackingRecord operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, tracking_data: Dict[str, Any]) -> TrackingRecord:
        record = TrackingRecord(**tracking_data)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_by_tracking_number(self, tracking_number: str) -> Optional[TrackingRecord]:
        return self.db.query(TrackingRecord).filter(
            TrackingRecord.tracking_number == tracking_number
        ).first()
    
    def get_multiple(self, tracking_numbers: List[str]) -> List[TrackingRecord]:
        return self.db.query(TrackingRecord).filter(
            TrackingRecord.tracking_number.in_(tracking_numbers)
        ).all()
    
    def update(self, tracking_number: str, update_data: Dict[str, Any]) -> Optional[TrackingRecord]:
        record = self.get_by_tracking_number(tracking_number)
        if record:
            for key, value in update_data.items():
                setattr(record, key, value)
            record.updated_at = datetime.utcnow()
            record.last_checked = datetime.utcnow()
            self.db.commit()
            self.db.refresh(record)
        return record
    
    def upsert(self, tracking_data: Dict[str, Any]) -> TrackingRecord:
        tracking_number = tracking_data.get('tracking_number')
        existing = self.get_by_tracking_number(tracking_number)
        if existing:
            return self.update(tracking_number, tracking_data)
        else:
            return self.create(tracking_data)
    
    def bulk_upsert(self, tracking_data_list: List[Dict[str, Any]]) -> List[TrackingRecord]:
        results = []
        for tracking_data in tracking_data_list:
            record = self.upsert(tracking_data)
            results.append(record)
        return results
    
    def get_by_batch_id(self, batch_id: str) -> List[TrackingRecord]:
        return self.db.query(TrackingRecord).filter(
            TrackingRecord.batch_id == batch_id
        ).all()
    
    def get_recent(self, limit: int = 100) -> List[TrackingRecord]:
        return self.db.query(TrackingRecord).order_by(
            TrackingRecord.created_at.desc()
        ).limit(limit).all()
    
    def count_all(self) -> int:
        return self.db.query(TrackingRecord).count()
    
    def delete(self, tracking_number: str) -> bool:
        record = self.get_by_tracking_number(tracking_number)
        if record:
            self.db.delete(record)
            self.db.commit()
            return True
        return False


class APIUsageRepository:
    """Repository for API usage tracking"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_today(self) -> APIUsage:
        today = date.today().isoformat()
        usage = self.db.query(APIUsage).filter(APIUsage.date == today).first()
        if not usage:
            usage = APIUsage(date=today, request_count=0)
            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)
        return usage
    
    def increment_usage(self, success: bool = True) -> APIUsage:
        usage = self.get_or_create_today()
        usage.request_count += 1
        if success:
            usage.successful_requests += 1
        else:
            usage.failed_requests += 1
        usage.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(usage)
        return usage
    
    def get_remaining_requests(self, daily_limit: int = 250) -> int:
        usage = self.get_or_create_today()
        return max(0, daily_limit - usage.request_count)
    
    def can_make_request(self, daily_limit: int = 250) -> bool:
        return self.get_remaining_requests(daily_limit) > 0
    
    def get_usage_stats(self, days: int = 7) -> List[APIUsage]:
        return self.db.query(APIUsage).order_by(
            APIUsage.date.desc()
        ).limit(days).all()


class ExportRepository:
    """Repository for export history"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, export_data: Dict[str, Any]) -> ExportHistory:
        export = ExportHistory(**export_data)
        self.db.add(export)
        self.db.commit()
        self.db.refresh(export)
        return export
    
    def get_recent(self, limit: int = 50) -> List[ExportHistory]:
        return self.db.query(ExportHistory).order_by(
            ExportHistory.created_at.desc()
        ).limit(limit).all()
    
    def get_by_type(self, export_type: str) -> List[ExportHistory]:
        return self.db.query(ExportHistory).filter(
            ExportHistory.export_type == export_type
        ).order_by(ExportHistory.created_at.desc()).all()


__all__ = [
    'TrackingRepository',
    'APIUsageRepository',
    'ExportRepository'
]

