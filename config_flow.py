import logging
import time
import voluptuous as vol
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigEntry
from homeassistant.helpers import config_entry_oauth2_flow
from .const import (
    DOMAIN, 
    SCOPE, 
    DEFAULT_CLIENT_ID, 
    DEFAULT_CLIENT_SECRET, 
    DEFAULT_REGION,
    DEFAULT_REDIRECT_URI,
    AUTHORIZE_URL,
    TOKEN_URL
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session, async_get_config_entry_implementation
from .api import FusionSolarApiClient
from .oauth2_helper import FusionSolarOAuth2Implementation

class FusionSolarFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    DOMAIN = DOMAIN
    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL
    
    @property
    def logger(self):
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self):
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPE}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            # Store the configuration data
            self._user_input = user_input
            
            # Create and register the OAuth2 implementation with custom redirect URI
            implementation = FusionSolarOAuth2Implementation(
                self.hass,
                DOMAIN,
                client_id=user_input["client_id"],
                client_secret=user_input["client_secret"],
                authorize_url=AUTHORIZE_URL,
                token_url=TOKEN_URL,
                redirect_uri=user_input["redirect_uri"]
            )
            
            # Store the implementation for later use
            self.flow_impl = implementation
            
            # Register the implementation
            config_entry_oauth2_flow.async_register_implementation(
                self.hass, DOMAIN, implementation
            )
            
            # Start the OAuth2 flow
            return await self.async_step_pick_implementation(
                user_input={"implementation": DOMAIN}
            )
            
        # Show the form with default values
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("client_id", default=DEFAULT_CLIENT_ID): str,
                vol.Required("client_secret", default=DEFAULT_CLIENT_SECRET): str,
                vol.Required("region", default=DEFAULT_REGION): str,
                vol.Required("redirect_uri", default=DEFAULT_REDIRECT_URI): str
            })
        )
    
    async def async_oauth_create_entry(self, data):
        """Create config entry from OAuth2 data."""
        # Fix OAuth2 token structure if needed
        token_data = data.copy()
        if "access_token" in token_data:
            oauth_token = token_data
        elif "token" in token_data and "access_token" in token_data["token"]:
            oauth_token = token_data["token"]
        else:
            self.logger.error("Invalid token data structure: %s", list(token_data.keys()))
            return self.async_abort(reason="invalid_token")
        
        # Ensure expires_at field exists for OAuth2Session compatibility
        if "expires_at" not in oauth_token and "expires_in" in oauth_token:
            oauth_token["expires_at"] = time.time() + oauth_token["expires_in"]
        elif "expires_at" not in oauth_token:
            oauth_token["expires_at"] = time.time() + 3600  # Default 1 hour
        
        # Create single config entry for all plants
        # Plants will be discovered and registered as devices in __init__.py
        return self.async_create_entry(
            title="FusionSolar Cloud Control",
            data={
                "auth_implementation": DOMAIN,
                "token": oauth_token,
                "region": self._user_input["region"],
                "redirect_uri": self._user_input["redirect_uri"],
                "client_id": self._user_input["client_id"],
                "client_secret": self._user_input["client_secret"],
            },
        )
    
 