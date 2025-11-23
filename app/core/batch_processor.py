"""
Advanced batch processor with intelligent multi-level retry system
Processes in batches of 20 with 7-second delays
Automatically retries failed requests multiple times until success or max retries
"""
import asyncio
from typing import List, Dict, Any, Optional
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
    - Processes 20 waybills per batch---will change to maybe 10 or 15 if the test fail
    - 7-second delays between batches----will change to 10 if the test fail
    - Automatic retry up to MAX_RETRIES times---till all the waybill are processed with clear result not the HTTP error429--This is a brut_force approach {[:|]
    - Background retry processing (transparent to user)
    """
    
    def __init__(self, dhl_service: DHLAPIService):
        self.dhl_service = dhl_service
        self.batch_size = 5  # Process 20 waybills per batch
        self.batch_delay = 10  # 7 seconds between batches
        self.daily_limit = settings.DHL_DAILY_LIMIT
        self.max_retries = 5 # Maximum number of retry attempts
        self.retry_delay = 10  # 10 seconds between retry attempts
    
    def generate_batch_id(self) -> str:
        """Generate unique batch ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"batch_{timestamp}_{unique_id}"
    
    async def _retry_failed_waybills(
        self,
        failed_waybills: List[str],
        retry_attempt: int,
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository
    ) -> Dict[str, Any]:
        """
        Retry failed waybills with exponential backoff
        
        Args:
            failed_waybills: List of failed tracking numbers
            retry_attempt: Current retry attempt number (1, 2, 3...)
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            
        Returns:
            Dictionary with successful and still-failed results
        """
        if not failed_waybills:
            return {"successful": [], "failed": []}
        
        # Calculate delay with exponential backoff
        # Retry 1: 10s, Retry 2: 15s, Retry 3: 20s
        delay = self.retry_delay + (5 * (retry_attempt - 1))
        
        logger.info(f"Retry attempt {retry_attempt}/{self.max_retries} for {len(failed_waybills)} waybills")
        logger.info(f" Waiting {delay} seconds before retry...")
        await asyncio.sleep(delay)
        
        # Process failed waybills
        retry_results = await self.dhl_service.track_batch(failed_waybills, delay=0.5)
        
        successful = []
        still_failed = []
        
        for result in retry_results:
            tracking_number = result.get('tracking_number')
            
            if result.get('is_successful'):
                successful.append(result)
                logger.info(f"Retry success: {tracking_number}")
                
                # Update in database
                try:
                    tracking_repo.upsert(result)
                    api_usage_repo.increment_usage(success=True)
                except Exception as e:
                    logger.error(f"Error saving retry result: {str(e)}")
            else:
                still_failed.append(tracking_number)
                logger.warning(f"Retry failed: {tracking_number}")
                api_usage_repo.increment_usage(success=False)
        
        return {
            "successful": successful,
            "failed": still_failed
        }
    
    async def _process_with_multi_retry(
        self,
        tracking_numbers: List[str],
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository,
        batch_id: str
    ) -> Dict[str, Any]:
        """
        Process waybills with multi-level retry system
        Keeps retrying failed waybills until success or max retries reached
        
        Args:
            tracking_numbers: List of tracking numbers to process
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            batch_id: Batch identifier
            
        Returns:
            Processing results with all attempts combined
        """
        all_successful_results = []
        failed_waybills = []
        total_api_calls = 0
        
        # First pass: Process in batches of 20 with 7-second delays
        logger.info(f"Processing {len(tracking_numbers)} waybills in batches of {self.batch_size}")
        
        for i in range(0, len(tracking_numbers), self.batch_size):
            batch = tracking_numbers[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(tracking_numbers) + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} waybills)")
            
            # Process this batch
            batch_results = await self.dhl_service.track_batch(batch, delay=0.2)
            total_api_calls += len(batch)
            
            # Separate successful and failed
            for result in batch_results:
                tracking_number = result.get('tracking_number')
                
                if result.get('is_successful'):
                    result['batch_id'] = batch_id
                    all_successful_results.append(result)
                    
                    # Save to database
                    try:
                        tracking_repo.upsert(result)
                        api_usage_repo.increment_usage(success=True)
                    except Exception as e:
                        logger.error(f"Error saving result: {str(e)}")
                else:
                    failed_waybills.append(tracking_number)
            
            # Wait 7 seconds before next batch (except for last batch)
            if i + self.batch_size < len(tracking_numbers):
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
                
                # Retry failed waybills
                retry_result = await self._retry_failed_waybills(
                    current_failed,
                    retry_attempt,
                    tracking_repo,
                    api_usage_repo
                )
                
                # Add successful retries to results
                for success in retry_result["successful"]:
                    success['batch_id'] = batch_id
                    all_successful_results.append(success)
                
                # Update failed list
                current_failed = retry_result["failed"]
                total_api_calls += len(retry_result["successful"]) + len(current_failed)
                
                # Log retry summary
                logger.info(f"\nRetry {retry_attempt} Summary:")
                logger.info(f"Succeeded: {len(retry_result['successful'])}")
                logger.info(f"Still failing: {len(current_failed)}")
                
                if not current_failed:
                    logger.info(f"Yes:All waybills processed successfully!")
                    break
                elif retry_attempt < self.max_retries:
                    logger.info(f"Will retry again (attempt {retry_attempt + 1}/{self.max_retries})")
            
            # Final failed waybills after all retries
            if current_failed:
                logger.warning(f"\n  {len(current_failed)} waybills still failed after {self.max_retries} retry attempts")
                logger.warning(f"   Failed waybills: {', '.join(current_failed[:10])}")
                if len(current_failed) > 10:
                    logger.warning(f"   ... and {len(current_failed) - 10} more")
                
                # Mark these as failed in database
                for tn in current_failed:
                    try:
                        tracking_repo.upsert({
                            'tracking_number': tn,
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
        tracking_numbers: List[str],
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository
    ) -> Dict[str, Any]:
        """
        Main batch processing method with multi-level retry
        User sees seamless results - all retry logic happens in background
        
        Args:
            tracking_numbers: List of tracking numbers to process
            tracking_repo: Repository for tracking records
            api_usage_repo: Repository for API usage tracking
            
        Returns:
            Complete results appearing as single operation to user
        """
        start_time = datetime.now()
        batch_id = self.generate_batch_id()
        
        results = {
            "batch_id": batch_id,
            "total_requested": len(tracking_numbers),
            "successful": 0,
            "failed": 0,
            "results": [],
            "processing_time": 0,
            "api_calls_made": 0
        }
        
        try:
            # Check rate limits
            remaining = api_usage_repo.get_remaining_requests(self.daily_limit)
            
            if remaining <= 0:
                logger.warning("Daily API limit reached")
                results["failed"] = len(tracking_numbers)
                results["error"] = "Daily API limit reached"
                return results
            
            # Limit to remaining requests
            if len(tracking_numbers) > remaining:
                logger.warning(f"Limiting batch from {len(tracking_numbers)} to {remaining} (remaining quota)")
                tracking_numbers = tracking_numbers[:remaining]
                results["total_requested"] = len(tracking_numbers)
            
            # Check for existing cached records
            existing_records = tracking_repo.get_multiple(tracking_numbers)
            existing_map = {r.tracking_number: r for r in existing_records}
            
            # Separate new and cached tracking numbers
            new_tracking_numbers = []
            cached_results = []
            
            for tn in tracking_numbers:
                if tn in existing_map:
                    record = existing_map[tn]
                    # Use cached data if recent (less than 1 hour old)
                    if record.last_checked and (datetime.utcnow() - record.last_checked).seconds < 3600:
                        cached_results.append(record)
                        logger.info(f"Using cached data for {tn}")
                    else:
                        new_tracking_numbers.append(tn)
                else:
                    new_tracking_numbers.append(tn)
            
            # Process new tracking numbers with multi-retry
            if new_tracking_numbers:
                processing_result = await self._process_with_multi_retry(
                    new_tracking_numbers,
                    tracking_repo,
                    api_usage_repo,
                    batch_id
                )
                
                # Get successful results from database (includes all retries)
                successful_records = [
                    tracking_repo.get_by_tracking_number(r['tracking_number'])
                    for r in processing_result["successful_results"]
                ]
                successful_records = [r for r in successful_records if r]
                
                results["results"].extend(successful_records)
                results["successful"] = len(successful_records)
                results["failed"] = len(processing_result["failed_waybills"])
                results["api_calls_made"] = processing_result["total_api_calls"]
            
            # Add cached results
            results["results"].extend(cached_results)
            results["successful"] += len(cached_results)
            
            # Calculate processing time
            end_time = datetime.now()
            results["processing_time"] = (end_time - start_time).total_seconds()
            
            # Final summary log
            logger.info(f"\n{'='*80}")
            logger.info(f"BATCH {batch_id} COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f" Successful: {results['successful']}/{results['total_requested']}")
            logger.info(f" Failed: {results['failed']}/{results['total_requested']}")
            logger.info(f" API calls made: {results['api_calls_made']}")
            logger.info(f"  Processing time: {results['processing_time']:.2f}s")
            logger.info(f"{'='*80}\n")
            
            return results
            
        except Exception as e:
            logger.error(f" Batch processing error: {str(e)}")
            results["failed"] = len(tracking_numbers)
            results["error"] = str(e)
            return results
    
    async def process_large_batch(
        self,
        tracking_numbers: List[str],
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Process large batch - uses same multi-retry system
        
        Args:
            tracking_numbers: List of tracking numbers
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            progress_callback: Optional callback for progress updates
            
        Returns:
            Complete results with all retries processed
        """
        logger.info(f" Starting large batch processing for {len(tracking_numbers)} waybills")
        logger.info(f"Retry strategy: Up to {self.max_retries} attempts per failed waybill")
        
        # Use the main batch processor which handles everything
        result = await self.process_batch(
            tracking_numbers,
            tracking_repo,
            api_usage_repo
        )
        
        return result
    
    def calculate_estimated_time(self, count: int) -> float:
        """
        Calculate estimated processing time including retries
        
        Args:
            count: Number of tracking numbers
            
        Returns:
            Estimated time in seconds
        """
        # Calculate batches
        batches = (count + self.batch_size - 1) // self.batch_size
        
        # Base time: batches with delays + processing
        base_time = (batches - 1) * self.batch_delay
        processing_time = count * 0.5
        
        # Retry buffer (assume 10% failure rate, 2 retries average)
        retry_buffer = (count * 0.1) * 2 * (self.retry_delay + 5)
        
        total = base_time + processing_time + retry_buffer
        
        return total
