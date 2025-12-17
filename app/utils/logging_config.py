"""
Enhanced Logging Configuration - FIXED
Captures all CLI output and saves to local AND network locations
"""
import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


class NetworkAwareHandler(TimedRotatingFileHandler):
    """
    Custom handler that gracefully handles network unavailability
    Falls back to local-only logging if network fails
    """
    
    def __init__(self, filename, when='midnight', interval=1, backupCount=30, encoding='utf-8', is_network=False):
        self.is_network = is_network
        self.network_available = True
        
        # IMPORTANT: Initialize parent class first to set up all attributes
        try:
            # Ensure directory exists--if they don't exist then they qill be added/Created MKDIR
            log_dir = Path(filename).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Call parent __init__ to properly initialize the handler
            super().__init__(
                filename=str(filename),
                when=when,
                interval=interval,
                backupCount=backupCount,
                encoding=encoding
            )
            
            if is_network:
                #getLogger(__name__).info(f"Network logging enabled: {filename}")
                logging.getLogger(__name__).info(f"-->YES> Network logging enable: {filename}")
              
        except Exception as e:
            if is_network:
                # Network failed - create a dummy handler that does nothing
                self.network_available = False
                logging.getLogger(__name__).warning(f"[:(] Network logging unavailable: {e}")
                
                # Initialize parent with a safe local temp file instead--will remove this later on ><
                temp_file = Path("./data/logs/network_fallback.log")
                temp_file.parent.mkdir(parents=True, exist_ok=True)
                
                super().__init__(
                    filename=str(temp_file),
                    when=when,
                    interval=interval,
                    backupCount=backupCount,
                    encoding=encoding
                )
                
                # Disable this handler since network is unavailable
                self.setLevel(logging.CRITICAL + 1)  # Set to level higher than any log
            else:
                raise
    
    def emit(self, record):
        """1. Emit log record 
           2. Handling network failures gracefully
           """
        if self.is_network and not self.network_available:
            return  # Skip network logging if unavailable
        
        try:
            super().emit(record)
        except Exception as e:
            if self.is_network:
                # Network logging failed, mark as unavailable
                self.network_available = False
                # Don't log error to avoid recursion
            else:
                # Local logging failed - this is serious--Need intervention and hight attention
                self.handleError(record)


def setup_logging(log_level: str = "INFO"):
    """
    Setup comprehensive logging system with local AND network support
    Logs to both locations simultaneously with graceful degradation
    """
    # Create local logs directory
    local_log_dir = Path("./data/logs")
    local_log_dir.mkdir(parents=True, exist_ok=True)
    
    # Network logs directory
    network_log_dir = Path("\\\\soj3serv07\\Production To Office\\DHL\\data\\logs")
    
    # Define log format
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    #root_logger.setLevel(getattr(logger, log_level))   
    root_logger.setLevel(getattr(logging,log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    
    # 1. Console Handler (stdout)-->for log reading and recording

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    

    # 2. LOCAL Application Log File

    local_app_log = local_log_dir / "app.log"
    local_app_handler = TimedRotatingFileHandler(
        local_app_log,
        when='midnight',
        interval=1,
        backupCount=30, # can be changed--here and ond on config
        encoding='utf-8'
    )
    local_app_handler.setLevel(logging.DEBUG)
    local_app_handler.setFormatter(log_format)
    local_app_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(local_app_handler)
    
    
    # 3. NETWORK Application Log File (Duplicate) - SAFE

    try:
        network_app_log = network_log_dir / "app.log"
        network_app_handler = NetworkAwareHandler(
            network_app_log,
            when='midnight',
            interval=1,
            backupCount=30, # can be changed--here and ond on config
            encoding='utf-8',
            is_network=True
        )
        network_app_handler.setLevel(logging.DEBUG)
        network_app_handler.setFormatter(log_format)
        network_app_handler.suffix = "%Y-%m-%d"
        root_logger.addHandler(network_app_handler)
    except Exception as e:
        # Silently continue if network logging setup fails--->This ensure that the processing does not stop during production
        pass
    
    
    # 4. LOCAL Automation Log File
    
    local_automation_log = local_log_dir / "automation.log"
    local_automation_handler = TimedRotatingFileHandler(
        local_automation_log,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    local_automation_handler.setLevel(logging.INFO)
    local_automation_handler.setFormatter(log_format)
    local_automation_handler.suffix = "%Y-%m-%d"
    
    # Add to automation logger
    automation_logger = logging.getLogger('app.automation')
    automation_logger.addHandler(local_automation_handler)
    
   
    # 5. NETWORK Automation Log File (Duplicate) - SAFE
    
    try:
        network_automation_log = network_log_dir / "automation.log"
        network_automation_handler = NetworkAwareHandler(
            network_automation_log,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8',
            is_network=True
        )
        network_automation_handler.setLevel(logging.INFO)
        network_automation_handler.setFormatter(log_format)
        network_automation_handler.suffix = "%Y-%m-%d"
        automation_logger.addHandler(network_automation_handler)
    except Exception as e:
        # Silently continue
        pass
    
    # ============================================================
    # 6. LOCAL Error Log File
    # ============================================================
    local_error_log = local_log_dir / "errors.log"
    local_error_handler = TimedRotatingFileHandler(
        local_error_log,
        when='midnight',
        interval=1,
        backupCount=60,
        encoding='utf-8'
    )
    local_error_handler.setLevel(logging.ERROR)
    local_error_handler.setFormatter(log_format)
    local_error_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(local_error_handler)
    
    # ============================================================
    # 7. NETWORK Error Log File (Duplicate) - SAFE
    # ============================================================
    try:
        network_error_log = network_log_dir / "errors.log"
        network_error_handler = NetworkAwareHandler(
            network_error_log,
            when='midnight',
            interval=1,
            backupCount=60,
            encoding='utf-8',
            is_network=True
        )
        network_error_handler.setLevel(logging.ERROR)
        network_error_handler.setFormatter(log_format)
        network_error_handler.suffix = "%Y-%m-%d"
        root_logger.addHandler(network_error_handler)
    except Exception as e:
        # Silently continue
        pass
    
    # ============================================================
    # 8. LOCAL Scheduler Log File
    # ============================================================
    local_scheduler_log = local_log_dir / "scheduler.log"
    local_scheduler_handler = TimedRotatingFileHandler(
        local_scheduler_log,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    local_scheduler_handler.setLevel(logging.INFO)
    local_scheduler_handler.setFormatter(log_format)
    local_scheduler_handler.suffix = "%Y-%m-%d"
    
    # Add to scheduler logger
    scheduler_logger = logging.getLogger('apscheduler')
    scheduler_logger.addHandler(local_scheduler_handler)
    
    # ============================================================
    # 9. NETWORK Scheduler Log File (Duplicate) - SAFE
    # ============================================================
    try:
        network_scheduler_log = network_log_dir / "scheduler.log"
        network_scheduler_handler = NetworkAwareHandler(
            network_scheduler_log,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8',
            is_network=True
        )
        network_scheduler_handler.setLevel(logging.INFO)
        network_scheduler_handler.setFormatter(log_format)
        network_scheduler_handler.suffix = "%Y-%m-%d"
        scheduler_logger.addHandler(network_scheduler_handler)
    except Exception as e:
        # Silently continue
        pass
    
    # Check if network logging is working
    network_status = "unavailable (will use local logs only)"
    try:
        if network_log_dir.exists():
            network_status = "available"
    except:
        pass
    
    # Log startup message
    root_logger.info("=" * 80)
    root_logger.info(f"Logging system initialized - Level: {log_level}")
    root_logger.info(f"Local logs: {local_log_dir.absolute()}")
    root_logger.info(f"Network logs: {network_status}")
    if network_status == "available":
        root_logger.info(f"  Network path: {network_log_dir}")
    root_logger.info(f"  - App Log: app.log")
    root_logger.info(f"  - Automation Log: automation.log")
    root_logger.info(f"  - Error Log: errors.log")
    root_logger.info(f"  - Scheduler Log: scheduler.log")
    root_logger.info("=" * 80)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module"""
    return logging.getLogger(name)


