"""
File Watcher--dog watche approach :)
Monotors inbox folder for new files and triggers process if thereExist a file
"""

import os
import time
import shutil
import logging
from pathlib import Path
from typing import List,Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class FileWatcher:
    """
    Keep a close eye to the inbox folder for a new CSV/Excell files
    If therExist then it triggers the process--More like a wistle blower
    """

    def __init__(self, inbox_folder: str, processed_folder:str, failed_folder:str):
        """..."""
        self.inbox_folder = Path(inbox_folder)
        self.processed_folder = Path(processed_folder)
        self.failed_folder = Path(failed_folder)

        #Creating folders if they don't exist--this is a saafety  maesure when migrating to a different working space
        self.inbox_folder.mkdir(parents=True, exist_ok=True)
        self.processed_folder.mkdir(parents=True, exist_ok=True)
        self.failed_folder.mkdir(parents=True, exist_ok=True)

        #Dublication Avoidance :)
        self.processed_files = set()
        logger.info(f"File Watcher initialized")
        logger.info(f"Inbox: {self.inbox_folder}")
        logger.info(f"Processed: {self.processed_folder}")
        logger.info(f"Failed: {self.failed_folder}")

    def get_new_file(self):
        """...
        Retrieves new files in the inbox folder
        and returns files that don't have the processed tag :)
        """

        new_files = []

        if not self.inbox_folder.exists():
            return new_files
        for file_path in self.inbox_folder.iterdir():
            if not file_path.self.is_file():
                continue
            
            #Now we make sure that the file is CSV?orxlsx

            if file_path.suffix.lower() not in ['.csv','xlsx','xls']:
                continue
            # Checking if file has a processed tag
            if file_path.name in self.processed_files:
                continue
            if self._is_file_stable(file_path):
                new_files.append(file_path)

        return new_files

    def _is_file_stable(self,file_path:Path,wait_time:int = 2) -> bool:
        """...
        Check of the file is stable for processing
        """       
        try:
            size1 = file_path.stat().st_size
            time.sleep(wait_time)
            size2 = file_path.stat().st_size
            return size1==size2
        except Exception as e:
            logger.error(f"Error checking file stability:{e}")
            return False
        
    def move_to_processed(self,file_path:Path) ->Path:
        """
        Move processed file the respective folder :)

        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            destination = self.failed_folder / new_name

            shutil.move(str(file_path), str(destination))
            self.processed_files.add(file_path.name)

            logger.info(f"Moved tp processed: {file_path.name} -> {new_name}")
            return destination
        except Exception as e:
            logger.error(f"Error moving file to processed: {e}")

    def move_to_failed(self,file_path:Path, error_message:str = "")-> Path:
        """
        moving to the failed folder  with the error info if the file did not process

        """
        try:
             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
             new_name = f"{file_path.stem}_Failed_{timestamp}{file_path.suffix}"
             destination  =self.failed_folder /new_name

             shutil.move(str(file_path),str(destination))
             self.processed_files.add(file_path.name)

             # error log file
             if error_message:
                 error_file = destination.with_suffix('.error.txt')
                 error_file.write_text(f"Error:{error_message}\nTime: {destination.now()}")
             logger.error(f"Moved to failed: {file_path.name}-> {datetime.now()}")  
             return destination
        except Exception as e:
            logger.error(f"Error moving file to failed: {e}")
            raise

    def mark_as_processed(self,filename: str):
        """Set a processed tag"""

        self.processed_files.add(filename)       


       
        

