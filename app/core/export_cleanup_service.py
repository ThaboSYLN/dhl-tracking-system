"""
Export Cleanup Service
Manages export file lifecycle: active → network archive → deletion
"""
import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import os

logger = logging.getLogger(__name__)


class ExportCleanupService:
    """
    Manages export file cleanup and archiving
    - Files < 3 days: Stay in ./exports/
    - Files > 3 days: Move to network archive
    - Files > 30 days in archive: Delete
    """
    
    def __init__(
        self,
        exports_folder: str = "./exports",
        network_archive_path: str = "\\\\soj3serv07\\Production To Office\\DHL\\exports\\archive",
        active_retention_days: int = 3,  # for testing change data type tppe to float and assign 0.0006944--one minutes in days
        archive_retention_days: int = 30 #for testing change data type tppe to float and assign 0,00138889--2 minutes in days
    ):
        self.exports_folder = Path(exports_folder)
        self.network_archive_path = Path(network_archive_path)
        self.active_retention_days = active_retention_days
        self.archive_retention_days = archive_retention_days
        
        # Ensure local exports folder exists
        self.exports_folder.mkdir(parents=True, exist_ok=True)
        
        # Try to create network archive folder
        try:
            self.network_archive_path.mkdir(parents=True, exist_ok=True)
            self.network_available = True
            logger.info(f"--> Network archive available: {self.network_archive_path}")
        except Exception as e:
            self.network_available = False
            logger.warning(f"-->X<--Network archive unavailable: {e}")
            logger.warning("Export cleanup will continue with local operations only")
    
    def get_file_age_days(self, file_path: Path) -> int:
        """Get file age in days"""
        try:
            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            age = datetime.now() - file_time
            return age.days
        except Exception as e:
            logger.error(f"Error getting file age for {file_path}: {e}")
            return 0
    
    def move_to_archive(self, file_path: Path) -> bool:
        """
        Move file from local exports to network archive
        Returns True if successful, False otherwise
        """
        if not self.network_available:
            logger.warning(f"Cannot archive {file_path.name} - network unavailable")
            return False
        
        try:
            destination = self.network_archive_path / file_path.name
            
            # Copy to network first
            shutil.copy2(str(file_path), str(destination))
            
            # Then delete local file
            file_path.unlink()
            
            logger.info(f"[folder_name]-->Archived: {file_path.name} → Network archive")
            return True
            
        except Exception as e:
            logger.error(f"Failed to archive {file_path.name}: {e}")
            return False
    
    def delete_from_archive(self, file_path: Path) -> bool:
        """
        Delete old file from network archive
        Returns True if successful, False otherwise
        """
        try:
            file_path.unlink()
            logger.info(f">|< Deleted from archive: {file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {file_path.name}: {e}")
            return False
    
    def cleanup_exports(self) -> Dict[str, int]:
        """
        Run cleanup process:
        1. Move old files (> 3 days) from exports to network archive
        2. Delete very old files (> 30 days) from archive
        
        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            "files_archived": 0,
            "files_deleted": 0,
            "errors": 0,
            "active_files": 0
        }
        
        logger.info(" Starting export cleanup process...")
        
        
        # Step 1: Archive old files from local exports--Will stay for 3 days and can be configured differently
        
        try:
            export_files = [
                f for f in self.exports_folder.iterdir()
                if f.is_file() and f.suffix.lower() in ['.pdf', '.docx']
            ]
            
            for file_path in export_files:
                age_days = self.get_file_age_days(file_path)
                
                if age_days >= self.active_retention_days:
                    # File is old enough to archive
                    if self.move_to_archive(file_path):
                        stats["files_archived"] += 1
                    else:
                        stats["errors"] += 1
                else:
                    # File is still active
                    stats["active_files"] += 1
                    
        except Exception as e:
            logger.error(f"Error during export archiving: {e}")
            stats["errors"] += 1
      
        # Step 2: Delete very old files from network archive--Ideally after 30 days/33 days total--> Can be configured differently as well
   
        if self.network_available:
            try:
                if self.network_archive_path.exists():
                    archive_files = [
                        f for f in self.network_archive_path.iterdir()
                        if f.is_file() and f.suffix.lower() in ['.pdf', '.docx']
                    ]
                    
                    for file_path in archive_files:
                        age_days = self.get_file_age_days(file_path)
                        
                        # Total age: 3 days active + 30 days archive = 33 days total
                        if age_days >= self.archive_retention_days:
                            if self.delete_from_archive(file_path):
                                stats["files_deleted"] += 1
                            else:
                                stats["errors"] += 1
                                
            except Exception as e:
                logger.error(f"Error during archive cleanup: {e}")
                stats["errors"] += 1
        
        # Log summary
        logger.info("--> Export cleanup complete:")
        logger.info(f"   - Active files (< {self.active_retention_days} days): {stats['active_files']}")
        logger.info(f"   - Files archived: {stats['files_archived']}")
        logger.info(f"   - Files deleted: {stats['files_deleted']}")
        if stats['errors'] > 0:
            logger.warning(f"   - Errors: {stats['errors']}")
        
        return stats
    
    def get_cleanup_status(self) -> Dict:
        """
        Get current status of export files
        """
        status = {
            "network_available": self.network_available,
            "active_files": [],
            "archived_files": [],
            "active_count": 0,
            "archived_count": 0,
            "active_size_mb": 0.0,
            "archived_size_mb": 0.0
        }
        
        # Check local exports
        try:
            if self.exports_folder.exists():
                for file_path in self.exports_folder.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.docx']:
                        age_days = self.get_file_age_days(file_path)
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        
                        status["active_files"].append({
                            "name": file_path.name,
                            "age_days": age_days,
                            "size_mb": round(size_mb, 2)
                        })
                        status["active_count"] += 1
                        status["active_size_mb"] += size_mb
        except Exception as e:
            logger.error(f"Error checking active files: {e}")
        
        # Check network archive--->
        if self.network_available:
            try:
                if self.network_archive_path.exists():
                    for file_path in self.network_archive_path.iterdir():
                        if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.docx']:
                            age_days = self.get_file_age_days(file_path)
                            size_mb = file_path.stat().st_size / (1024 * 1024)
                            
                            status["archived_files"].append({
                                "name": file_path.name,
                                "age_days": age_days,
                                "size_mb": round(size_mb, 2)
                            })
                            status["archived_count"] += 1
                            status["archived_size_mb"] += size_mb
            except Exception as e:
                logger.error(f"Error checking archived files: {e}")
        
        # Round totals
        status["active_size_mb"] = round(status["active_size_mb"], 2)
        status["archived_size_mb"] = round(status["archived_size_mb"], 2)
        
        return status


# Create service instance
export_cleanup_service = ExportCleanupService()

