"""
DHL API Service
Handles communication with DHL tracking API
Follows Single Responsibility and Dependency Inversion principles

CHANGES MADE:
1. track_single: Now accepts optional bin_id parameter (Line 36)
2. track_single: Includes bin_id in return dictionary (Line 65)
3. track_batch: Now accepts List[Tuple[waybill, binID]] (Line 95)
4. _parse_tracking_response: Now accepts and includes bin_id (Lines 142, 181)
"""
import httpx
import asyncio
from typing import Dict, List, Optional, Any, Tuple
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
        
        self.headers = {
            "DHL-API-Key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def track_single(self, tracking_number: str, bin_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Track a single shipment
        
        UPDATED: Now accepts bin_id parameter to maintain association
        
        Args:
            tracking_number: DHL tracking/waybill number
            bin_id: Optional binID to associate with this tracking
            
        Returns:
            Dictionary containing tracking information with bin_id
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.api_url}?trackingNumber={tracking_number}"
                
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_tracking_response(data, tracking_number, bin_id)
                elif response.status_code == 404:
                    return {
                        "tracking_number": tracking_number,
                        "bin_id": bin_id,
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
                "bin_id": bin_id,
                "is_successful": False,
                "error_message": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error tracking {tracking_number}: {str(e)}")
            return {
                "tracking_number": tracking_number,
                "bin_id": bin_id,
                "is_successful": False,
                "error_message": str(e)
            }
    
    async def track_batch(
        self, 
        tracking_data: List[Tuple[str, Optional[str]]], 
        delay: float = 10.0
    ) -> List[Dict[str, Any]]:
        """
        Track multiple shipments with rate limiting
        
        UPDATED: Now accepts List[Tuple[waybill, binID]] instead of List[str]
        
        Args:
            tracking_data: List of tuples [(waybill, binID), ...]
            delay: Delay between requests in seconds
            
        Returns:
            List of tracking results with bin_id preserved
        """
        results = []
        batch_size = settings.DHL_BATCH_SIZE
        
        for i in range(0, len(tracking_data), batch_size):
            batch = tracking_data[i:i + batch_size]
            
            # Create tasks with bin_id
            tasks = [
                self.track_single(waybill, bin_id) 
                for waybill, bin_id in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch tracking error: {result}")
                else:
                    results.append(result)
            
            if i + batch_size < len(tracking_data):
                await asyncio.sleep(delay)
        
        return results
    
    def _parse_tracking_response(
        self, 
        data: Dict[str, Any], 
        tracking_number: str,
        bin_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse DHL API response into standardized format
        
        UPDATED: Now includes bin_id in response
        
        Args:
            data: Raw API response
            tracking_number: Original tracking number
            bin_id: Associated binID
            
        Returns:
            Standardized tracking information dictionary with bin_id
        """
        try:
            shipments = data.get("shipments", [])
            
            if not shipments:
                return {
                    "tracking_number": tracking_number,
                    "bin_id": bin_id,
                    "is_successful": False,
                    "error_message": "No shipment data found"
                }
            
            shipment = shipments[0]
            status = shipment.get("status", {})
            status_code = status.get("statusCode", "unknown")
            status_description = status.get("status", "Unknown")
            
            origin = self._extract_location(shipment.get("origin", {}))
            destination = self._extract_location(shipment.get("destination", {}))
            events = shipment.get("events", [])
            
            return {
                "tracking_number": tracking_number,
                "bin_id": bin_id,  # NEW: binID included in response
                "status_code": status_code,
                "status": status_description,
                "origin": origin,
                "destination": destination,
                "tracking_details": {
                    "service": shipment.get("service"),
                    "estimated_delivery": shipment.get("estimatedTimeOfDelivery"),
                    "events": events[:5],
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
                "bin_id": bin_id,
                "is_successful": False,
                "error_message": f"Error parsing response: {str(e)}"
            }
    
    def _extract_location(self, location_data: Dict[str, Any]) -> str:
        """Extract and format location information"""
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
        """Test DHL API connectivity"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.api_url, headers=self.headers)
                return response.status_code in [200, 400, 404]
        except Exception as e:
            logger.error(f"DHL API connection test failed: {str(e)}")
            return False


# Create service instance
dhl_service = DHLAPIService()
