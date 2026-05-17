import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta, datetime, time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .api import FusionSolarApiClient, FusionSolarRateLimitError, FusionSolarApiException
from .plant import create_plant_realtime_data, PlantRealTimeData
from .const import DEFAULT_NIGHT_START, DEFAULT_NIGHT_END

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlantCoordinatorData:
    """Strongly typed coordinator data for a single plant."""
    
    # Control state
    is_plant_on: bool | None = None
    power_limit_percent: float | None = None
    
    # Energy metrics (for utility meter calculations)
    day_power_kwh: float | None = None
    total_power_kwh: float | None = None
    month_power_kwh: float | None = None
    year_power_kwh: float | None = None
    
    # Status
    data_available: bool = False
    plant_status: str | None = None
    
    # Debug info (optional)
    raw_power_config: dict | None = None
    raw_realtime_data: PlantRealTimeData | None = None

# Parse night mode defaults from const.py strings
_night_start_parts = list(map(int, DEFAULT_NIGHT_START.split(":")))
_night_end_parts = list(map(int, DEFAULT_NIGHT_END.split(":")))
DEFAULT_NIGHT_START_TIME = time(_night_start_parts[0], _night_start_parts[1])
DEFAULT_NIGHT_END_TIME = time(_night_end_parts[0], _night_end_parts[1])

# Rate limit compliant intervals
MIN_POLLING_INTERVAL = 300  # 5 minutes minimum per API docs
NIGHT_POLLING_INTERVAL = 1800  # 30 minutes during night (reduced activity)


class FusionSolarCloudControlCoordinator(DataUpdateCoordinator[dict[str, PlantCoordinatorData]]):
    """Manages fetching data from the FusionSolar API for all plants."""

    def __init__(
        self, hass: HomeAssistant, api_client: FusionSolarApiClient, plants: list,
        night_mode_enabled: bool = True,
        night_start: time = DEFAULT_NIGHT_START_TIME,
        night_end: time = DEFAULT_NIGHT_END_TIME
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="FusionSolar active power configuration",
            update_interval=timedelta(seconds=MIN_POLLING_INTERVAL),
        )
        self.api_client = api_client
        self.plants = plants
        self.night_mode_enabled = night_mode_enabled
        self.night_start = night_start
        self.night_end = night_end
        self._last_successful_data = {}

    def _is_night_mode(self) -> bool:
        """Check if we should be in night mode (reduced polling)."""
        if not self.night_mode_enabled:
            return False
        
        now = dt_util.now().time()
        
        # Handle case where night spans midnight
        if self.night_start > self.night_end:
            return now >= self.night_start or now < self.night_end
        else:
            return self.night_start <= now < self.night_end

    def get_next_update_interval(self) -> timedelta:
        """Get the appropriate update interval based on time of day."""
        if self._is_night_mode():
            return timedelta(seconds=NIGHT_POLLING_INTERVAL)
        return timedelta(seconds=MIN_POLLING_INTERVAL)

    async def _async_update_data(self) -> dict:
        """Fetch power configuration and current power for all plants."""
        # Adjust polling interval dynamically
        new_interval = self.get_next_update_interval()
        if self.update_interval != new_interval:
            self.update_interval = new_interval
            _LOGGER.debug("Adjusted polling interval to %s seconds", new_interval.total_seconds())
        
        return await self._fetch_data_with_retry()
    
    async def _fetch_data_with_retry(self, retry_count=0, max_retries=3) -> dict:
        """Fetch data with exponential backoff retry for rate limiting."""
        result = await self._fetch_api_data_with_retry(retry_count, max_retries)
        
        # Save successful data for fallback during night mode or rate limits
        if result:
            self._last_successful_data = result.copy()
        
        return result
    
    async def _fetch_api_data_with_retry(self, retry_count=0, max_retries=3) -> dict:
        """Fetch API data with retry logic for rate limiting."""
        try:
            plant_codes = [plant.id for plant in self.plants]
            
            # Fetch both power configuration and current power data
            all_plant_data = {}
            
            for i, plant_code in enumerate(plant_codes):
                # Add throttling between requests to avoid rate limiting
                if i > 0:  # Don't wait before the first request
                    await asyncio.sleep(3)  # Wait 3 seconds between plants
                
                plant_data = {}
                
                # 1. Fetch power configuration (control settings)
                try:
                    settings = await self.api_client.async_get_plant_power_config(plant_code)
                    if settings:
                        plant_data["power_config"] = settings
                except FusionSolarRateLimitError:
                    raise  # Re-raise to trigger retry
                except Exception as err:
                    _LOGGER.warning("Failed to fetch power config for plant %s: %s", plant_code, err)
                
                # Small delay between different API calls
                await asyncio.sleep(1)
                
                # 2. Fetch plant real-time data (day_power for utility meter calculations)
                # Using getStationRealKpi - provides cumulative energy (day_power) 
                # which is perfect for 15-minute utility meter calculations
                try:
                    realtime_data = await self.api_client.async_get_plant_realtime_data(plant_code)
                    if realtime_data:
                        plant_data["realtime_data"] = realtime_data
                except FusionSolarRateLimitError:
                    raise  # Re-raise to trigger retry
                except Exception as err:
                    _LOGGER.debug("Failed to fetch plant realtime data for plant %s: %s", plant_code, err)
                
                if plant_data:  # Only add if we got any valid data
                    all_plant_data[plant_code] = plant_data
                    
            return self._process_plant_data(all_plant_data)

        except FusionSolarRateLimitError as err:
            # Handle rate limiting with retry logic
            if retry_count < max_retries:
                wait_time = (2 ** retry_count) * 60  # 60s, 120s, 240s
                _LOGGER.warning(
                    "FusionSolar API rate limit exceeded (code %s). Retrying in %d seconds (attempt %d/%d)", 
                    err.error_code, wait_time, retry_count + 1, max_retries + 1
                )
                await asyncio.sleep(wait_time)
                return await self._fetch_data_with_retry(retry_count + 1, max_retries)
            else:
                # Max retries reached for rate limiting - return last known data
                _LOGGER.error(
                    "FusionSolar API rate limit exceeded (code %s). Max retries (%d) reached. "
                    "Using last known data.", 
                    err.error_code, max_retries + 1
                )
                # Return last successful data or empty dict
                return self._last_successful_data if self._last_successful_data else {}
        except FusionSolarApiException as err:
            # Handle other FusionSolar API errors
            raise UpdateFailed(f"FusionSolar API error (code {err.error_code}): {err}") from err
        except Exception as err:
            # Handle unexpected errors
            raise UpdateFailed(f"Unexpected error communicating with API: {err}") from err
    
    def _process_plant_data(self, all_plant_data: dict) -> dict[str, PlantCoordinatorData]:
        """Process raw API data into coordinator format.
        
        This method handles data processing separately from API calls,
        with its own exception handling that doesn't trigger retries.
        """
        try:
            plant_codes = [plant.id for plant in self.plants]
            processed_data = {}
            
            for plant_code in plant_codes:
                # Get raw API data for this plant
                plant_raw_data = all_plant_data.get(plant_code, {})
                
                # Check if we have valid API data
                has_valid_data = bool(plant_raw_data)
                
                if not has_valid_data:
                    # No API data available - use last known or mark unavailable
                    fallback_data = self._last_successful_data.get(plant_code)
                    if fallback_data:
                        processed_data[plant_code] = PlantCoordinatorData(
                            is_plant_on=fallback_data.is_plant_on,
                            power_limit_percent=fallback_data.power_limit_percent,
                            day_power_kwh=fallback_data.day_power_kwh,
                            total_power_kwh=fallback_data.total_power_kwh,
                            data_available=False,
                        )
                    else:
                        processed_data[plant_code] = PlantCoordinatorData(data_available=False)
                    continue
                
                # Parse power configuration
                power_config = plant_raw_data.get("power_config", {})
                control_mode_str = power_config.get("controlMode", "noLimit")
                
                # Calculate derived values from power config
                plant = self._get_plant_by_id(plant_code)
                
                if control_mode_str == "noLimit":
                    is_plant_on = True
                    power_limit_percent = 100.0
                elif control_mode_str in ["limitedPowerGridKW", "limitedPowerGridPercent", "zeroExportLimitation"]:
                    power_limit_percent = 0.0
                    if control_mode_str == "limitedPowerGridKW":
                        limited_param = power_config.get("limitedPowerGridValueParam", {})
                        if limited_param and "maxGridFeedInPowerValue" in limited_param and plant and plant.capacity > 0:
                            power_limit_kw = float(limited_param["maxGridFeedInPowerValue"])
                            power_limit_percent = (power_limit_kw / plant.capacity) * 100
                    elif control_mode_str == "limitedPowerGridPercent":
                        limited_param = power_config.get("limitedPowerGridPercentParam", {})
                        if limited_param and "maxGridFeedInPowerPercent" in limited_param:
                            power_limit_percent = float(limited_param.get("maxGridFeedInPowerPercent", 0))
                    
                    is_plant_on = power_limit_percent > 0.0
                else:
                    is_plant_on = None
                    power_limit_percent = None
                
                # Convert raw realtime data to typed model (business logic layer)
                raw_realtime = plant_raw_data.get("realtime_data", {})
                realtime_data = create_plant_realtime_data(raw_realtime) if raw_realtime else None
                
                processed_data[plant_code] = PlantCoordinatorData(
                    # Entity data - power config
                    is_plant_on=is_plant_on,
                    power_limit_percent=power_limit_percent,
                    
                    # Energy data - for utility meter calculations
                    day_power_kwh=realtime_data.day_power_kwh if realtime_data else None,
                    total_power_kwh=realtime_data.total_power_kwh if realtime_data else None,
                    month_power_kwh=realtime_data.month_power_kwh if realtime_data else None,
                    year_power_kwh=realtime_data.year_power_kwh if realtime_data else None,
                    
                    # Status flags
                    data_available=True,
                    plant_status=realtime_data.plant_status if realtime_data else None,
                    
                    # Debug info
                    raw_power_config=power_config,
                    raw_realtime_data=realtime_data,
                )
                
                _LOGGER.debug(
                    "Plant %s: day_power=%s kWh, limit=%s%%, mode=%s, on=%s",
                    plant_code,
                    realtime_data.day_power_kwh if realtime_data else None,
                    power_limit_percent,
                    control_mode_str,
                    is_plant_on
                )

            return processed_data
            
        except Exception as err:
            # Data processing errors should not trigger API retries
            _LOGGER.error("Error processing plant data: %s", err)
            raise UpdateFailed(f"Error processing plant data: {err}") from err
            
    def _get_plant_by_id(self, plant_id: str):
        """Helper to get a plant by its ID."""
        return next((p for p in self.plants if p.id == plant_id), None)
    
    def _is_control_task_successful(self, api_response: dict) -> bool:
        """Check if the control API response indicates successful task creation.
        
        The FusionSolar control API is asynchronous and returns task status.
        We consider the operation successful if the task was created successfully,
        even if it hasn't completed yet.
        
        Args:
            api_response: The response from the control API
            
        Returns:
            bool: True if task was successfully created, False otherwise
        """
        if not api_response:
            return False
            
        # Check for successful API call (failCode == 0 or None)
        fail_code = api_response.get("failCode")
        if fail_code is not None and fail_code != 0:
            # Special case: error code 2 means "already in desired state" which is success
            if fail_code == 2:
                return True
            return False
            
        # Check task status in the data.result array
        data = api_response.get("data", {})
        if isinstance(data, dict) and "result" in data:
            results = data["result"]
            if isinstance(results, list) and len(results) > 0:
                # Check the first result (should be our plant)
                first_result = results[0]
                if isinstance(first_result, dict):
                    status = first_result.get("status", "").upper()
                    # Task is successful if it's RUNNING or SUCCESS
                    return status in ["RUNNING", "SUCCESS"]
        
        # If we can't determine status, check the top-level 'success' property
        success = api_response.get("success")
        if success is not None:
            return bool(success)
            
        # Final fallback: assume success if no error code
        return fail_code is None or fail_code == 0
    
    async def async_turn_on_plant(self, plant_id: str) -> bool:
        """Turn on a plant via coordinator with proper error handling."""
        try:
            result = await self.api_client.async_turn_on_plant(plant_id)
            # Check if the asynchronous task was successfully created
            if result and self._is_control_task_successful(result):
                _LOGGER.debug("Plant %s turn-on task created successfully", plant_id)
                return True
            else:
                _LOGGER.warning("Plant %s turn-on task creation failed", plant_id)
                return False
        except Exception as err:
            _LOGGER.error("Failed to turn on plant %s via coordinator: %s", plant_id, err)
            return False
    
    async def async_turn_off_plant(self, plant_id: str) -> bool:
        """Turn off a plant via coordinator with proper error handling."""
        try:
            result = await self.api_client.async_turn_off_plant(plant_id)
            # Check if the asynchronous task was successfully created
            if result and self._is_control_task_successful(result):
                _LOGGER.debug("Plant %s turn-off task created successfully", plant_id)
                return True
            else:
                _LOGGER.warning("Plant %s turn-off task creation failed", plant_id)
                return False
        except Exception as err:
            _LOGGER.error("Failed to turn off plant %s via coordinator: %s", plant_id, err)
            return False
    
    async def async_set_plant_power_limit(self, plant_id: str, power_kw: float) -> bool:
        """Set plant power limit via coordinator with proper error handling."""
        try:
            result = await self.api_client.async_set_plant_power_limit(plant_id, power_kw)
            # Check if the asynchronous task was successfully created
            if result and self._is_control_task_successful(result):
                _LOGGER.debug("Plant %s power limit task created successfully", plant_id)
                return True
            else:
                _LOGGER.warning("Plant %s power limit task creation failed", plant_id)
                return False
        except Exception as err:
            _LOGGER.error("Failed to set power limit for plant %s via coordinator: %s", plant_id, err)
            return False
