import logging
from datetime import time as dt_time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .api import FusionSolarApiClient
from .const import DOMAIN, PLATFORMS, AUTHORIZE_URL, TOKEN_URL, DEFAULT_NIGHT_START, DEFAULT_NIGHT_END
from .coordinator import FusionSolarCloudControlCoordinator
from .oauth2_helper import FusionSolarOAuth2Implementation
from .plant import create_plant_info, PlantInfo

# Apply OAuth2 patches for state shortening support
from .oauth2_helper import patch_oauth2_flow
patch_oauth2_flow()

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the FusionSolar Cloud Control component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up FusionSolar Cloud Control from a config entry."""
    # Get OAuth2 credentials from config entry
    client_id = entry.data.get("client_id")
    client_secret = entry.data.get("client_secret")
    redirect_uri = entry.data.get("redirect_uri")
    
    # Create the OAuth2 implementation
    implementation = FusionSolarOAuth2Implementation(
        hass,
        DOMAIN,
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=AUTHORIZE_URL,
        token_url=TOKEN_URL,
        redirect_uri=redirect_uri
    )
    
    oauth_session = OAuth2Session(hass, entry, implementation)
    api = FusionSolarApiClient(hass, entry, oauth_session)
    
    _LOGGER.debug("Fetching all plants from FusionSolar API")
    
    # Fetch all plants for this account
    try:
        plants_data = await api.get_plants()
        if not plants_data:
            _LOGGER.error("No plants found for this FusionSolar account")
            return False
        
        _LOGGER.debug("Found %d plants", len(plants_data))
        
        # Convert raw API data to strongly typed PlantInfo objects
        plants: list[PlantInfo] = []
        
        for plant_data in plants_data:
            try:
                # Create strongly typed PlantInfo from raw API data
                plant_info = await create_plant_info(plant_data)
                
                plants.append(plant_info)
                _LOGGER.debug("Created PlantInfo: %s (ID: %s)", plant_info.name, plant_info.id)
                
            except Exception as err:
                _LOGGER.error("Failed to create PlantInfo from data %s: %s", plant_data, err)
                continue
        
        # Register each plant as a separate Home Assistant device
        device_registry = dr.async_get(hass)
        
        for plant_info in plants:
            # Register plant as Home Assistant device
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, str(plant_info.id))},
                name=plant_info.name,
                manufacturer="Huawei",
                model="FusionSolar Plant",
            )
            
            _LOGGER.debug("Registered plant device: %s (ID: %s)", plant_info.name, plant_info.id)
        
    except Exception as err:
        _LOGGER.error("Failed to fetch plants: %s", err, exc_info=True)
        return False
    
    # Store the API and plants data for this config entry
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    # Get night mode settings from config entry options (with defaults from const.py)
    night_mode_enabled = entry.data.get("night_mode_enabled", True)
    night_start = entry.data.get("night_start", DEFAULT_NIGHT_START)
    night_end = entry.data.get("night_end", DEFAULT_NIGHT_END)
    
    # Parse time strings
    try:
        start_hour, start_minute = map(int, night_start.split(":"))
        night_start_time = dt_time(start_hour, start_minute)
    except (ValueError, AttributeError):
        start_hour, start_minute = map(int, DEFAULT_NIGHT_START.split(":"))
        night_start_time = dt_time(start_hour, start_minute)
    
    try:
        end_hour, end_minute = map(int, night_end.split(":"))
        night_end_time = dt_time(end_hour, end_minute)
    except (ValueError, AttributeError):
        end_hour, end_minute = map(int, DEFAULT_NIGHT_END.split(":"))
        night_end_time = dt_time(end_hour, end_minute)
    
    coordinator = FusionSolarCloudControlCoordinator(
        hass, api, plants,
        night_mode_enabled=night_mode_enabled,
        night_start=night_start_time,
        night_end=night_end_time
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "plants": plants,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
