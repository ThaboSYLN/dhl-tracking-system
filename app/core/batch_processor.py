"""
Enhanced batch processor with intelligent retry logic
Implements 20-waybill batching with 7-second delays and automatic retry for failed requests
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
    Intelligent batch processor with retry logic for failed requests
    Processes tracking requests in batches of 20 with 7-second delays
    """
    
    def __init__(self, dhl_service: DHLAPIService):
        self.dhl_service = dhl_service
        self.batch_size = 20  # Industry standard for rate limiting
        self.batch_delay = 7  # 7 seconds between batches
        self.daily_limit = settings.DHL_DAILY_LIMIT
    
    def generate_batch_id(self) -> str:
        """Generate unique batch ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"batch_{timestamp}_{unique_id}"
    
    async def process_batch(
        self,
        tracking_numbers: List[str],
        tracking_repo: TrackingRepository,
        api_usage_repo: APIUsageRepository
    ) -> Dict[str, Any]:
        """
        Process a batch of tracking numbers with automatic retry for failures
        
        Args:
            tracking_numbers: List of tracking numbers to process
            tracking_repo: Repository for tracking records
            api_usage_repo: Repository for API usage tracking
            
        Returns:
            Dictionary with batch processing results (appears as single attempt to user)
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
            
            # Limit batch to remaining requests
            if len(tracking_numbers) > remaining:
                logger.warning(f"Batch size ({len(tracking_numbers)}) exceeds remaining requests ({remaining})")
                tracking_numbers = tracking_numbers[:remaining]
                results["total_requested"] = len(tracking_numbers)
            
            # Check for existing records to minimize API calls
            existing_records = tracking_repo.get_multiple(tracking_numbers)
            existing_map = {r.tracking_number: r for r in existing_records}
            
            # Separate new and existing tracking numbers
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
            
            # Process new tracking numbers in batches of 20 with 7-second delays
            if new_tracking_numbers:
                logger.info(f"Processing {len(new_tracking_numbers)} new tracking numbers in batches of {self.batch_size}")
                
                all_api_results = []
                failed_tracking_numbers = []
                
                # First pass: Process in batches of 20
                for i in range(0, len(new_tracking_numbers), self.batch_size):
                    batch = new_tracking_numbers[i:i + self.batch_size]
                    batch_num = (i // self.batch_size) + 1
                    total_batches = (len(new_tracking_numbers) + self.batch_size - 1) // self.batch_size
                    
                    logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} waybills)")
                    
                    # Process this batch
                    batch_results = await self.dhl_service.track_batch(batch, delay=0.2)
                    all_api_results.extend(batch_results)
                    
                    # Collect failed ones for retry
                    for result in batch_results:
                        if not result.get('is_successful'):
                            failed_tracking_numbers.append(result.get('tracking_number'))
                    
                    # Wait 7 seconds before next batch (except for last batch)
                    if i + self.batch_size < len(new_tracking_numbers):
                        logger.info(f"Waiting {self.batch_delay} seconds before next batch...")
                        await asyncio.sleep(self.batch_delay)
                
                # Second pass: Retry failed waybills (automatic retry in background)
                if failed_tracking_numbers:
                    logger.info(f"Retrying {len(failed_tracking_numbers)} failed waybills...")
                    await asyncio.sleep(self.batch_delay)  # Wait before retry
                    
                    retry_results = await self.dhl_service.track_batch(failed_tracking_numbers, delay=0.5)
                    
                    # Replace failed results with retry results
                    retry_map = {r['tracking_number']: r for r in retry_results}
                    for i, result in enumerate(all_api_results):
                        if result['tracking_number'] in retry_map:
                            all_api_results[i] = retry_map[result['tracking_number']]
                    
                    logger.info(f"Retry completed for {len(failed_tracking_numbers)} waybills")
                
                # Save all results to database
                for api_result in all_api_results:
                    try:
                        # Add batch ID
                        api_result['batch_id'] = batch_id
                        
                        # Upsert to database
                        record = tracking_repo.upsert(api_result)
                        results["results"].append(record)
                        
                        # Update counters
                        if api_result.get('is_successful'):
                            results["successful"] += 1
                            api_usage_repo.increment_usage(success=True)
                        else:
                            results["failed"] += 1
                            api_usage_repo.increment_usage(success=False)
                        
                        results["api_calls_made"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error saving tracking result: {str(e)}")
                        results["failed"] += 1
            
            # Add cached results
            results["results"].extend(cached_results)
            results["successful"] += len(cached_results)
            
            # Calculate processing time
            end_time = datetime.now()
            results["processing_time"] = (end_time - start_time).total_seconds()
            
            logger.info(
                f"Batch {batch_id} completed: "
                f"{results['successful']} successful, "
                f"{results['failed']} failed, "
                f"{results['api_calls_made']} API calls, "
                f"{results['processing_time']:.2f}s"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}")
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
        Process a large batch with progress updates
        Uses the enhanced batch processor with retry logic
        
        Args:
            tracking_numbers: List of tracking numbers
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            progress_callback: Optional callback for progress updates
            
        Returns:
            Aggregated results from processing (appears as single operation)
        """
        logger.info(f"Starting large batch processing for {len(tracking_numbers)} waybills")
        
        # Use the main batch processor which now handles everything
        result = await self.process_batch(
            tracking_numbers,
            tracking_repo,
            api_usage_repo
        )
        
        return result
    
    def calculate_estimated_time(self, count: int) -> float:
        """
        Calculate estimated processing time for a batch
        
        Args:
            count: Number of tracking numbers
            
        Returns:
            Estimated time in seconds
        """
        # Calculate number of batches
        batches = (count + self.batch_size - 1) // self.batch_size
        
        # Time = (batches * delay) + (count * 0.5 seconds per request) + retry buffer
        base_time = (batches - 1) * self.batch_delay  # Delays between batches
        processing_time = count * 0.5  # Approximate processing per waybill
        retry_buffer = batches * 2  # Buffer for potential retries
        
        return base_time + processing_time + retry_buffer

