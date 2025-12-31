"""
File Watcher - WITH NETWORK FOLDER SUPPORT
Monitors multiple inbox folders (local, network, mapped drives)
"""
import os
import time
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class NetworkFolderConfig:
    """Configuration for a single inbox folder"""
    def __init__(self, config: Dict):
        self.path = Path(config['path'])
        self.type = config.get('type', 'local')
        self.enabled = config.get('enabled', True)
        self.name = config.get('name', str(self.path))
        self.credentials = config.get('credentials', {})
    
    def __repr__(self):
        return f"<Folder: {self.name} ({self.type}) - {'Enabled' if self.enabled else 'Disabled'}>"


class FileWatcher:
    """
    Watches multiple inbox folders for new CSV/Excel files
    Supports: Local folders, Network UNC paths, Mapped drives
    """
    
    def __init__(self, inbox_configs: List[Dict], processed_folder: str, failed_folder: str):
        # Parse inbox configurations
        self.inbox_folders = [NetworkFolderConfig(cfg) for cfg in inbox_configs]
        
        self.processed_folder = Path(processed_folder)
        self.failed_folder = Path(failed_folder)
        
        # Create output folders
        self.processed_folder.mkdir(parents=True, exist_ok=True)
        self.failed_folder.mkdir(parents=True, exist_ok=True)
        
        # Track processed files to avoid duplicates
        self.processed_files = set()
        
        # Initialize and validate folders
        self._initialize_folders()
        
        logger.info(f"File Watcher initialized")
        logger.info(f"Monitoring {len([f for f in self.inbox_folders if f.enabled])} inbox folder(s)")
        logger.info(f"Processed: {self.processed_folder}")
        logger.info(f"Failed: {self.failed_folder}")
    
    def _initialize_folders(self):
        """Initialize and validate all inbox folders"""
        for folder_config in self.inbox_folders:
            if not folder_config.enabled:
                logger.info(f"⏸️  Folder disabled: {folder_config.name}")
                continue
            
            try:
                # Try to create/access folder
                folder_config.path.mkdir(parents=True, exist_ok=True)
                
                # Test read access
                if folder_config.path.exists() and folder_config.path.is_dir():
                    logger.info(f"--> Folder accessible: {folder_config.name} -> {folder_config.path}")
                else:
                    logger.warning(f"⚠️  Folder not accessible: {folder_config.name} -> {folder_config.path}")
                    
            except PermissionError:
                logger.error(f" X-> Permission denied: {folder_config.name} -> {folder_config.path}")
            except Exception as e:
                logger.error(f"X-> Error accessing {folder_config.name}: {e}")
    
    def _connect_network_folder(self, folder_config: NetworkFolderConfig) -> bool:
        """
        Connect to network folder if credentials are provided
        Uses Windows net use command
        """
        if folder_config.type != "network":
            return True
        
        username = folder_config.credentials.get('username')
        password = folder_config.credentials.get('password')
        
        if not username or not password:
            # No credentials provided, assume direct access-- most varable 
            return True
        
        try:
            import subprocess
            
            # Disconnect first (in case already connected)
            subprocess.run(
                ['net', 'use', str(folder_config.path), '/delete'],
                capture_output=True,
                check=False
            )
            
            # Connect with credentials
            cmd = ['net', 'use', str(folder_config.path), f'/user:{username}', password]
            result = subprocess.run(cmd, capture_output=True, check=True)
            
            logger.info(f"✅ Connected to network folder: {folder_config.name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to connect to {folder_config.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error connecting to network folder: {e}")
            return False
    
    def get_new_files(self) -> List[Tuple[Path, str]]:
        """
        Get list of new files from ALL enabled inbox folders
        
        Returns:
            List of tuples: [(file_path, source_folder_name), ...]
        """
        new_files = []
        
        for folder_config in self.inbox_folders:
            if not folder_config.enabled:
                continue
            
            # Connect to network folder if needed
            if folder_config.type == "network":
                if not self._connect_network_folder(folder_config):
                    continue
            
            # Scan folder for files
            try:
                if not folder_config.path.exists():
                    logger.warning(f"Folder not found: {folder_config.name}")
                    continue
                
                for file_path in folder_config.path.iterdir():
                    if not file_path.is_file():
                        continue
                    
                    # Check if it's a supported file type
                    if file_path.suffix.lower() not in ['.csv', '.xlsx', '.xls']:
                        continue
                    
                    # Check if already processed
                    unique_key = f"{folder_config.name}:{file_path.name}"
                    if unique_key in self.processed_files:
                        #continue
                        pass
                    
                    # Check if file is still being written
                    if self._is_file_stable(file_path):
                        new_files.append((file_path, folder_config.name))
                        
            except PermissionError:
                logger.error(f"Permission denied accessing {folder_config.name}")
            except Exception as e:
                logger.error(f"Error scanning {folder_config.name}: {e}")
        
        return new_files
    
    def _is_file_stable(self, file_path: Path, wait_time: int = 2) -> bool:
        """Check if file size is stable (not currently being written)"""
        try:
            size1 = file_path.stat().st_size
            time.sleep(wait_time)
            size2 = file_path.stat().st_size
            return size1 == size2
        except Exception as e:
            logger.error(f"Error checking file stability: {e}")
            return False
    
    def move_to_processed(self, file_path: Path, source_folder: str) -> Path:
        """Move successfully processed file to processed folder"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Include source folder in filename to track origin
            source_prefix = source_folder.replace(" ", "_").replace("\\", "_").replace("/", "_")
            new_name = f"{source_prefix}_{file_path.stem}_{timestamp}{file_path.suffix}"
            destination = self.processed_folder / new_name
            
            shutil.copy2(str(file_path), str(destination))  # Copy first
            file_path.unlink()  # Then delete original
            
           #unique_key = f"{source_folder}:{file_path.name}"
           # self.processed_files.add(unique_key)
            
            logger.info(f"Moved to processed: {file_path.name} -> {new_name}")
            return destination
            
        except Exception as e:
            logger.error(f"Error moving file to processed: {e}")
            raise
    
    def move_to_failed(self, file_path: Path, source_folder: str, error_message: str = "") -> Path:
        """Move failed file to failed folder with error info"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_prefix = source_folder.replace(" ", "_").replace("\\", "_").replace("/", "_")
            new_name = f"{source_prefix}_{file_path.stem}_FAILED_{timestamp}{file_path.suffix}"
            destination = self.failed_folder / new_name
            
            shutil.copy2(str(file_path), str(destination))
            file_path.unlink()
            
            unique_key = f"{source_folder}:{file_path.name}"
            self.processed_files.add(unique_key)
            
            # Create error log file
            if error_message:
                error_file = destination.with_suffix('.error.txt')
                error_file.write_text(
                    f"Source: {source_folder}\n"
                    f"File: {file_path.name}\n"
                    f"Error: {error_message}\n"
                    f"Time: {datetime.now()}"
                )
            
            logger.error(f"Moved to failed: {file_path.name} -> {new_name}")
            return destination
            
        except Exception as e:
            logger.error(f"Error moving file to failed: {e}")
            raise
    
    def mark_as_processed(self, filename: str, source_folder: str):
        """Mark a file as processed without moving it"""
        unique_key = f"{source_folder}:{filename}"
        self.processed_files.add(unique_key)

