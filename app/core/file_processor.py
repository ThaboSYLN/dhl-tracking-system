"""
File processor for CSV and Excel files
Handles file upload, validation, and parsing
Follows Single Responsibility Principle

CHANGES MADE:
1. extract_tracking_numbers_from_csv: Now returns List[Tuple[waybill, binID]] (Lines 88-150)
2. extract_tracking_numbers_from_excel: Now returns List[Tuple[waybill, binID]] (Lines 152-214)
3. Added _find_column helper method to find columns flexibly (Lines 73-86)
4. process_file: Returns List[Tuple[waybill, binID]] (Lines 216-274)
"""
import pandas as pd
import os
from typing import List, Dict, Any, Optional, Tuple
from fastapi import UploadFile, HTTPException
import aiofiles
import logging
from pathlib import Path

from app.utils.config import settings

logger = logging.getLogger(__name__)


class FileProcessorException(Exception):
    """Custom exception for file processing errors"""
    pass


class FileProcessor:
    """
    Service for processing uploaded CSV and Excel files
    Extracts tracking numbers and binIDs from files
    """
    
    def __init__(self):
        self.max_file_size = settings.MAX_FILE_SIZE
        self.allowed_extensions = settings.ALLOWED_EXTENSIONS
        self.upload_dir = settings.UPLOAD_DIR
        
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
    
    async def save_upload_file(self, file: UploadFile) -> str:
        """Save uploaded file to disk"""
        try:
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            file_extension = Path(file.filename).suffix
            filename = f"upload_{timestamp}{file_extension}"
            file_path = os.path.join(self.upload_dir, filename)
            
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            logger.info(f"File saved: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            raise FileProcessorException(f"Failed to save file: {str(e)}")
    
    def validate_file(self, file: UploadFile) -> bool:
        """Validate uploaded file"""
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(self.allowed_extensions)}"
            )
        
        if hasattr(file, 'size') and file.size > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {self.max_file_size / (1024*1024)}MB"
            )
        
        return True
    
    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """
        Find column by checking multiple possible names (case-insensitive)
        
        Args:
            df: DataFrame to search
            possible_names: List of possible column names
            
        Returns:
            Actual column name if found, None otherwise
        """
        for col in df.columns:
            if col.lower().strip() in [name.lower() for name in possible_names]:
                return col
        return None
    
    def extract_tracking_numbers_from_csv(self, file_path: str) -> List[Tuple[str, Optional[str]]]:
        """
        Extract tracking numbers and binIDs from CSV file
        
        UPDATED: Now extracts both waybill and binID columns
        
        Returns:
            List of tuples: [(waybill, binID), ...]
        """
        try:
            df = pd.read_csv(file_path)
            
            # Look for waybill/tracking column
            waybill_columns = [
                'waybill', 'tracking_number', 'tracking', 'waybill_number',
                'tracking_no', 'waybill_no', 'trackingnumber', 'waybillnumber',
                'awb', 'tracking number', 'waybill number'
            ]
            
            # Look for binID column
            binid_columns = [
                'binid', 'bin_id', 'bin', 'binID', 'bin ID', 'bin-id',
                'bin_no', 'binno', 'bin number', 'binnumber', 'location',
                'bin_location', 'binlocation'
            ]
            
            waybill_col = self._find_column(df, waybill_columns)
            binid_col = self._find_column(df, binid_columns)
            
            # If no waybill column found, use first column
            if waybill_col is None:
                if len(df.columns) == 0:
                    raise FileProcessorException("CSV file has no columns")
                waybill_col = df.columns[0]
                logger.warning(f"No waybill column found, using first column: {waybill_col}")
            
            # If file has 2 columns but no binID column detected, use second column
            if binid_col is None and len(df.columns) >= 2:
                # Get second column (assuming it's binID)
                second_col = df.columns[1] if df.columns[1] != waybill_col else None
                if second_col:
                    binid_col = second_col
                    logger.info(f"Using second column as binID: {binid_col}")
            
            # Extract waybills
            waybills = df[waybill_col].astype(str).str.strip().tolist()
            
            # Extract binIDs if column exists
            if binid_col:
                bin_ids = df[binid_col].astype(str).str.strip().tolist()
            else:
                bin_ids = [None] * len(waybills)
                logger.info("No binID column found, all binIDs will be None")
            
            # Combine and clean
            tracking_data = []
            for waybill, bin_id in zip(waybills, bin_ids):
                # Clean waybill
                if waybill and waybill.lower() not in ['nan', 'none', '']:
                    waybill = waybill.upper()
                    # Clean binID
                    if bin_id and bin_id.lower() not in ['nan', 'none', '']:
                        tracking_data.append((waybill, bin_id))
                    else:
                        tracking_data.append((waybill, None))
            
            logger.info(f"Extracted {len(tracking_data)} tracking records from CSV")
            return tracking_data
            
        except Exception as e:
            logger.error(f"Error extracting from CSV: {str(e)}")
            raise FileProcessorException(f"Failed to extract from CSV: {str(e)}")
    
    def extract_tracking_numbers_from_excel(self, file_path: str) -> List[Tuple[str, Optional[str]]]:
        """
        Extract tracking numbers and binIDs from Excel file
        
        UPDATED: Now extracts both waybill and binID columns
        
        Returns:
            List of tuples: [(waybill, binID), ...]
        """
        try:
            df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
            
            # Look for waybill/tracking column
            waybill_columns = [
                'waybill', 'tracking_number', 'tracking', 'waybill_number',
                'tracking_no', 'waybill_no', 'trackingnumber', 'waybillnumber',
                'awb', 'tracking number', 'waybill number'
            ]
            
            # Look for binID column
            binid_columns = [
                'binid', 'bin_id', 'bin', 'binID', 'bin ID', 'bin-id',
                'bin_no', 'binno', 'bin number', 'binnumber', 'location',
                'bin_location', 'binlocation'
            ]
            
            waybill_col = self._find_column(df, waybill_columns)
            binid_col = self._find_column(df, binid_columns)
            
            # If no waybill column found, use first column
            if waybill_col is None:
                if len(df.columns) == 0:
                    raise FileProcessorException("Excel file has no columns")
                waybill_col = df.columns[0]
                logger.warning(f"No waybill column found, using first column: {waybill_col}")
            
            # If file has 2 columns but no binID column detected, use second column
            if binid_col is None and len(df.columns) >= 2:
                second_col = df.columns[1] if df.columns[1] != waybill_col else None
                if second_col:
                    binid_col = second_col
                    logger.info(f"Using second column as binID: {binid_col}")
            
            # Extract waybills
            waybills = df[waybill_col].astype(str).str.strip().tolist()
            
            # Extract binIDs if column exists
            if binid_col:
                bin_ids = df[binid_col].astype(str).str.strip().tolist()
            else:
                bin_ids = [None] * len(waybills)
                logger.info("No binID column found, all binIDs will be None")
            
            # Combine and clean
            tracking_data = []
            for waybill, bin_id in zip(waybills, bin_ids):
                if waybill and waybill.lower() not in ['nan', 'none', '']:
                    waybill = waybill.upper()
                    if bin_id and bin_id.lower() not in ['nan', 'none', '']:
                        tracking_data.append((waybill, bin_id))
                    else:
                        tracking_data.append((waybill, None))
            
            logger.info(f"Extracted {len(tracking_data)} tracking records from Excel")
            return tracking_data
            
        except Exception as e:
            logger.error(f"Error extracting from Excel: {str(e)}")
            raise FileProcessorException(f"Failed to extract from Excel: {str(e)}")
    
    async def process_file(self, file: UploadFile) -> List[Tuple[str, Optional[str]]]:
        """
        Main method to process uploaded file
        
        UPDATED: Returns List[Tuple[waybill, binID]]
        
        Returns:
            List of tuples: [(waybill, binID), ...]
        """
        self.validate_file(file)
        file_path = await self.save_upload_file(file)
        
        try:
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.csv':
                tracking_data = self.extract_tracking_numbers_from_csv(file_path)
            elif file_extension in ['.xlsx', '.xls']:
                tracking_data = self.extract_tracking_numbers_from_excel(file_path)
            else:
                raise FileProcessorException(f"Unsupported file type: {file_extension}")
            
            # Remove duplicates while preserving order (based on waybill)
            seen = set()
            unique_tracking_data = []
            for waybill, bin_id in tracking_data:
                if waybill not in seen:
                    seen.add(waybill)
                    unique_tracking_data.append((waybill, bin_id))
            
            return unique_tracking_data
            
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not clean up file {file_path}: {str(e)}")


# Create file processor instance
file_processor = FileProcessor()

