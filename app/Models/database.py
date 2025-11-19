"""
Database models using SQLAlchemy ORM
Follows declarative base pattern
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class TrackingRecord(Base):
    """
    Main table for storing tracking information
    """
    __tablename__ = "tracking_records"
    
    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String(50), unique=True, index=True, nullable=False)
    
    # Tracking Information
    status_code = Column(String(20), nullable=True)
    status = Column(String(100), nullable=True)
    origin = Column(String(100), nullable=True)
    destination = Column(String(100), nullable=True)
    
    # Additional tracking details (stored as JSON for flexibility)
    tracking_details = Column(JSON, nullable=True)
    
    # Metadata
    batch_id = Column(String(100), nullable=True, index=True)
    is_successful = Column(Boolean, default=False)
    error_message = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_checked = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<TrackingRecord(tracking_number={self.tracking_number}, status={self.status})>"


class APIUsage(Base):
    """
    Track DHL API usage for rate limiting
    """
    __tablename__ = "api_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), unique=True, index=True)  # Format: YYYY-MM-DD
    request_count = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<APIUsage(date={self.date}, requests={self.request_count})>"


class ExportHistory(Base):
    """
    Track export operations
    """
    __tablename__ = "export_history"
    
    id = Column(Integer, primary_key=True, index=True)
    export_type = Column(String(10))  # 'pdf' or 'docx'
    file_path = Column(String(500))
    tracking_numbers = Column(JSON)  # List of tracking numbers included
    record_count = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ExportHistory(type={self.export_type}, records={self.record_count})>"
