"""
Pydantic schemas for request/response validation
Ensures type safety and data validation

FINAL VERSION - Simple text area input matching single tracking style
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from enum import Enum


class ExportFormat(str, Enum):
    """Export format options"""
    PDF = "pdf"
    DOCX = "docx"


class TrackingNumberInput(BaseModel):
    """Single tracking number input"""
    tracking_number: str = Field(..., min_length=5, max_length=50)
    bin_id: Optional[str] = Field(None, max_length=100)
    
    @validator('tracking_number')
    def validate_tracking_number(cls, v):
        """Clean and validate tracking number"""
        v = v.strip().upper()
        if not v:
            raise ValueError("Tracking number cannot be empty")
        return v
    
    @validator('bin_id')
    def validate_bin_id(cls, v):
        """Clean binID"""
        if v:
            return v.strip()
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "tracking_number": "1234567890",
                "bin_id": "BIN001"
            }
        }


class TrackingResponse(BaseModel):
    """Response for single tracking query"""
    tracking_number: str
    bin_id: Optional[str] = None
    status_code: Optional[str] = None
    status: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    tracking_details: Optional[Dict[str, Any]] = None
    is_successful: bool
    error_message: Optional[str] = None
    last_checked: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "tracking_number": "1234567890",
                "bin_id": "BIN001",
                "status_code": "delivered",
                "status": "Delivered",
                "origin": "New York, USA",
                "destination": "Los Angeles, USA",
                "is_successful": True,
                "last_checked": "2024-01-15T10:30:00"
            }
        }


class BulkTrackingRequest(BaseModel):
    """Request for bulk tracking"""
    tracking_numbers: List[str] = Field(..., min_items=1, max_items=1000)
    
    @validator('tracking_numbers')
    def validate_tracking_numbers(cls, v):
        """Clean and validate tracking numbers"""
        cleaned = [num.strip().upper() for num in v if num.strip()]
        if not cleaned:
            raise ValueError("No valid tracking numbers provided")
        seen = set()
        unique = []
        for num in cleaned:
            if num not in seen:
                seen.add(num)
                unique.append(num)
        return unique
    
    class Config:
        json_schema_extra = {
            "example": {
                "tracking_numbers": ["1234567890", "0987654321", "1122334455"]
            }
        }


class PlainTextBulkRequest(BaseModel):
    """
    Simple bulk tracking request - one text area
    Format: waybill,binID per line
    """
    tracking_data: str = Field(
        ..., 
        description="Enter tracking data (one per line)\nFormat: waybill,binID",
        min_length=1
    )
    
    @validator('tracking_data')
    def parse_tracking_data(cls, v):
        """
        Parse text area input
        Accepts: waybill,binID per line
        Returns: List[Tuple[waybill, binID]]
        """
        if not v or not v.strip():
            raise ValueError("No tracking data provided")
        
        lines = v.strip().split('\n')
        tracking_list = []
        
        for line_num, line in enumerate(lines, 1):
            cleaned = line.strip()
            if not cleaned:
                continue
            
            # Parse waybill,binID
            if ',' in cleaned:
                parts = cleaned.split(',', 1)
                waybill = parts[0].strip().upper()
                bin_id = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            else:
                # Just waybill
                waybill = cleaned.upper()
                bin_id = None
            
            if not waybill:
                raise ValueError(f"Line {line_num}: Waybill cannot be empty")
            
            tracking_list.append((waybill, bin_id))
        
        if not tracking_list:
            raise ValueError("No valid tracking data found")
        
        if len(tracking_list) > 1000:
            raise ValueError("Maximum 1000 records allowed")
        
        # Remove duplicates
        seen = set()
        unique = []
        for waybill, bin_id in tracking_list:
            if waybill not in seen:
                seen.add(waybill)
                unique.append((waybill, bin_id))
        
        return unique
    
    class Config:
        json_schema_extra = {
            "example": {
                "tracking_data": "5859187246,BI01FSTD00001002\n2079797893,BI01FSTS00010573\n1010019043,BI01FSTD00001003"
            }
        }


class BulkTrackingResponse(BaseModel):
    """Response for bulk tracking"""
    total_requested: int
    successful: int
    failed: int
    results: List[TrackingResponse]
    batch_id: Optional[str] = None
    processing_time: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_requested": 3,
                "successful": 2,
                "failed": 1,
                "results": [],
                "batch_id": "batch_20240115_103000",
                "processing_time": 2.5
            }
        }


class ExportRequest(BaseModel):
    """Request for exporting tracking data"""
    tracking_numbers: List[str] = Field(..., min_items=1)
    format: ExportFormat = ExportFormat.PDF
    include_details: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "tracking_numbers": ["1234567890", "0987654321"],
                "format": "pdf",
                "include_details": True
            }
        }


class PlainTextExportRequest(BaseModel):
    """
    Simple export request - one text area
    Format: waybill,binID per line
    """
    tracking_data: str = Field(
        ..., 
        description="Enter tracking data (one per line)\nFormat: waybill,binID"
    )
    format: ExportFormat = ExportFormat.PDF
    include_details: bool = True
    
    @validator('tracking_data')
    def parse_tracking_data(cls, v):
        """
        Parse text area input
        Accepts: waybill,binID per line
        Returns: List[Tuple[waybill, binID]]
        """
        if not v or not v.strip():
            raise ValueError("No tracking data provided")
        
        lines = v.strip().split('\n')
        tracking_list = []
        
        for line_num, line in enumerate(lines, 1):
            cleaned = line.strip()
            if not cleaned:
                continue
            
            if ',' in cleaned:
                parts = cleaned.split(',', 1)
                waybill = parts[0].strip().upper()
                bin_id = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            else:
                waybill = cleaned.upper()
                bin_id = None
            
            if not waybill:
                raise ValueError(f"Line {line_num}: Waybill cannot be empty")
            
            tracking_list.append((waybill, bin_id))
        
        if not tracking_list:
            raise ValueError("No valid tracking data found")
        
        # Remove duplicates
        seen = set()
        unique = []
        for waybill, bin_id in tracking_list:
            if waybill not in seen:
                seen.add(waybill)
                unique.append((waybill, bin_id))
        
        return unique
    
    class Config:
        json_schema_extra = {
            "example": {
                "tracking_data": "5859187246,BI01FSTD00001002\n2079797893,BI01FSTS00010573\n1010019043,BI01FSTD00001003",
                "format": "pdf",
                "include_details": True
            }
        }


class ExportResponse(BaseModel):
    """Response for export operation"""
    success: bool
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    download_url: Optional[str] = None
    record_count: int
    error_message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "file_path": "/exports/tracking_report_20240115.pdf",
                "file_name": "tracking_report_20240115.pdf",
                "record_count": 5
            }
        }


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


class APIUsageResponse(BaseModel):
    """Response for API usage statistics"""
    date: str
    requests_used: int
    requests_remaining: int
    daily_limit: int
    percentage_used: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-15",
                "requests_used": 150,
                "requests_remaining": 100,
                "daily_limit": 250,
                "percentage_used": 60.0
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    database_connected: bool
    api_available: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00",
                "version": "1.0.0",
                "database_connected": True,
                "api_available": True
            }
        }

