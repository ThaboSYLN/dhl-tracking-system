"""
Repository pattern for tracking records
Separates data access logic from business logic
Follows Single Responsibility Principle
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from app.models.database import TrackingRecord, APIUsage, ExportHistory


class TrackingRepository:
    """
    Repository for TrackingRecord operations
    Encapsulates all database queries for tracking records
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, tracking_data: Dict[str, Any]) -> TrackingRecord:
        """Create a new tracking record"""
        record = TrackingRecord(**tracking_data)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_by_tracking_number(self, tracking_number: str) -> Optional[TrackingRecord]:
        """Get tracking record by tracking number"""
        return self.db.query(TrackingRecord).filter(
            TrackingRecord.tracking_number == tracking_number
        ).first()
    
    def get_multiple(self, tracking_numbers: List[str]) -> List[TrackingRecord]:
        """Get multiple tracking records"""
        return self.db.query(TrackingRecord).filter(
            TrackingRecord.tracking_number.in_(tracking_numbers)
        ).all()
    
    def update(self, tracking_number: str, update_data: Dict[str, Any]) -> Optional[TrackingRecord]:
        """Update existing tracking record"""
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
        """Insert or update tracking record"""
        tracking_number = tracking_data.get('tracking_number')
        existing = self.get_by_tracking_number(tracking_number)
        
        if existing:
            return self.update(tracking_number, tracking_data)
        else:
            return self.create(tracking_data)
    
    def bulk_upsert(self, tracking_data_list: List[Dict[str, Any]]) -> List[TrackingRecord]:
        """Bulk insert or update tracking records"""
        results = []
        for tracking_data in tracking_data_list:
            record = self.upsert(tracking_data)
            results.append(record)
        return results
    
    def get_by_batch_id(self, batch_id: str) -> List[TrackingRecord]:
        """Get all records for a specific batch"""
        return self.db.query(TrackingRecord).filter(
            TrackingRecord.batch_id == batch_id
        ).all()
    
    def get_recent(self, limit: int = 100) -> List[TrackingRecord]:
        """Get most recent tracking records"""
        return self.db.query(TrackingRecord).order_by(
            TrackingRecord.created_at.desc()
        ).limit(limit).all()
    
    def count_all(self) -> int:
        """Count total tracking records"""
        return self.db.query(TrackingRecord).count()
    
    def delete(self, tracking_number: str) -> bool:
        """Delete tracking record"""
        record = self.get_by_tracking_number(tracking_number)
        if record:
            self.db.delete(record)
            self.db.commit()
            return True
        return False

    async def mark_bin_closure_email_sent(self, tracking_number: str) -> bool:
        record = self.get_by_tracking_number(tracking_number)
        if record and not getattr(record, "bin_closure_email_sent", False):
            record.bin_closure_email_sent = True
            record.bin_closure_email_sent_at = datetime.utcnow()
            record.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False

    async def get_by_tracking_number_async(self, tracking_number: str) -> Optional[TrackingRecord]:
        return self.get_by_tracking_number(tracking_number)

class APIUsageRepository:
    """
    Repository for API usage tracking
    Helps manage DHL API rate limits
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_today(self) -> APIUsage:
        """Get or create API usage record for today"""
        today = date.today().isoformat()
        usage = self.db.query(APIUsage).filter(APIUsage.date == today).first()
        
        if not usage:
            usage = APIUsage(date=today, request_count=0)
            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)
        
        return usage
    
    def increment_usage(self, success: bool = True) -> APIUsage:
        """Increment API usage counter"""
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
        """Get remaining API requests for today"""
        usage = self.get_or_create_today()
        return max(0, daily_limit - usage.request_count)
    
    def can_make_request(self, daily_limit: int = 250) -> bool:
        """Check if we can make more API requests today"""
        return self.get_remaining_requests(daily_limit) > 0
    
    def get_usage_stats(self, days: int = 7) -> List[APIUsage]:
        """Get API usage statistics for last N days"""
        return self.db.query(APIUsage).order_by(
            APIUsage.date.desc()
        ).limit(days).all()


class ExportRepository:
    """
    Repository for export history
    Tracks document exports
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, export_data: Dict[str, Any]) -> ExportHistory:
        """Create export history record"""
        export = ExportHistory(**export_data)
        self.db.add(export)
        self.db.commit()
        self.db.refresh(export)
        return export
    
    def get_recent(self, limit: int = 50) -> List[ExportHistory]:
        """Get recent export history"""
        return self.db.query(ExportHistory).order_by(
            ExportHistory.created_at.desc()
        ).limit(limit).all()
    
    def get_by_type(self, export_type: str) -> List[ExportHistory]:
        """Get exports by type (pdf/docx)"""
        return self.db.query(ExportHistory).filter(
            ExportHistory.export_type == export_type
        ).order_by(ExportHistory.created_at.desc()).all()

# GLOBAL REPOSITORY INSTANCE — CORRECT & FINAL VERSION
from fastapi import Depends
from sqlalchemy.orm import Session
from app.utils.dependencies import get_db

def get_tracking_repo(db: Session = Depends(get_db)):
    return TrackingRepository(db)

# This is what dhl_services.py imports
tracking_repo = get_tracking_repo()
#as async and see 