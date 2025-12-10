"""
Enhanced Logging Configuration
Captures all CLI output and saves to organized log files
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime


def setup_logging(log_level: str = "INFO"):
    """
    Setup comprehensive logging system
    Logs to both console and files
    """
    #C:\Users\thabomth\OneDrive - myidemia\Desktop\Projects_Dev\dhl-tracking-system\data\logs
    # Create logs directory
    log_dir = Path("./data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)  # if it does not exist in the file structure
    
    # Define log format
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # 1. Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # 2. Application Log File (rotating daily)
    app_log_file = log_dir / "app.log"
    app_handler = TimedRotatingFileHandler(
        app_log_file,
        when='midnight',
        interval=1,
        backupCount=30,  # Keep 30 days
        encoding='utf-8'
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(log_format)
    app_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(app_handler)
    
    # 3. Automation Log File (separate for automation events)
    automation_log_file = log_dir / "automation.log"
    automation_handler = TimedRotatingFileHandler(
        automation_log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    automation_handler.setLevel(logging.INFO)
    automation_handler.setFormatter(log_format)
    automation_handler.suffix = "%Y-%m-%d"
    
    # Add automation handler to automation logger only
    automation_logger = logging.getLogger('app.automation')
    automation_logger.addHandler(automation_handler)
    
    # 4. Error Log File (errors only)
    error_log_file = log_dir / "errors.log"
    error_handler = TimedRotatingFileHandler(
        error_log_file,
        when='midnight',
        interval=1,
        backupCount=60,  # Keep errors for 60 days
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    error_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(error_handler)
    
    # 5. Scheduler Log File
    scheduler_log_file = log_dir / "scheduler.log"
    scheduler_handler = TimedRotatingFileHandler(
        scheduler_log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    scheduler_handler.setLevel(logging.INFO)
    scheduler_handler.setFormatter(log_format)
    scheduler_handler.suffix = "%Y-%m-%d"
    
    # Add to APScheduler logger
    scheduler_logger = logging.getLogger('apscheduler')
    scheduler_logger.addHandler(scheduler_handler)
    
    # Log startup message
    root_logger.info("=" * 80)
    root_logger.info(f"Logging system initialized - Level: {log_level}")
    root_logger.info(f"Logs directory: {log_dir.absolute()}")
    root_logger.info(f"App Log: {app_log_file}")
    root_logger.info(f"Automation Log: {automation_log_file}")
    root_logger.info(f"Error Log: {error_log_file}")
    root_logger.info(f"Scheduler Log: {scheduler_log_file}")
    root_logger.info("=" * 80)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module"""
    return logging.getLogger(name)

