"""
Automation API Endpoints
Trigger and control automation via API
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
import logging
import asyncio

from app.utils.database import get_db
from app.Automation.file_watcher import FileWatcher
from app.Automation.automation_service import AutomationService
from app.core.batch_processor import BatchProcessor
from app.core.dhl_services import dhl_service
from app.core.export_services import export_service
from app.repositories import TrackingRepository, APIUsageRepository, ExportRepository
from app.utils.database import get_db_context
from app.core.export_cleanup_service import export_cleanup_service
import yaml
from app.utils.email_service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automation", tags=["Automation"])


# Response Models
class AutomationTriggerResponse(BaseModel):
    """Response for trigger endpoint"""
    success: bool
    message: str
    files_found: int
    files_processed: int
    files_failed: int
    files_skipped: int
    reports_generated: int
    processing_time: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Automation scan completed successfully",
                "files_found": 3,
                "files_processed": 2,
                "files_failed": 0,
                "files_skipped": 1,
                "reports_generated": 2,
                "processing_time": 45.5
            }
        }


class AutomationStatusResponse(BaseModel):
    """Response for status endpoint"""
    automation_available: bool
    config_loaded: bool
    inbox_folders: list
    last_scan: Optional[str] = None
    total_files_processed_today: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "automation_available": True,
                "config_loaded": True,
                "inbox_folders": [
                    {"name": "Local Inbox", "path": "./data/inbox", "enabled": True},
                    {"name": "Network Folder", "path": "\\\\server\\share", "enabled": True}
                ],
                "last_scan": "2025-12-08 10:30:00",
                "total_files_processed_today": 15
            }
        }


# Global state to track automation
class AutomationState:
    """Track automation state"""
    last_scan_time: Optional[datetime] = None
    is_scanning: bool = False
    files_processed_today: int = 0


automation_state = AutomationState()


def load_automation_config() -> dict:
    """Load automation configuration"""
    try:
        with open("./config/automation_config.yaml", 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading automation config: {e}")
        return None


async def run_automation_scan(db: Session, process_all: bool = False) -> dict:
    """
    Run automation scan and process files
    
    Args:
        db: Database session
        process_all: If True, process ALL files including 'Thabo' (scheduled mode)
                    If False, skip 'Thabo' files (immediate mode)
    
    Returns:
        Dictionary with scan results
    """
    start_time = datetime.now()
    
    results = {
        "files_found": 0,
        "files_processed": 0,
        "files_failed": 0,
        "files_skipped": 0,
        "reports_generated": 0,
        "processing_time": 0.0,
        "errors": []
    }
    
    try:
        # Load config
        config = load_automation_config()
        if not config:
            raise Exception("Failed to load automation configuration")
        
        # Initialize file watcher
        file_watcher = FileWatcher(
            inbox_configs=config['automation']['inbox_folders'],
            processed_folder=config['automation']['processed_folder'],
            failed_folder=config['automation']['failed_folder']
        )
        
        # Initialize batch processor
        batch_processor = BatchProcessor(dhl_service)
        
        # Get new files from all folders
        if process_all:
            logger.info("API Trigger: SCHEDULED MODE - Processing ALL files...")
            new_files = file_watcher.get_scheduled_files()
        else:
            logger.info("API Trigger: IMMEDIATE MODE - Scanning inbox folders (skipping scheduled-only files)...")
            new_files = file_watcher.get_new_files(include_scheduled_only=False)
        
        results["files_found"] = len(new_files)
        
        if not new_files:
            logger.info("No new files found")
            return results
        
        logger.info(f"Found {len(new_files)} new file(s)")
        
        # Process each file
        for file_path, source_folder in new_files:
            try:
                logger.info(f"Processing: {file_path.name} (from: {source_folder})")
                
                # Create mock UploadFile
                class MockUploadFile:
                    def __init__(self, filepath):
                        self.filename = filepath.name
                        self._filepath = filepath
                    
                    async def read(self):
                        with open(self._filepath, 'rb') as f:
                            return f.read()
                
                from app.core.file_processor import file_processor
                mock_file = MockUploadFile(file_path)
                
                # Process file
                tracking_data = await file_processor.process_file(mock_file)
                
                if not tracking_data:
                    raise Exception("No tracking data extracted")
                
                logger.info(f"Extracted {len(tracking_data)} records")
                
                # Process through batch processor
                tracking_repo = TrackingRepository(db)
                api_usage_repo = APIUsageRepository(db)
                
                batch_results = await batch_processor.process_batch(
                    tracking_data,
                    tracking_repo,
                    api_usage_repo
                )
                
                logger.info(f"Batch complete: {batch_results['successful']} successful")
                
                # Move to processed
                file_watcher.move_to_processed(file_path, source_folder)
                results["files_processed"] += 1
                
                # Generate report if enabled
                if config['automation']['auto_reports']['enabled']:
                    tracking_numbers = [waybill for waybill, _ in tracking_data]
                    
                    # Get records and generate report
                    records = tracking_repo.get_multiple(tracking_numbers)
                    if records:
                        report_format = config['automation']['auto_reports']['format']
                        if report_format == 'pdf':
                            report_path = export_service.generate_pdf(records, True)
                        else:
                            report_path = export_service.generate_docx(records, True)
                        
                        logger.info(f"Report generated: {report_path}")
                        results["reports_generated"] += 1

                        # Send email
                        EmailService().send_report(
                            report_path,
                            source_file=file_path.name
                        )
                
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")
                file_watcher.move_to_failed(file_path, source_folder, str(e))
                results["files_failed"] += 1
                results["errors"].append(str(e))
        
        # Update state
        automation_state.last_scan_time = datetime.now()
        automation_state.files_processed_today += results["files_processed"]
        
        end_time = datetime.now()
        results["processing_time"] = (end_time - start_time).total_seconds()
        
        logger.info(f"API scan complete: {results['files_processed']} processed, {results['files_failed']} failed, {results['files_skipped']} skipped")
        
    except Exception as e:
        logger.error(f"Error in automation scan: {e}")
        results["errors"].append(str(e))
    
    return results


@router.post("/trigger", response_model=AutomationTriggerResponse, summary="Trigger Automation Scan")
async def trigger_automation(
    background_tasks: BackgroundTasks,
    process_all: bool = False,
    db: Session = Depends(get_db)
):
    """
    Manually trigger automation to scan inbox folders and process files
    
    **What this does:**
    - Scans all configured inbox folders (local and network)
    - Processes any CSV/Excel files found
    - Generates PDF reports automatically
    - Moves files to processed/failed folders
    
    **Parameters:**
    - **process_all**: If True, process ALL files including 'Thabo' (scheduled mode)
                      If False, skip 'Thabo' files (immediate mode, default)
    
    **Use cases:**
    - Process files immediately without waiting for schedule (process_all=False)
    - Manually trigger scheduled processing (process_all=True)
    - Test automation without running full service
    - On-demand processing via API
    
    **Note:** This runs in the background and returns immediately
    """
    try:
        # Check if already scanning
        if automation_state.is_scanning:
            raise HTTPException(
                status_code=409,
                detail="Automation scan already in progress. Please wait for it to complete."
            )
        
        automation_state.is_scanning = True
        
        # Run scan
        results = await run_automation_scan(db, process_all=process_all)
        
        automation_state.is_scanning = False
        
        mode = "SCHEDULED MODE (all files)" if process_all else "IMMEDIATE MODE (excluding scheduled-only files)"
        
        return AutomationTriggerResponse(
            success=True,
            message=f"Automation scan completed successfully ({mode})" if not results["errors"] else f"Scan completed with errors ({mode})",
            files_found=results["files_found"],
            files_processed=results["files_processed"],
            files_failed=results["files_failed"],
            files_skipped=results["files_skipped"],
            reports_generated=results["reports_generated"],
            processing_time=results["processing_time"]
        )
        
    except HTTPException:
        automation_state.is_scanning = False
        raise
    except Exception as e:
        automation_state.is_scanning = False
        logger.error(f"Error triggering automation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger automation: {str(e)}")


@router.get("/status", response_model=AutomationStatusResponse, summary="Get Automation Status")
async def get_automation_status(db: Session = Depends(get_db)):
    """
    Get current automation status and configuration
    
    **Returns:**
    - Whether automation is available
    - Configuration status
    - List of monitored folders
    - Last scan time
    - Files processed today
    """
    try:
        # Load config
        config = load_automation_config()
        
        if not config:
            return AutomationStatusResponse(
                automation_available=False,
                config_loaded=False,
                inbox_folders=[],
                last_scan=None,
                total_files_processed_today=0
            )
        
        # Parse inbox folders
        inbox_folders = []
        for folder_config in config['automation']['inbox_folders']:
            inbox_folders.append({
                "name": folder_config.get('name', 'Unknown'),
                "path": folder_config.get('path', ''),
                "type": folder_config.get('type', 'local'),
                "enabled": folder_config.get('enabled', False)
            })
        
        # Format last scan time
        last_scan = None
        if automation_state.last_scan_time:
            last_scan = automation_state.last_scan_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return AutomationStatusResponse(
            automation_available=True,
            config_loaded=True,
            inbox_folders=inbox_folders,
            last_scan=last_scan,
            total_files_processed_today=automation_state.files_processed_today
        )
        
    except Exception as e:
        logger.error(f"Error getting automation status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
    


@router.post("/export/cleanup", summary="Trigger Export Cleanup")
async def trigger_export_cleanup():
    """
    Manually trigger export cleanup process
    
    **What it does:**
    - Moves exports older than 3 days to network archive
    - Deletes archived files older than 30 days
    
    **Use when:**
    - Want to clean up immediately (don't wait for 2 AM schedule)
    - Testing cleanup functionality
    - Manual maintenance
    """
    try:
        logger.info("Manual export cleanup triggered via API")
        stats = export_cleanup_service.cleanup_exports()
        
        return {
            "success": True,
            "message": "Export cleanup completed",
            "files_archived": stats["files_archived"],
            "files_deleted": stats["files_deleted"],
            "active_files_remaining": stats["active_files"],
            "errors": stats["errors"]
        }
    except Exception as e:
        logger.error(f"Error in manual cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/status", summary="Get Export Cleanup Status")
async def get_export_status():
    """
    Get current status of export files and archiving
    
    **Returns:**
    - Active files (< 3 days old)
    - Archived files (in network archive)
    - File counts and sizes
    - Network availability status
    """
    try:
        status = export_cleanup_service.get_cleanup_status()
        return {
            "success": True,
            "network_archive_available": status["network_available"],
            "active_files": {
                "count": status["active_count"],
                "total_size_mb": status["active_size_mb"],
                "files": status["active_files"][:10]
            },
            "archived_files": {
                "count": status["archived_count"],
                "total_size_mb": status["archived_size_mb"],
                "files": status["archived_files"][:10]
            }
        }
    except Exception as e:
        logger.error(f"Error getting export status:{e}")
        raise HTTPException(status_code=500, detail=str(e))


