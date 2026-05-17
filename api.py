import logging
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
_LOGGER = logging.getLogger(__name__)


class FusionSolarApiException(Exception):
    """Base exception for FusionSolar API errors."""
    def __init__(self, message: str, error_code: int = None):
        super().__init__(message)
        self.error_code = error_code


class FusionSolarAuthenticationError(FusionSolarApiException):
    """Authentication failed with FusionSolar API."""
    pass


class FusionSolarRateLimitError(FusionSolarApiException):
    """Rate limit exceeded for FusionSolar API."""
    pass

class FusionSolarApiClient:
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, oauth_session: OAuth2Session):
        self.hass = hass
        self.config_entry = config_entry
        self.oauth_session = oauth_session
        self.region = config_entry.data.get("region", "eu5")
        
        _LOGGER.info("FusionSolarApiClient initialized with region: %s", self.region)

    async def get_plants(self):
        """Get all plants/stations from FusionSolar API."""
        url = f"https://{self.region}.fusionsolar.huawei.com/thirdData/stations"
        payload = {
            "pageNo": 1,
            "pageSize": 100  # Maximum records per page
        }
        
        _LOGGER.info("Getting plants from FusionSolar API")
        _LOGGER.debug("Request URL: %s", url)
        _LOGGER.debug("Request payload: %s", payload)
        
        # Use OAuth2Session for authenticated request with automatic token management
        resp = await self.oauth_session.async_request(
            "POST", url, 
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if resp.status != 200:
            error_text = await resp.text()
            _LOGGER.error("Plants API error (status %d): %s", resp.status, error_text)
            resp.raise_for_status()
        
        res = await resp.json()
        _LOGGER.debug("Plants API raw response: %s", res)
        
        # Check if FusionSolar API returned an error in the response
        # FusionSolar uses failCode: 0 for success, other values for errors
        fail_code = res.get("failCode")
        if fail_code is not None and fail_code != 0:
            error_msg = res.get("message", "Unknown error")
            _LOGGER.error("FusionSolar API error - Code: %s, Message: %s", fail_code, error_msg)
            
            if fail_code == 305 or "RELOGIN" in str(error_msg):
                raise FusionSolarAuthenticationError(f"Authentication failed: {error_msg}", fail_code)
            elif fail_code == 407:
                # Rate limiting - let coordinator handle retry logic
                raise FusionSolarRateLimitError(f"API rate limit exceeded: {error_msg}", fail_code)
            else:
                raise FusionSolarApiException(f"API error: {error_msg}", fail_code)
        
        # Success! Extract plants data from FusionSolar format
        data = res.get("data", {})
        if isinstance(data, dict):
            # Handle paginated response format
            plants = data.get("list", []) or data.get("stations", []) or data.get("data", [])
        else:
            # Handle direct array format
            plants = data if isinstance(data, list) else []
        
        _LOGGER.debug("Found %d plants: %s", len(plants), [plant["plantName"] for plant in plants])
        return plants

    async def control_plant(self, plant_id, control_mode, power=None):
        """Control plant power using FusionSolar active power control API.
        
        Args:
            plant_id: Plant/station code
            control_mode: 0 = unlimited, 6 = limited feed-in (kW)
            power: Maximum grid feed-in power in kW (required when control_mode=6)
        """
        url = f"https://{self.region}.fusionsolar.huawei.com/rest/openapi/pvms/nbi/v2/control/active-power-control/async-task"
        
        # Build the control task payload according to SmartPVMS v2 API spec
        task = {
            "plantCode": plant_id,  # Plant DN as required by v2 API
            "controlMode": str(control_mode)  # Control mode as string: "0" = unlimited, "6" = limited feed-in
        }
        
        # Add power control parameters for limited mode
        if control_mode == 6 and power is not None:
            task["controlInfo"] = {
                "maxGridFeedInPower": power,
                "limitationMode": "0"  # Total power mode (string)
            }
        
        payload = {"tasks": [task]}
        
        _LOGGER.info("Controlling plant %s: mode=%s, power=%s", plant_id, control_mode, power)
        _LOGGER.debug("Request URL: %s", url)
        _LOGGER.debug("Request payload: %s", payload)
        
        # Use OAuth2Session for authenticated request
        resp = await self.oauth_session.async_request(
            "POST", url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if resp.status != 200:
            error_text = await resp.text()
            _LOGGER.error("Plant control API error (status %d): %s", resp.status, error_text)
            resp.raise_for_status()
        
        result = await resp.json()
        _LOGGER.debug("Plant control API response: %s", result)
        
        # Check if FusionSolar API returned an error
        fail_code = result.get("failCode")
        if fail_code is not None and fail_code != 0:
            error_msg = result.get("message", "Unknown error")
            
            # Handle error code 2: "The configured value is the same as the current value"
            # This is not actually an error - it means the plant is already in the desired state
            if fail_code == 2:
                _LOGGER.debug("Plant %s already in desired state: %s", plant_id, error_msg)
                return result
            
            # Extract detailed error information from data.result if available
            detailed_errors = []
            data = result.get("data", {})
            if isinstance(data, dict) and "result" in data:
                for plant_result in data["result"]:
                    if isinstance(plant_result, dict):
                        plant_code = plant_result.get("plantCode", "unknown")
                        status = plant_result.get("status", "unknown")
                        plant_msg = plant_result.get("message", "no details")
                        detailed_errors.append(f"Plant {plant_code}: {status} - {plant_msg}")
            
            if detailed_errors:
                detailed_msg = "; ".join(detailed_errors)
                _LOGGER.error("FusionSolar plant control error - Code: %s, Message: %s, Details: %s", 
                             fail_code, error_msg, detailed_msg)
                raise FusionSolarApiException(f"Plant control failed: {error_msg}. Details: {detailed_msg}", fail_code)
            else:
                _LOGGER.error("FusionSolar plant control error - Code: %s, Message: %s", fail_code, error_msg)
                raise FusionSolarApiException(f"Plant control failed: {error_msg}", fail_code)
        
        return result

    async def async_turn_on_plant(self, plant_id: str):
        """Turn on the plant (unlimited power)."""
        return await self.control_plant(plant_id, control_mode=0)

    async def async_turn_off_plant(self, plant_id: str):
        """Turn off the plant (set power to 0)."""
        return await self.control_plant(plant_id, control_mode=6, power=0)

    async def async_set_plant_power_limit(self, plant_id: str, power_kw: float):
        """Set the plant's power limit in kW."""
        return await self.control_plant(plant_id, control_mode=6, power=power_kw)



    async def async_get_plant_power_config(self, plant_code: str) -> dict:
        """Get active power configuration for a single plant.
        
        This queries the current configured power limits/settings for the plant,
        which is essential for keeping Home Assistant in sync with external changes.
        
        Uses the official SmartPVMS API endpoint:
        /rest/openapi/pvms/nbi/v1/configuration/active-power-control-mode
        
        Args:
            plant_code: The plant code to query configuration for
        
        Returns:
            dict: Power setting info for the plant, or empty dict if failed
        """
        url = f"https://{self.region}.fusionsolar.huawei.com/rest/openapi/pvms/nbi/v1/configuration/active-power-control-mode"
        
        payload = {
            "plantCode": plant_code
        }
        
        _LOGGER.debug("Getting active power configuration for plant: %s", plant_code)
        
        try:
            resp = await self.oauth_session.async_request(
                "POST", url, json=payload, headers={"Content-Type": "application/json"}
            )

            if resp.status != 200:
                error_text = await resp.text()
                _LOGGER.error(
                    "Active power configuration API error for plant %s (status %d): %s", 
                    plant_code, resp.status, error_text
                )
                return {}

            res = await resp.json()
            _LOGGER.debug("Active power configuration API response for plant %s: %s", plant_code, res)

            fail_code = res.get("failCode")
            if fail_code is not None and fail_code != 0:
                error_msg = res.get("message", "Unknown error")
                _LOGGER.error(
                    "FusionSolar active power configuration error for plant %s - Code: %s, Message: %s",
                    plant_code, fail_code, error_msg
                )
                
                if fail_code == 305 or "RELOGIN" in str(error_msg):
                    raise FusionSolarAuthenticationError(f"Authentication failed: {error_msg}", fail_code)
                elif fail_code == 407:
                    # Rate limiting - let coordinator handle retry logic
                    raise FusionSolarRateLimitError(f"API rate limit exceeded: {error_msg}", fail_code)
                else:
                    raise FusionSolarApiException(f"API error: {error_msg}", fail_code)

            # Return raw API data - let coordinator handle business logic
            data = res.get("data", {})
            
            if data:
                return data
            else:
                _LOGGER.warning("No data returned for plant %s power configuration", plant_code)
                return {}
                
        except Exception as e:
            _LOGGER.error("Failed to get power configuration for plant %s: %s", plant_code, e)
            return {}

    async def async_get_plant_realtime_data(self, plant_code: str) -> dict:
        """Get real-time plant data including day_power (cumulative energy).
        
        This queries the getStationRealKpi endpoint to fetch energy metrics
        like day_power, which is perfect for utility meter calculations.
        
        Uses the official SmartPVMS API endpoint:
        /thirdData/getStationRealKpi
        
        Args:
            plant_code: The plant code to query data for
        
        Returns:
            dict: Raw API response data for plant real-time metrics, empty dict if failed
        """
        url = f"https://{self.region}.fusionsolar.huawei.com/thirdData/getStationRealKpi"
        
        payload = {
            "stationCodes": plant_code
        }
        
        _LOGGER.debug("Getting real-time plant data for plant %s", plant_code)
        
        try:
            resp = await self.oauth_session.async_request(
                "POST", url, json=payload, headers={"Content-Type": "application/json"}
            )

            if resp.status != 200:
                error_text = await resp.text()
                _LOGGER.error(
                    "Plant real-time data API error for plant %s (status %d): %s", 
                    plant_code, resp.status, error_text
                )
                return None

            res = await resp.json()
            _LOGGER.debug("Plant real-time data API response for plant %s: %s", plant_code, res)

            fail_code = res.get("failCode")
            if fail_code is not None and fail_code != 0:
                error_msg = res.get("message", "Unknown error")
                
                if fail_code == 305 or "RELOGIN" in str(error_msg):
                    raise FusionSolarAuthenticationError(f"Authentication failed: {error_msg}", fail_code)
                elif fail_code == 407:
                    raise FusionSolarRateLimitError(f"API rate limit exceeded: {error_msg}", fail_code)
                else:
                    _LOGGER.warning("Plant data API error for plant %s: %s", plant_code, error_msg)
                    return {}

            data = res.get("data", [])
            if data and isinstance(data, list):
                return data[0] if data else {}
            elif data and isinstance(data, dict):
                return data
            
            _LOGGER.debug("No real-time data found for plant %s", plant_code)
            return {}

        except FusionSolarRateLimitError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to get plant real-time data for plant %s: %s", plant_code, e)
            return None


