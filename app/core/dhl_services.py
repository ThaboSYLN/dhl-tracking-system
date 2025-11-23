"""
DHL API Service
Handles communication with DHL tracking API
Follows Single Responsibility and Dependency Inversion principles
"""
import httpx
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from app.utils.config import settings

logger = logging.getLogger(__name__)


class DHLAPIException(Exception):
    """Custom exception for DHL API errors"""
    pass


class DHLAPIService:
    """
    Service for interacting with DHL Tracking API
    Handles rate limiting and error handling
    """
    
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key or settings.DHL_API_KEY
        self.api_url = api_url or settings.DHL_API_URL
        self.timeout = 30.0
        
        # HTTP headers for DHL API
        self.headers = {
            "DHL-API-Key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def track_single(self, tracking_number: str) -> Dict[str, Any]:
        """
        Track a single shipment
        
        Args:
            tracking_number: DHL tracking/waybill number
            
        Returns:
            Dictionary containing tracking information
            
        Raises:
            DHLAPIException: If API request fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # DHL API endpoint for single tracking
                url = f"{self.api_url}?trackingNumber={tracking_number}"
                
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_tracking_response(data, tracking_number)
                elif response.status_code == 404:
                    return {
                        "tracking_number": tracking_number,
                        "is_successful": False,
                        "error_message": "Tracking number not found"
                    }
                elif response.status_code == 401:
                    raise DHLAPIException("Invalid API key")
                elif response.status_code == 429:
                    raise DHLAPIException("Rate limit exceeded")
                else:
                    raise DHLAPIException(f"API request failed: {response.status_code}")
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout tracking {tracking_number}")
            return {
                "tracking_number": tracking_number,
                "is_successful": False,
                "error_message": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error tracking {tracking_number}: {str(e)}")
            return {
                "tracking_number": tracking_number,
                "is_successful": False,
                "error_message": str(e)
            }
    
    async def track_batch(self, tracking_numbers: List[str], delay: float = 10.0) -> List[Dict[str, Any]]:   #changed delay  from 0.1 sec to  10 second --hope it will work
        """
        Track multiple shipments with rate limiting
        
        Args:
            tracking_numbers: List of tracking numbers
            delay: Delay between requests in seconds (for rate limiting)
            
        Returns:
            List of tracking results
        """
        results = []
        
        # Process in batches to respect rate limits
        batch_size = settings.DHL_BATCH_SIZE
        
        for i in range(0, len(tracking_numbers), batch_size):
            batch = tracking_numbers[i:i + batch_size]
            
            # Create tasks for concurrent requests
            tasks = [self.track_single(tn) for tn in batch]
            
            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch tracking error: {result}")
                else:
                    results.append(result)
            
            # Delay between batches to respect rate limits
            if i + batch_size < len(tracking_numbers):
                await asyncio.sleep(delay)
        
        return results
    
    def _parse_tracking_response(self, data: Dict[str, Any], tracking_number: str) -> Dict[str, Any]:
        """
        Parse DHL API response into standardized format
        
        Args:
            data: Raw API response
            tracking_number: Original tracking number
            
        Returns:
            Standardized tracking information dictionary
        """
        try:
            # DHL API response structure (adjust based on actual API)
            shipments = data.get("shipments", [])
            
            if not shipments:
                return {
                    "tracking_number": tracking_number,
                    "is_successful": False,
                    "error_message": "No shipment data found"
                }
            
            # Get first shipment (most relevant)
            shipment = shipments[0]
            
            # Extract status information
            status = shipment.get("status", {})
            status_code = status.get("statusCode", "unknown")
            status_description = status.get("status", "Unknown")
            
            # Extract location information
            origin = self._extract_location(shipment.get("origin", {}))
            destination = self._extract_location(shipment.get("destination", {}))
            
            # Extract events/timeline
            events = shipment.get("events", [])
            
            return {
                "tracking_number": tracking_number,
                "status_code": status_code,
                "status": status_description,
                "origin": origin,
                "destination": destination,
                "tracking_details": {
                    "service": shipment.get("service"),
                    "estimated_delivery": shipment.get("estimatedTimeOfDelivery"),
                    "events": events[:5],  # Store last 5 events
                    "pieces": shipment.get("details", {}).get("pieceIds", [])
                },
                "is_successful": True,
                "error_message": None,
                "last_checked": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error parsing tracking response: {str(e)}")
            return {
                "tracking_number": tracking_number,
                "is_successful": False,
                "error_message": f"Error parsing response: {str(e)}"
            }
    
    def _extract_location(self, location_data: Dict[str, Any]) -> str:
        """
        Extract and format location information
        
        Args:
            location_data: Location data from API
            
        Returns:
            Formatted location string
        """
        try:
            address = location_data.get("address", {})
            city = address.get("addressLocality", "")
            country = address.get("countryCode", "")
            
            if city and country:
                return f"{city}, {country}"
            elif city:
                return city
            elif country:
                return country
            else:
                return "Unknown"
        except Exception:
            return "Unknown"
    
    async def test_connection(self) -> bool:
        """
        Test DHL API connectivity
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.api_url, headers=self.headers)
                return response.status_code in [200, 400, 404]  # 400/404 means API is reachable
        except Exception as e:
            logger.error(f"DHL API connection test failed: {str(e)}")
            return False


# Create service instance
dhl_service = DHLAPIService()

