"""Here I'm Handling All DHL API Interactions :) """

import asyncio
from typing import List,Dict,Optional
from datetime import datetime
import httpx
from app.config import Settings
from app.models.schemas import TrackingInfo


class DHLAPIServices:
    """interface segration"""

    def __init__(self,settings:Settings):
        self.settings = settings
        self.base_url = settings.DHL_API_BASE_URL
        self.headers = settings.dhl_uath_header
        self.client:Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """This is for context manager entry"""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers=self.headers
        )
        return self
    async def __aexit__(self,exc_type,exc_val,exc_tb):
         """This is for context manager exit"""
         if self.client:
             await self.client.aclose()

    async def track_single_shipment(self,waybill_number:str) -> TrackingInfo:
        """Must Comment when done"""
        try:
            if not self.client:
                raise RuntimeError("Service not started/Init.check context manager")
            url = f"{self.base_url}?trackingNumber  ={waybill_number}"
            responce = await self.client.get(url)
            if responce.status_code==200:
                data = responce.json()
                return self._parse_tracking_responce(waybill_number,data)
            elif responce.status_code==404:
                return TrackingInfo(
                    waybill_number = waybill_number,
                    error_message = "Tracking number not found"
                )
            else:
                return TrackingInfo(
                    waybill_number = waybill_number,
                    error_message = f"API ERROR:{responce.status_code}" 
                )
        except httpx.TimeoutException:
            return TrackingInfo(
                waybill_number = waybill_number,
                error_message = "Request TimeOut :( )"
            )
        except Exception as e:
            return TrackingInfo(
                waybill_number  =waybill_number,
                error_message  =f"Error:{str(e)}"

            )
        
    async def track_multiple_shipments(
            self,
            waybill_numbers:List[str],
            batch_size: int  = 25,
            delay_between_baches: int  = 2 
            ) -> List[TrackingInfo] :
        result = []

        for i in range(0,len(waybill_numbers),batch_size):
            batch = waybill_numbers[i:i+batch_size] 

            batch_tasks = [
                self.track_single_shipment(waybill)
                for waybill in batch
            ]
            batch_results = await asyncio.gather(*batch_tasks,return_exceptions=True)

            #handle results
            for result in batch_results:
                if isinstance(result,Exception):
                    result.append(TrackingInfo(
                        waybill_number = "UNKNOWN",
                        error_message = str(result)
                    ))
                else:
                    result.append(result)   
            #manage ops Delay 
            if i + batch_size<len(waybill_numbers):
                await asyncio.sleep(delay_between_baches)    
        return result
    

    def _parse_tracking_response(self,waybill_number,data:Dict)->TrackingInfo:
        try:
            shipments = data.get("shipments",[])

            if not shipments:
                return TrackingInfo(
                    waybill_number = waybill_number,
                    error_message = "No tracking information available"
                )  
            shipment = shipments[0]

            #getting status  now  
            status_info = shipment.get("Status",{})   
            status_code =  status_info.get("StatusCoide","")
            status_desc = status_info.get("Status","")

            #getting origin and distination

            origin_address = shipment.get("origin",{}).get("address",{})
            dest_address  = shipment.get("destination",{}).get("Address",{})

            origin = origin_address.get("AddressLocality") or origin_address.get("CountryCode","")
            destination = dest_address.get("AddressLocality") or dest_address.get("CountryCode","")


            #Timestamp
            timestamp_str = status_info.get("timestamp")
            last_updated = None
            if timestamp_str:
                try:
                    last_updated = datetime.fromisoformat(timestamp_str.replace("Z","+00:00"))
                except:
                    pass

            return TrackingInfo(
                waybill_number = waybill_number,
                status_code = status_code,
                status = status_desc,
                origin = origin,
                destination = destination,
                last_updated = last_updated or datetime.utcnow()
            )
        except Exception as e:
            return TrackingInfo(waybill_number = waybill_number,
                                error_message = f"Parse Error: {str(e)}"
                                
                                )        
           




    
           