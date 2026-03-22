"""
Automation Service - WITH AUTO-REPORTS, SCHEDULED FILE PROCESSING, AND WAYBILL VALIDATOR
Main service with network folder support, automatic PDF generation, and specialized waybill validation

CHANGES MADE:
- tracking_data unpacking updated from (waybill, _) to (waybill, _, _) to handle
  the new 3-tuple format (waybill, binID, date_order_binned) from file_processor
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
from app.utils.email_service import EmailService
from app.core.export_cleanup_service import export_cleanup_service

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.Automation.file_watcher import FileWatcher
from app.Automation.scheduler import AutomationScheduler
from app.Automation.waybill_validator_scanner import WaybillValidatorScanner
from app.core.file_processor import file_processor
from app.core.batch_processor import BatchProcessor

from app.core.dhl_services import dhl_service
from app.core.export_services import export_service
from app.repositories import TrackingRepository, APIUsageRepository, ExportRepository
from app.utils.database import get_db_context
from app.utils.config import settings
import yaml

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Main automation service with network support, auto-reports, and waybill validation
    """
    async def _run_export_cleanup(self):
        """Run export cleanup"""
        try:
            logger.info("Running scheduled export cleanup...")
            stats = export_cleanup_service.cleanup_exports()
            logger.info(f"cleanup completed:{stats['files_archived']} archived, {stats['files_deleted']} deleted")
        except Exception as e:
            logger.error(f"Error in scheduled cleanup:{e}")    
   
    def __init__(self, config_path: str = "./config/automation_config.yaml"):
        self.config = self._load_config(config_path)
        self.is_running = False
        
        # Track last scheduled processing hour to avoid duplicates
        self.last_scheduled_hour = None
        
        # Get scheduled-only filenames from config
        scheduled_filenames = self.config['automation']['processing'].get('scheduled_only_files', ['thabo'])
        
        # Initialize file watcher with multiple folders
        self.file_watcher = FileWatcher(
            inbox_configs=self.config['automation']['inbox_folders'],
            processed_folder=self.config['automation']['processed_folder'],
            failed_folder=self.config['automation']['failed_folder'],
            scheduled_filenames=scheduled_filenames
        )
        
        # NEW: Initialize waybill validator scanner
        self.waybill_scanner = WaybillValidatorScanner(
            search_root="\\\\soj3serv07\\Production To Office\\DHL\\",
            target_filename="dhl_waybill_validation",
            processed_folder=self.config['automation']['processed_folder'],
            failed_folder=self.config['automation']['failed_folder']
        )
        
        self.scheduler = AutomationScheduler()
        self.batch_processor = BatchProcessor(dhl_service)
        
        # Setup signal handlers
        import threading
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Automation Service initialized with Waybill Validator")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            'automation': {
                'enabled': True,
                'inbox_folders': [
                    {
                        'path': './data/inbox',
                        'type': 'local',
                        'enabled': True,
                        'name': 'Local Inbox'
                    }
                ],
                'processed_folder': './data/processed',
                'failed_folder': './data/failed',
                'schedule': {
                    'time': '09:00',
                    'enabled': True
                },
                'processing': {
                    'immediate_process': True,
                    'max_retries': 3,
                    'watch_interval': 10,
                    'scheduled_only_files': ['thabo', 'dhl_waybill_validation']
                },
                'auto_reports': {
                    'enabled': True,
                    'format': 'pdf',
                    'export_folder': './exports',
                    'include_details': True
                }
            },
            'logging': {
                'level': 'INFO',
                'keep_days': 30
            }
        }
    
    async def generate_report(self, tracking_numbers: List[str], source_file: str) -> Optional[str]:
        """
        Generate PDF/DOCX report automatically after processing
        
        Returns:
            Path to generated report file, or None if failed
        """
        if not self.config['automation']['auto_reports']['enabled']:
            logger.info("Auto-reports disabled, skipping report generation")
            return None
        
        try:
            logger.info(f"Generating automatic report for {len(tracking_numbers)} records...")
            
            # Get configuration
            report_config = self.config['automation']['auto_reports']
            export_format = report_config.get('format', 'pdf')
            export_folder = Path(report_config.get('export_folder', './exports'))
            include_details = report_config.get('include_details', True)
            
            # Ensure export folder exists
            export_folder.mkdir(parents=True, exist_ok=True)
            
            # Get tracking records from database
            with get_db_context() as db:
                tracking_repo = TrackingRepository(db)
                export_repo = ExportRepository(db)
                
                records = tracking_repo.get_multiple(tracking_numbers)
                
                if not records:
                    logger.warning("No records found for report generation")
                    return None
                
                # Generate report based on format
                if export_format.lower() == 'pdf':
                    file_path = export_service.generate_pdf(records, include_details)
                else:
                    file_path = export_service.generate_docx(records, include_details)
                
                # Save export history
                export_repo.create({
                    "export_type": export_format,
                    "file_path": file_path,
                    "tracking_numbers": tracking_numbers,
                    "record_count": len(records)
                })
                
                logger.info(f"Report generated: {Path(file_path).name}")
                logger.info(f"Saved to: {file_path}")

                EmailService().send_report(file_path, source_file)
              
                return file_path
                
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None
            
    async def process_file(
        self, 
        file_path: Path, 
        source_folder: str, 
        retries: int = 0
    ) -> Tuple[bool, List[str]]:
        """
        Process a single file
        
        Returns:
            Tuple of (success, list of tracking numbers)
        """
        max_retries = self.config['automation']['processing']['max_retries']
        
        try:
            logger.info(f"Processing file: {file_path.name} (from: {source_folder})")
            
            # Create mock UploadFile
            class MockUploadFile:
                def __init__(self, filepath):
                    self.filename = filepath.name
                    self._filepath = filepath
                
                async def read(self):
                    with open(self._filepath, 'rb') as f:
                        return f.read()
            
            mock_file = MockUploadFile(file_path)
            
            # Process file
            tracking_data = await file_processor.process_file(mock_file)
            
            if not tracking_data:
                raise Exception("No tracking data extracted from file")
            
            logger.info(f"Extracted {len(tracking_data)} records from {file_path.name}")
            
            # Process through batch processor
            with get_db_context() as db:
                tracking_repo = TrackingRepository(db)
                api_usage_repo = APIUsageRepository(db)
                
                results = await self.batch_processor.process_batch(
                    tracking_data,
                    tracking_repo,
                    api_usage_repo
                )
                
                logger.info(f"Processing complete: {results['successful']} successful, {results['failed']} failed")
            
            # Get list of tracking numbers for report
            # UPDATED: now unpacks 3-tuples (waybill, binID, date_order_binned)
            tracking_numbers = [waybill for waybill, _, _ in tracking_data]
            
            # Move to processed folder based on source
            if source_folder == "DHL Waybill Validator":
                self.waybill_scanner.move_to_processed(file_path)
            else:
                self.file_watcher.move_to_processed(file_path, source_folder)
            
            # Generate automatic report
            await self.generate_report(tracking_numbers, file_path.name)
            
            return True, tracking_numbers
            
        except Exception as e:
            logger.error(f"Error processing file {file_path.name}: {str(e)}")
            
            # Retry logic
            if retries < max_retries:
                logger.info(f"Retrying... (attempt {retries + 1}/{max_retries})")
                await asyncio.sleep(5)
                return await self.process_file(file_path, source_folder, retries + 1)
            else:
                # Move to failed folder
                if source_folder == "DHL Waybill Validator":
                    self.waybill_scanner.move_to_failed(file_path, str(e))
                else:
                    self.file_watcher.move_to_failed(file_path, source_folder, str(e))
                return False, []
    
    async def scan_and_process(self, scheduled_run: bool = False):
        """
        Scan all inbox folders AND waybill validator and process files
        
        Args:
            scheduled_run: If True, process ALL files including 'Thabo' and validation files
                          If False, check current time and process accordingly
        """
        try:
            current_time = datetime.now()
            
            # If not explicitly a scheduled run, check if we're in the scheduled hour
            if not scheduled_run:
                schedule_time = self.config['automation']['schedule']['time']
                schedule_hour = int(schedule_time.split(':')[0])
                
                # If current hour matches scheduled hour AND we haven't processed this hour yet
                if current_time.hour == schedule_hour:
                    # Check if we already processed scheduled files this hour
                    if self.last_scheduled_hour != schedule_hour:
                        logger.info(f"Current hour ({current_time.hour}) matches scheduled hour ({schedule_hour})")
                        logger.info("SCHEDULED HOUR DETECTED: Processing ALL files including scheduled-only files...")
                        scheduled_run = True
                        self.last_scheduled_hour = schedule_hour
                    else:
                        logger.info(f"Already processed scheduled files this hour ({schedule_hour})")
            
            all_files = []
            
            # Get regular inbox files
            if scheduled_run:
                logger.info("SCHEDULED SCAN: Processing ALL files including scheduled-only files...")
                inbox_files = self.file_watcher.get_scheduled_files()
            else:
                logger.info("IMMEDIATE SCAN: Processing files (excluding scheduled-only files)...")
                inbox_files = self.file_watcher.get_new_files(include_scheduled_only=False)
            
            all_files.extend(inbox_files)
            
            # NEW: Get waybill validation file (only during scheduled runs)
            if scheduled_run:
                logger.info("\n" + "=" * 80)
                logger.info("SEARCHING FOR DHL WAYBILL VALIDATION FILE")
                logger.info("=" * 80)
                
                validation_file = self.waybill_scanner.find_validation_file()
                
                if validation_file:
                    all_files.append(validation_file)
                    logger.info("✓ Waybill validation file added to processing queue")
                else:
                    logger.info("No waybill validation file found this scan")
                
                logger.info("=" * 80 + "\n")
            
            if not all_files:
                logger.info("No new files found")
                return
            
            logger.info(f"Found {len(all_files)} new file(s) total")
            
            # Process each file
            for file_path, source_folder in all_files:
                await self.process_file(file_path, source_folder)
            
            logger.info(f"EMAIL_TO: {settings.EMAIL_TO}")
            logger.info(f"Enabled: {EmailService().enabled}")
            
        except Exception as e:
            logger.error(f"Error in scan_and_process: {e}")
    
    async def watch_loop(self):
        """Continuous file watching loop - Automatically detects scheduled hour"""
        watch_interval = self.config['automation']['processing']['watch_interval']
        
        logger.info(f"File watcher started (checking every {watch_interval} seconds)")
        
        scheduled_filenames = self.config['automation']['processing'].get('scheduled_only_files', ['thabo', 'dhl_waybill_validation'])
        logger.info(f"Scheduled-only files: {', '.join(scheduled_filenames)}")
        
        schedule_time = self.config['automation']['schedule']['time']
        logger.info(f"Scheduled processing hour: {schedule_time} (processes scheduled files anytime during this hour)")
        logger.info(f"Waybill validation file will be searched during scheduled hour")
        
        while self.is_running:
            try:
                # The scan_and_process method automatically detects if we're in scheduled hour
                await self.scan_and_process(scheduled_run=False)
                await asyncio.sleep(watch_interval)
                
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                await asyncio.sleep(watch_interval)
    
    async def scheduled_scan_task(self):
        """
        Task that runs at scheduled time (e.g., 9:00 AM)
        This processes ALL files including 'Thabo' and waybill validation
        """
        logger.info("=" * 80)
        logger.info("SCHEDULED TASK TRIGGERED")
        logger.info("Processing ALL files including scheduled-only files AND waybill validation")
        logger.info("=" * 80)
        
        await self.scan_and_process(scheduled_run=True)
    
    async def run_async(self):
        """Async main loop"""
        try:
            logger.info("=" * 60)
            logger.info("Starting DHL Tracking Automation Service")
            logger.info("With Waybill Validation Scanner")
            logger.info("=" * 60)
            
            self.is_running = True
            
            # Schedule export cleanup at 2:00 AM
            self.scheduler.add_daily_task(
                self._run_export_cleanup,
                hour=2,
                minute=0,
                task_name="export_cleanup"
            )
            logger.info(f"Scheduled export cleanup at 2:00 AM")
            
            # Setup scheduler if enabled
            if self.config['automation']['schedule']['enabled']:
                schedule_time = self.config['automation']['schedule']['time']
                hour, minute = map(int, schedule_time.split(':'))
                
                # Schedule the task that processes ALL files
                self.scheduler.add_daily_task(
                    self.scheduled_scan_task,
                    hour=hour,
                    minute=minute,
                    task_name="daily_file_scan"
                )
                
                self.scheduler.start()
                logger.info(f"Scheduled daily scan at {schedule_time} (processes ALL files + waybill validation)")
            
            # Log auto-report status
            if self.config['automation']['auto_reports']['enabled']:
                report_format = self.config['automation']['auto_reports']['format'].upper()
                logger.info(f"Auto-reports enabled ({report_format} format)")
            
            # Start watch loop
            if self.config['automation']['processing']['immediate_process']:
                logger.info("Immediate processing enabled")
                schedule_time = self.config['automation']['schedule']['time']
                schedule_hour = schedule_time.split(':')[0]
                scheduled_filenames = self.config['automation']['processing'].get('scheduled_only_files', ['thabo', 'dhl_waybill_validation'])
                logger.info(f"Scheduled files ({', '.join(scheduled_filenames)}) will be processed anytime during hour {schedule_hour}")
                await self.watch_loop()
            else:
                logger.info("Running in scheduled mode only")
                while self.is_running:
                    await asyncio.sleep(60)
                    
        except Exception as e:
            logger.error(f"Error in async loop: {e}")
            self.stop()
    
    def start(self):
        """Start the automation service"""
        try:
            # Windows compatibility
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
            asyncio.run(self.run_async())
                    
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.stop()
        except Exception as e:
            logger.error(f"Error starting service: {e}", exc_info=True)
            self.stop()
    
    def stop(self):
        """Stop the automation service"""
        logger.info("Stopping automation service...")
        self.is_running = False
        
        if self.scheduler:
            self.scheduler.stop()
        
        logger.info("Automation service stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point"""
    from app.utils.logging_config import setup_logging
    setup_logging()
    
    service = AutomationService()
    service.start()


if __name__ == "__main__":
    main()
    