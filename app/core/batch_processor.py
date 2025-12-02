"""
Advanced batch processor with intelligent multi-level retry system
Processes in batches of 20 with 7-second delays
Automatically retries failed requests multiple times until success or max retries

CHANGES MADE:
1. _retry_failed_waybills: Now handles List[Tuple[waybill, binID]] (Line 54)
2. _process_with_multi_retry: Now accepts and processes tracking_data tuples (Line 134)
3. process_batch: Now accepts List[Tuple[waybill, binID]] (Line 269)
4. process_large_batch: Now accepts List[Tuple[waybill, binID]] (Line 446)
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import uuid

from app.core.dhl_services import DHLAPIService
from app.repositories import TrackingRepository, APIUsageRepository
from app.utils.config import settings

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Intelligent batch processor with multi-level retry system
    Features:
    - Processes 5 waybills per batch (configurable)
    - 7-second delays between batches
    - Automatic retry up to MAX_RETRIES times
    - Maintains binID association throughout processing
    """
    
    def __init__(self, dhl_service: DHLAPIService):
        self.dhl_service = dhl_service
        self.batch_size = 5
        self.batch_delay = 7
        self.daily_limit = settings.DHL_DAILY_LIMIT
        self.max_retries = 5
        self.retry_delay = 10
    
    def generate_batch_id(self) -> str:
        """Generate unique batch ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"batch_{timestamp}_{unique_id}"
    
    async def _retry_failed_waybills(
        self,
        failed_waybills: List[Tuple[str, Optional[str]]],  # UPDATED: Now List[Tuple]
        retry_attempt: int,
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository
    ) -> Dict[str, Any]:
        """
        Retry failed waybills with exponential backoff
        
        UPDATED: Now handles List[Tuple[waybill, binID]]
        
        Args:
            failed_waybills: List of tuples [(waybill, binID), ...]
            retry_attempt: Current retry attempt number
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            
        Returns:
            Dictionary with successful and still-failed results
        """
        if not failed_waybills:
            return {"successful": [], "failed": []}
        
        delay = self.retry_delay + (5 * (retry_attempt - 1))
        
        logger.info(f"Retry attempt {retry_attempt}/{self.max_retries} for {len(failed_waybills)} waybills")
        logger.info(f"Waiting {delay} seconds before retry...")
        await asyncio.sleep(delay)
        
        # Process failed waybills with binID
        retry_results = await self.dhl_service.track_batch(failed_waybills, delay=0.5)
        
        successful = []
        still_failed = []
        
        for result in retry_results:
            tracking_number = result.get('tracking_number')
            bin_id = result.get('bin_id')  # Preserve binID
            
            if result.get('is_successful'):
                successful.append(result)
                logger.info(f"Retry success: {tracking_number} (binID: {bin_id})")
                
                try:
                    tracking_repo.upsert(result)
                    api_usage_repo.increment_usage(success=True)
                except Exception as e:
                    logger.error(f"Error saving retry result: {str(e)}")
            else:
                still_failed.append((tracking_number, bin_id))  # Keep as tuple
                logger.warning(f"Retry failed: {tracking_number} (binID: {bin_id})")
                api_usage_repo.increment_usage(success=False)
        
        return {
            "successful": successful,
            "failed": still_failed
        }
    
    async def _process_with_multi_retry(
        self,
        tracking_data: List[Tuple[str, Optional[str]]],  # UPDATED: Now List[Tuple]
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository,
        batch_id: str
    ) -> Dict[str, Any]:
        """
        Process waybills with multi-level retry system
        Keeps retrying failed waybills until success or max retries reached
        
        UPDATED: Now handles List[Tuple[waybill, binID]]
        
        Args:
            tracking_data: List of tuples [(waybill, binID), ...]
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            batch_id: Batch identifier
            
        Returns:
            Processing results with all attempts combined
        """
        all_successful_results = []
        failed_waybills = []
        total_api_calls = 0
        
        logger.info(f"Processing {len(tracking_data)} waybills in batches of {self.batch_size}")
        
        # First pass: Process in batches
        for i in range(0, len(tracking_data), self.batch_size):
            batch = tracking_data[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(tracking_data) + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} waybills)")
            
            batch_results = await self.dhl_service.track_batch(batch, delay=0.2)
            total_api_calls += len(batch)
            
            for result in batch_results:
                tracking_number = result.get('tracking_number')
                bin_id = result.get('bin_id')
                
                if result.get('is_successful'):
                    result['batch_id'] = batch_id
                    all_successful_results.append(result)
                    
                    try:
                        tracking_repo.upsert(result)
                        api_usage_repo.increment_usage(success=True)
                    except Exception as e:
                        logger.error(f"Error saving result: {str(e)}")
                else:
                    failed_waybills.append((tracking_number, bin_id))  # Store as tuple
            
            if i + self.batch_size < len(tracking_data):
                logger.info(f"Waiting {self.batch_delay} seconds before next batch...")
                await asyncio.sleep(self.batch_delay)
        
        # Multi-level retry for failed waybills
        if failed_waybills:
            logger.info(f"{len(failed_waybills)} waybills failed initial processing")
            logger.info(f"Starting multi-level retry system (max {self.max_retries} attempts)")
            
            current_failed = failed_waybills.copy()
            
            for retry_attempt in range(1, self.max_retries + 1):
                if not current_failed:
                    break
                
                logger.info(f"\n{'='*80}")
                logger.info(f"RETRY ATTEMPT {retry_attempt}/{self.max_retries}")
                logger.info(f"Retrying {len(current_failed)} failed waybills")
                logger.info(f"{'='*80}")
                
                retry_result = await self._retry_failed_waybills(
                    current_failed,
                    retry_attempt,
                    tracking_repo,
                    api_usage_repo
                )
                
                for success in retry_result["successful"]:
                    success['batch_id'] = batch_id
                    all_successful_results.append(success)
                
                current_failed = retry_result["failed"]
                total_api_calls += len(retry_result["successful"]) + len(current_failed)
                
                logger.info(f"\nRetry {retry_attempt} Summary:")
                logger.info(f"Succeeded: {len(retry_result['successful'])}")
                logger.info(f"Still failing: {len(current_failed)}")
                
                if not current_failed:
                    logger.info(f"Yes: All waybills processed successfully!")
                    break
                elif retry_attempt < self.max_retries:
                    logger.info(f"Will retry again (attempt {retry_attempt + 1}/{self.max_retries})")
            
            if current_failed:
                logger.warning(f"\n{len(current_failed)} waybills still failed after {self.max_retries} retry attempts")
                
                for waybill, bin_id in current_failed:
                    try:
                        tracking_repo.upsert({
                            'tracking_number': waybill,
                            'bin_id': bin_id,  # Save binID even for failed records
                            'batch_id': batch_id,
                            'is_successful': False,
                            'error_message': f'Failed after {self.max_retries} retry attempts',
                            'last_checked': datetime.utcnow()
                        })
                    except Exception as e:
                        logger.error(f"Error saving failed result: {str(e)}")
            else:
                logger.info(f"\nSUCCESS! All waybills processed after retries!")
        else:
            logger.info(f"Perfect! All waybills succeeded on first attempt!")
        
        return {
            "successful_results": all_successful_results,
            "failed_waybills": current_failed if failed_waybills else [],
            "total_api_calls": total_api_calls
        }
    
    async def process_batch(
        self,
        tracking_data: List[Tuple[str, Optional[str]]],  # UPDATED: Now List[Tuple]
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository
    ) -> Dict[str, Any]:
        """
        Main batch processing method with multi-level retry
        User sees seamless results - all retry logic happens in background
        
        UPDATED: Now accepts List[Tuple[waybill, binID]]
        
        Args:
            tracking_data: List of tuples [(waybill, binID), ...]
            tracking_repo: Repository for tracking records
            api_usage_repo: Repository for API usage tracking
            
        Returns:
            Complete results appearing as single operation to user
        """
        start_time = datetime.now()
        batch_id = self.generate_batch_id()
        
        results = {
            "batch_id": batch_id,
            "total_requested": len(tracking_data),
            "successful": 0,
            "failed": 0,
            "results": [],
            "processing_time": 0,
            "api_calls_made": 0
        }
        
        try:
            remaining = api_usage_repo.get_remaining_requests(self.daily_limit)
            
            if remaining <= 0:
                logger.warning("Daily API limit reached")
                results["failed"] = len(tracking_data)
                results["error"] = "Daily API limit reached"
                return results
            
            if len(tracking_data) > remaining:
                logger.warning(f"Limiting batch from {len(tracking_data)} to {remaining} (remaining quota)")
                tracking_data = tracking_data[:remaining]
                results["total_requested"] = len(tracking_data)
            
            # Check for existing cached records
            waybills_only = [waybill for waybill, _ in tracking_data]
            existing_records = tracking_repo.get_multiple(waybills_only)
            existing_map = {r.tracking_number: r for r in existing_records}
            
            new_tracking_data = []
            cached_results = []
            
            for waybill, bin_id in tracking_data:
                if waybill in existing_map:
                    record = existing_map[waybill]
                    # Update binID if it was None before
                    if bin_id and not record.bin_id:
                        record.bin_id = bin_id
                        tracking_repo.update(waybill, {'bin_id': bin_id})
                    
                    if record.last_checked and (datetime.utcnow() - record.last_checked).seconds < 3600:
                        cached_results.append(record)
                        logger.info(f"Using cached data for {waybill} (binID: {bin_id})")
                    else:
                        new_tracking_data.append((waybill, bin_id))
                else:
                    new_tracking_data.append((waybill, bin_id))
            
            if new_tracking_data:
                processing_result = await self._process_with_multi_retry(
                    new_tracking_data,
                    tracking_repo,
                    api_usage_repo,
                    batch_id
                )
                
                successful_records = [
                    tracking_repo.get_by_tracking_number(r['tracking_number'])
                    for r in processing_result["successful_results"]
                ]
                successful_records = [r for r in successful_records if r]
                
                results["results"].extend(successful_records)
                results["successful"] = len(successful_records)
                results["failed"] = len(processing_result["failed_waybills"])
                results["api_calls_made"] = processing_result["total_api_calls"]
            
            results["results"].extend(cached_results)
            results["successful"] += len(cached_results)
            
            end_time = datetime.now()
            results["processing_time"] = (end_time - start_time).total_seconds()
            
            logger.info(f"\n{'='*80}")
            logger.info(f"BATCH {batch_id} COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"Successful: {results['successful']}/{results['total_requested']}")
            logger.info(f"Failed: {results['failed']}/{results['total_requested']}")
            logger.info(f"API calls made: {results['api_calls_made']}")
            logger.info(f"Processing time: {results['processing_time']:.2f}s")
            logger.info(f"{'='*80}\n")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}")
            results["failed"] = len(tracking_data)
            results["error"] = str(e)
            return results
    
    async def process_large_batch(
        self,
        tracking_data: List[Tuple[str, Optional[str]]],  # UPDATED: Now List[Tuple]
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Process large batch - uses same multi-retry system
        
        UPDATED: Now accepts List[Tuple[waybill, binID]]
        
        Args:
            tracking_data: List of tuples [(waybill, binID), ...]
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            progress_callback: Optional callback for progress updates
            
        Returns:
            Complete results with all retries processed
        """
        logger.info(f"Starting large batch processing for {len(tracking_data)} waybills")
        logger.info(f"Retry strategy: Up to {self.max_retries} attempts per failed waybill")
        
        result = await self.process_batch(
            tracking_data,
            tracking_repo,
            api_usage_repo
        )
        
        return result
    
    def calculate_estimated_time(self, count: int) -> float:
        """Calculate estimated processing time including retries"""
        batches = (count + self.batch_size - 1) // self.batch_size
        base_time = (batches - 1) * self.batch_delay
        processing_time = count * 0.5
        retry_buffer = (count * 0.1) * 2 * (self.retry_delay + 5)
        total = base_time + processing_time + retry_buffer
        return total

