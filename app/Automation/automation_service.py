"""
Automation Service - WITH AUTO-REPORTS
Main service with network folder support and automatic PDF generation
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
from app.utils.email_service import EmailService

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.Automation.file_watcher import FileWatcher
from app.Automation.scheduler import AutomationScheduler
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
    Main automation service with network support and auto-reports
    """
    
    def __init__(self, config_path: str = "./config/automation_config.yaml"):
        self.config = self._load_config(config_path)
        self.is_running = False
        
        # Initialize file watcher with multiple folders
        self.file_watcher = FileWatcher(
            inbox_configs=self.config['automation']['inbox_folders'],
            processed_folder=self.config['automation']['processed_folder'],
            failed_folder=self.config['automation']['failed_folder']
        )
        
        self.scheduler = AutomationScheduler()
        self.batch_processor = BatchProcessor(dhl_service)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(":) Automation Service initialized")
    
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
                    'watch_interval': 10
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
            logger.info(f"📄 Generating automatic report for {len(tracking_numbers)} records...")
            
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
                
                logger.info(f"[:)] Report generated: {Path(file_path).name}")
                logger.info(f"<-> Saved to: {file_path}")

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
            tracking_numbers = [waybill for waybill, _ in tracking_data]
            
            # Move to processed folder
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
                self.file_watcher.move_to_failed(file_path, source_folder, str(e))
                return False, []
    
    async def scan_and_process(self):
        """Scan all inbox folders and process files"""
        try:
            logger.info(" ... Scanning all inbox folders for new files...")
            
            new_files = self.file_watcher.get_new_files()
            
            if not new_files:
                logger.info("No new files found")
                return
            
            logger.info(f"Found {len(new_files)} new file(s)")
            
            # Process each file
            for file_path, source_folder in new_files:
                await self.process_file(file_path, source_folder)
            

            logger.info(f"SMTP_USER: {settings.SMTP_USERNAME}")
            logger.info(f"SMTP_PASS: {settings.SMTP_PASSWORD}")
            logger.info(f"EMAIL_TO: {settings.EMAIL_TO}")
            logger.info(f"Enabled: {EmailService().enabled}")
            
        except Exception as e:
            logger.error(f"Error in scan_and_process: {e}")
    
    async def watch_loop(self):
        """Continuous file watching loop"""
        watch_interval = self.config['automation']['processing']['watch_interval']
        
        logger.info(f"👁️ File watcher started (checking every {watch_interval} seconds)")
        
        while self.is_running:
            try:
                await self.scan_and_process()
                await asyncio.sleep(watch_interval)
                
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                await asyncio.sleep(watch_interval)
    
    async def run_async(self):
        """Async main loop"""
        try:
            logger.info("=" * 60)
            logger.info("--> Starting DHL Tracking Automation Service")
            logger.info("=" * 60)
            
            self.is_running = True
            
            # Setup scheduler if enabled
            if self.config['automation']['schedule']['enabled']:
                schedule_time = self.config['automation']['schedule']['time']
                hour, minute = map(int, schedule_time.split(':'))
                
                self.scheduler.add_daily_task(
                    self.scan_and_process,
                    hour=hour,
                    minute=minute,
                    task_name="daily_file_scan"
                )
                
                self.scheduler.start()
                logger.info(f"📅 Scheduled daily scan at {schedule_time}")
            
            # Log auto-report status
            if self.config['automation']['auto_reports']['enabled']:
                report_format = self.config['automation']['auto_reports']['format'].upper()
                logger.info(f"📄 Auto-reports enabled ({report_format} format)")
            
            # Start watch loop
            if self.config['automation']['processing']['immediate_process']:
                logger.info("⚡ Immediate processing enabled")
                await self.watch_loop()
            else:
                logger.info("⏰ Running in scheduled mode only")
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
        logger.info("🛑 Stopping automation service...")
        self.is_running = False
        
        if self.scheduler:
            self.scheduler.stop()
        
        logger.info("✅ Automation service stopped")
    
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


