"""
DHL Waybill Validation Scanner
Specialized scanner for finding and processing dhl_waybill_validation files
Searches the entire DHL network folder with optimized algorithms
"""
import os
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import fnmatch

logger = logging.getLogger(__name__)


class WaybillValidatorScanner:
    """
    Specialized scanner for DHL waybill validation files
    Uses fast search algorithm to find files in large directory structures
    """
    
    def __init__(
        self,
        search_root: str = "\\\\soj3serv07\\Production To Office\\DHL\\",
        target_filename: str = "dhl_waybill_validation",
        processed_folder: str = "./data/processed",
        failed_folder: str = "./data/failed"
    ):
        """
        Initialize waybill validator scanner
        
        Args:
            search_root: Root directory to search
            target_filename: Base filename to search for (without extension)
            processed_folder: Where to move processed files
            failed_folder: Where to move failed files
        """
        self.search_root = Path(search_root)
        self.target_filename = target_filename.lower()
        self.processed_folder = Path(processed_folder)
        self.failed_folder = Path(failed_folder)
        
        # Excel file extensions to search for
        self.excel_extensions = ['.xlsx', '.xls', '.xlsm', '.csv']
        
        # Track last found file to avoid reprocessing
        self.last_processed_file = None
        
        # Ensure output folders exist
        self.processed_folder.mkdir(parents=True, exist_ok=True)
        self.failed_folder.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"WaybillValidatorScanner initialized")
        logger.info(f"Search root: {self.search_root}")
        logger.info(f"Target file: {self.target_filename}.*")
    
    def _is_target_file(self, filepath: Path) -> bool:
        """
        Check if file matches our target filename pattern
        
        Args:
            filepath: Path to check
            
        Returns:
            True if file matches target pattern
        """
        if not filepath.is_file():
            return False
        
        # Check extension
        if filepath.suffix.lower() not in self.excel_extensions:
            return False
        
        # Check filename (case-insensitive)
        filename_stem = filepath.stem.lower()
        
        # Exact match or pattern match
        if filename_stem == self.target_filename:
            return True
        
        # Allow for variations like dhl_waybill_validation_2024
        if filename_stem.startswith(self.target_filename):
            return True
        
        return False
    
    def _breadth_first_search(self) -> Optional[Path]:
        """
        Fast breadth-first search algorithm
        Searches level by level, prioritizing root directory
        Good for files likely to be in root or near root
        
        Returns:
            Path to file if found, None otherwise
        """
        try:
            # First check root directory (most likely location)
            logger.info(f"Quick scan: Checking root directory first...")
            
            for item in self.search_root.iterdir():
                if self._is_target_file(item):
                    logger.info(f"✓ Found in root: {item.name}")
                    return item
            
            # If not in root, do breadth-first search of subdirectories
            logger.info(f"File not in root, searching subdirectories...")
            
            directories_to_search = [self.search_root]
            searched_count = 0
            max_depth = 5  # Limit search depth for performance
            current_depth = 0
            
            while directories_to_search and current_depth < max_depth:
                next_level_dirs = []
                
                for directory in directories_to_search:
                    try:
                        searched_count += 1
                        
                        # Log progress every 10 directories
                        if searched_count % 10 == 0:
                            logger.info(f"Searched {searched_count} directories...")
                        
                        for item in directory.iterdir():
                            # Check if it's our target file
                            if self._is_target_file(item):
                                logger.info(f"✓ Found after searching {searched_count} directories: {item.name}")
                                return item
                            
                            # Add subdirectories for next level
                            if item.is_dir():
                                next_level_dirs.append(item)
                    
                    except PermissionError:
                        logger.warning(f"Permission denied: {directory}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error accessing {directory}: {e}")
                        continue
                
                directories_to_search = next_level_dirs
                current_depth += 1
            
            logger.info(f"File not found after searching {searched_count} directories")
            return None
            
        except Exception as e:
            logger.error(f"Error in breadth-first search: {e}")
            return None
    
    def _glob_search(self) -> Optional[Path]:
        """
        Fast glob-based search as fallback
        Uses pattern matching for quick file location
        
        Returns:
            Path to file if found, None otherwise
        """
        try:
            logger.info("Using glob search as fallback...")
            
            # Search for files matching pattern
            patterns = [f"{self.target_filename}{ext}" for ext in self.excel_extensions]
            
            for pattern in patterns:
                # Search root directory first
                matches = list(self.search_root.glob(pattern))
                if matches:
                    logger.info(f"✓ Glob found: {matches[0].name}")
                    return matches[0]
                
                # Search subdirectories (limited depth)
                matches = list(self.search_root.glob(f"*/{pattern}"))
                if matches:
                    logger.info(f"✓ Glob found in subdirectory: {matches[0].name}")
                    return matches[0]
                
                matches = list(self.search_root.glob(f"*/*/{pattern}"))
                if matches:
                    logger.info(f"✓ Glob found in nested subdirectory: {matches[0].name}")
                    return matches[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error in glob search: {e}")
            return None
    
    def find_validation_file(self) -> Optional[Tuple[Path, str]]:
        """
        Find the DHL waybill validation file using optimized search
        
        Returns:
            Tuple of (file_path, source_name) if found, None otherwise
        """
        try:
            logger.info("=" * 80)
            logger.info("SEARCHING FOR DHL WAYBILL VALIDATION FILE")
            logger.info("=" * 80)
            
            # Check if search root exists
            if not self.search_root.exists():
                logger.error(f"Search root does not exist: {self.search_root}")
                return None
            
            # Try breadth-first search first (fast for nearby files)
            file_path = self._breadth_first_search()
            
            # If not found, try glob search as fallbackss
            if not file_path:
                file_path = self._glob_search()
            
            if not file_path:
                logger.info("No validation file found")
                return None
            
            # Check if this is a new file (not already processed)
            if self.last_processed_file == file_path.name:
                logger.info(f"File already processed this session: {file_path.name}")
                return None
            
            # Check if file is stable (not being written)
            if not self._is_file_stable(file_path):
                logger.info(f"File is still being written: {file_path.name}")
                return None
            
            logger.info(f"✓ VALIDATION FILE READY: {file_path.name}")
            logger.info(f"  Location: {file_path.parent}")
            logger.info(f"  Size: {file_path.stat().st_size / 1024:.2f} KB")
            
            return (file_path, "DHL Waybill Validator")
            
        except Exception as e:
            logger.error(f"Error finding validation file: {e}")
            return None
    
    def _is_file_stable(self, file_path: Path, wait_time: int = 2) -> bool:
        """
        Check if file is stable (not currently being written)
        
        Args:
            file_path: Path to check
            wait_time: Seconds to wait between size checks
            
        Returns:
            True if file size is stable
        """
        try:
            import time
            
            size1 = file_path.stat().st_size
            time.sleep(wait_time)
            size2 = file_path.stat().st_size
            
            return size1 == size2
            
        except Exception as e:
            logger.error(f"Error checking file stability: {e}")
            return False
    
    def move_to_processed(self, file_path: Path) -> Path:
        """
        Move successfully processed file to processed folder
        
        Args:
            file_path: Path to file to move
            
        Returns:
            New path of moved file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"waybill_validation_{file_path.stem}_{timestamp}{file_path.suffix}"
            destination = self.processed_folder / new_name
            
            import shutil
            shutil.copy2(str(file_path), str(destination))
            file_path.unlink()
            
            self.last_processed_file = file_path.name
            
            logger.info(f"✓ Moved to processed: {new_name}")
            return destination
            
        except Exception as e:
            logger.error(f"Error moving file to processed: {e}")
            raise
    
    def move_to_failed(self, file_path: Path, error_message: str = "") -> Path:
        """
        Move failed file to failed folder with error info
        
        Args:
            file_path: Path to file to move
            error_message: Error message to save
            
        Returns:
            New path of moved file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"waybill_validation_{file_path.stem}_FAILED_{timestamp}{file_path.suffix}"
            destination = self.failed_folder / new_name
            
            import shutil
            shutil.copy2(str(file_path), str(destination))
            file_path.unlink()
            
            self.last_processed_file = file_path.name
            
            # Create error log file
            if error_message:
                error_file = destination.with_suffix('.error.txt')
                error_file.write_text(
                    f"File: {file_path.name}\n"
                    f"Error: {error_message}\n"
                    f"Time: {datetime.now()}\n"
                )
            
            logger.error(f"✗ Moved to failed: {new_name}")
            return destination
            
        except Exception as e:
            logger.error(f"Error moving file to failed: {e}")
            raise
    
    def reset_tracking(self):
        """Reset last processed file tracking"""
        self.last_processed_file = None
        logger.info("Tracking reset - will reprocess validation files")