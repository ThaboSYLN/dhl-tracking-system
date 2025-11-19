"""
File processor for CSV and Excel files
Handles file upload, validation, and parsing
Follows Single Responsibility Principle
"""
import pandas as pd
import os
from typing import List, Dict, Any, Optional
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
    Extracts tracking numbers from files
    """
    
    def __init__(self):
        self.max_file_size = settings.MAX_FILE_SIZE
        self.allowed_extensions = settings.ALLOWED_EXTENSIONS
        self.upload_dir = settings.UPLOAD_DIR
        
        # Ensure upload directory exists
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
    
    async def save_upload_file(self, file: UploadFile) -> str:
        """
        Save uploaded file to disk
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            Path to saved file
            
        Raises:
            FileProcessorException: If save fails
        """
        try:
            # Generate unique filename
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            file_extension = Path(file.filename).suffix
            filename = f"upload_{timestamp}{file_extension}"
            file_path = os.path.join(self.upload_dir, filename)
            
            # Save file asynchronously
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            logger.info(f"File saved: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            raise FileProcessorException(f"Failed to save file: {str(e)}")
    
    def validate_file(self, file: UploadFile) -> bool:
        """
        Validate uploaded file
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            True if valid
            
        Raises:
            HTTPException: If validation fails
        """
        # Check file extension
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(self.allowed_extensions)}"
            )
        
        # Check file size
        if hasattr(file, 'size') and file.size > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {self.max_file_size / (1024*1024)}MB"
            )
        
        return True
    
    def extract_tracking_numbers_from_csv(self, file_path: str) -> List[str]:
        """
        Extract tracking numbers from CSV file
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            List of tracking numbers
            
        Raises:
            FileProcessorException: If extraction fails
        """
        try:
            # Read CSV file
            df = pd.read_csv(file_path)
            
            # Look for tracking number column (case-insensitive)
            tracking_columns = [
                'tracking_number', 'tracking', 'waybill', 'waybill_number',
                'tracking_no', 'waybill_no', 'trackingnumber', 'waybillnumber'
            ]
            
            tracking_column = None
            for col in df.columns:
                if col.lower().strip() in tracking_columns:
                    tracking_column = col
                    break
            
            # If no matching column, use first column
            if tracking_column is None:
                if len(df.columns) == 0:
                    raise FileProcessorException("CSV file has no columns")
                tracking_column = df.columns[0]
                logger.warning(f"No tracking column found, using first column: {tracking_column}")
            
            # Extract and clean tracking numbers
            tracking_numbers = df[tracking_column].astype(str).str.strip().tolist()
            
            # Remove empty/nan values
            tracking_numbers = [tn for tn in tracking_numbers if tn and tn.lower() not in ['nan', 'none', '']]
            
            logger.info(f"Extracted {len(tracking_numbers)} tracking numbers from CSV")
            return tracking_numbers
            
        except Exception as e:
            logger.error(f"Error extracting from CSV: {str(e)}")
            raise FileProcessorException(f"Failed to extract from CSV: {str(e)}")
    
    def extract_tracking_numbers_from_excel(self, file_path: str) -> List[str]:
        """
        Extract tracking numbers from Excel file
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            List of tracking numbers
            
        Raises:
            FileProcessorException: If extraction fails
        """
        try:
            # Read Excel file (first sheet)
            df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
            
            # Look for tracking number column (same logic as CSV)
            tracking_columns = [
                'tracking_number', 'tracking', 'waybill', 'waybill_number',
                'tracking_no', 'waybill_no', 'trackingnumber', 'waybillnumber'
            ]
            
            tracking_column = None
            for col in df.columns:
                if col.lower().strip() in tracking_columns:
                    tracking_column = col
                    break
            
            # If no matching column, use first column
            if tracking_column is None:
                if len(df.columns) == 0:
                    raise FileProcessorException("Excel file has no columns")
                tracking_column = df.columns[0]
                logger.warning(f"No tracking column found, using first column: {tracking_column}")
            
            # Extract and clean tracking numbers
            tracking_numbers = df[tracking_column].astype(str).str.strip().tolist()
            
            # Remove empty/nan values
            tracking_numbers = [tn for tn in tracking_numbers if tn and tn.lower() not in ['nan', 'none', '']]
            
            logger.info(f"Extracted {len(tracking_numbers)} tracking numbers from Excel")
            return tracking_numbers
            
        except Exception as e:
            logger.error(f"Error extracting from Excel: {str(e)}")
            raise FileProcessorException(f"Failed to extract from Excel: {str(e)}")
    
    async def process_file(self, file: UploadFile) -> List[str]:
        """
        Main method to process uploaded file
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            List of tracking numbers
            
        Raises:
            FileProcessorException: If processing fails
        """
        # Validate file
        self.validate_file(file)
        
        # Save file
        file_path = await self.save_upload_file(file)
        
        try:
            # Determine file type and extract
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.csv':
                tracking_numbers = self.extract_tracking_numbers_from_csv(file_path)
            elif file_extension in ['.xlsx', '.xls']:
                tracking_numbers = self.extract_tracking_numbers_from_excel(file_path)
            else:
                raise FileProcessorException(f"Unsupported file type: {file_extension}")
            
            # Clean up tracking numbers
            tracking_numbers = [tn.upper().strip() for tn in tracking_numbers]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_tracking_numbers = []
            for tn in tracking_numbers:
                if tn not in seen:
                    seen.add(tn)
                    unique_tracking_numbers.append(tn)
            
            return unique_tracking_numbers
            
        finally:
            # Optionally clean up uploaded file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not clean up file {file_path}: {str(e)}")


# Create file processor instance
file_processor = FileProcessor()

