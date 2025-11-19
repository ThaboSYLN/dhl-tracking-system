"""
Batch processor for handling multiple tracking requests efficiently
Implements intelligent batching and rate limiting
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
    Intelligent batch processor for tracking requests
    Manages DHL API rate limits and optimizes request patterns
    """
    
    def __init__(self, dhl_service: DHLAPIService):
        self.dhl_service = dhl_service
        self.batch_size = settings.DHL_BATCH_SIZE
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
        Process a batch of tracking numbers intelligently
        
        Args:
            tracking_numbers: List of tracking numbers to process
            tracking_repo: Repository for tracking records
            api_usage_repo: Repository for API usage tracking
            
        Returns:
            Dictionary with batch processing results
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
            
            # Process new tracking numbers via API
            if new_tracking_numbers:
                logger.info(f"Processing {len(new_tracking_numbers)} new tracking numbers")
                api_results = await self.dhl_service.track_batch(new_tracking_numbers)
                
                # Update database with new results
                for api_result in api_results:
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
        
        Args:
            tracking_numbers: List of tracking numbers
            tracking_repo: Tracking repository
            api_usage_repo: API usage repository
            progress_callback: Optional callback for progress updates
            
        Returns:
            Aggregated results from all sub-batches
        """
        all_results = {
            "total_requested": len(tracking_numbers),
            "successful": 0,
            "failed": 0,
            "results": [],
            "batch_ids": [],
            "processing_time": 0,
            "api_calls_made": 0
        }
        
        start_time = datetime.now()
        
        # Split into manageable batches
        for i in range(0, len(tracking_numbers), self.batch_size):
            batch = tracking_numbers[i:i + self.batch_size]
            
            # Process batch
            batch_result = await self.process_batch(batch, tracking_repo, api_usage_repo)
            
            # Aggregate results
            all_results["successful"] += batch_result["successful"]
            all_results["failed"] += batch_result["failed"]
            all_results["results"].extend(batch_result["results"])
            all_results["batch_ids"].append(batch_result["batch_id"])
            all_results["api_calls_made"] += batch_result["api_calls_made"]
            
            # Progress callback
            if progress_callback:
                progress = (i + len(batch)) / len(tracking_numbers) * 100
                await progress_callback(progress, batch_result)
            
            # Delay between batches to respect rate limits
            if i + self.batch_size < len(tracking_numbers):
                await asyncio.sleep(1)  # 1 second delay between batches
        
        end_time = datetime.now()
        all_results["processing_time"] = (end_time - start_time).total_seconds()
        
        return all_results
    
    def calculate_estimated_time(self, count: int) -> float:
        """
        Calculate estimated processing time for a batch
        
        Args:
            count: Number of tracking numbers
            
        Returns:
            Estimated time in seconds
        """
        # Estimate: ~0.5 seconds per request + batch overhead
        batches = (count + self.batch_size - 1) // self.batch_size
        return (count * 0.5) + (batches * 1)  # 1 second between batches

