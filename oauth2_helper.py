"""Patched OAuth2 Flow Helper for FusionSolar Cloud Control.

This module patches Home Assistant's config_entry_oauth2_flow to support
state parameter shortening for OAuth2 providers with URL length limitations.
"""

import logging
import secrets
import string
import jwt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)

# Import everything from the original module
from homeassistant.helpers.config_entry_oauth2_flow import *

# Store references to original functions
_original_encode_jwt = config_entry_oauth2_flow._encode_jwt
_original_decode_jwt = config_entry_oauth2_flow._decode_jwt


@callback
def _patched_encode_jwt(hass: HomeAssistant, data: dict) -> str:
    """Patched JWT encode data with state shortening support for FusionSolar.
    
    This function implements state parameter shortening for OAuth2 providers
    that have URL length limitations like FusionSolar.
    """
    _LOGGER.info("_patched_encode_jwt called with data: %s", data)
    
    # Check if this is a state parameter that needs shortening
    if "flow_id" in data and "redirect_uri" in data:
        # Create the full JWT token first using original function
        full_jwt = _original_encode_jwt(hass, data)
        _LOGGER.info("Original JWT length: %d chars", len(full_jwt))
        
        # Always shorten for FusionSolar to test the functionality
        # (You can adjust this threshold later)
        if len(full_jwt) > 20:  # Lowered threshold for testing
            # Get the oauth2_middleware if available for state shortening
            if "oauth2_middleware" in hass.data:
                middleware = hass.data["oauth2_middleware"]
                # Generate a short state and store the mapping
                short_state = middleware._generate_short_state(8)
                middleware._state_mappings[short_state] = full_jwt
                _LOGGER.info(
                    "Shortened JWT state for FusionSolar: %d -> %d chars (short_state: %s)", 
                    len(full_jwt), len(short_state), short_state
                )
                return short_state
            else:
                _LOGGER.warning("oauth2_middleware not available in hass.data, using fallback shortening")
                # Fallback: create a simple mapping without middleware
                if not hasattr(hass, '_fusionsolar_state_mappings'):
                    hass._fusionsolar_state_mappings = {}
                
                # Generate a simple short state
                import secrets
                import string
                short_state = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
                hass._fusionsolar_state_mappings[short_state] = full_jwt
                _LOGGER.info(
                    "Shortened JWT state (fallback): %d -> %d chars (short_state: %s)", 
                    len(full_jwt), len(short_state), short_state
                )
                return short_state
        
        return full_jwt
    
    # Fallback to original JWT encoding
    return _original_encode_jwt(hass, data)


@callback
def _patched_decode_jwt(hass: HomeAssistant, encoded: str) -> dict[str, any] | None:
    """Patched JWT decode data with state shortening support for FusionSolar.
    
    This function handles shortened state parameters from OAuth2 providers
    that have URL length limitations like FusionSolar.
    """
    _LOGGER.info("_patched_decode_jwt called with encoded: %s (length: %d)", encoded, len(encoded))
    
    # Check if this might be a shortened state (short alphanumeric string)
    if len(encoded) <= 10 and encoded.isalnum():
        # First try oauth2_middleware if available
        if "oauth2_middleware" in hass.data:
            middleware = hass.data["oauth2_middleware"]
            if encoded in middleware._state_mappings:
                # Restore the original JWT from the mapping
                original_jwt = middleware._state_mappings[encoded]
                _LOGGER.info(
                    "Restored JWT state for FusionSolar: %d -> %d chars", 
                    len(encoded), len(original_jwt)
                )
                
                # Clean up the mapping
                del middleware._state_mappings[encoded]
                
                # Decode the original JWT using original function
                return _original_decode_jwt(hass, original_jwt)
        
        # Fallback: check our own state mappings
        if hasattr(hass, '_fusionsolar_state_mappings') and encoded in hass._fusionsolar_state_mappings:
            # Restore the original JWT from the fallback mapping
            original_jwt = hass._fusionsolar_state_mappings[encoded]
            _LOGGER.info(
                "Restored JWT state (fallback): %d -> %d chars", 
                len(encoded), len(original_jwt)
            )
            
            # Clean up the mapping
            del hass._fusionsolar_state_mappings[encoded]
            
            # Decode the original JWT using original function
            return _original_decode_jwt(hass, original_jwt)
    
    # Standard JWT decoding using original function
    return _original_decode_jwt(hass, encoded)


def patch_oauth2_flow():
    """Patch the OAuth2 flow module with custom JWT functions."""
    # Replace the functions in the module
    config_entry_oauth2_flow._encode_jwt = _patched_encode_jwt
    config_entry_oauth2_flow._decode_jwt = _patched_decode_jwt
    _LOGGER.info("OAuth2 flow patched with FusionSolar state shortening support")


def unpatch_oauth2_flow():
    """Restore original OAuth2 flow functions."""
    config_entry_oauth2_flow._encode_jwt = _original_encode_jwt
    config_entry_oauth2_flow._decode_jwt = _original_decode_jwt
    _LOGGER.info("OAuth2 flow restored to original functions")


class FusionSolarOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """FusionSolar OAuth2 implementation that supports user-configured redirect URI."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
        redirect_uri: str,
    ) -> None:
        """Initialize custom OAuth2 implementation with user-configured redirect URI."""
        super().__init__(
            hass,
            domain,
            client_id,
            client_secret,
            authorize_url,
            token_url,
        )
        self._custom_redirect_uri = redirect_uri
    
    @property
    def redirect_uri(self) -> str:
        """Return the user-configured redirect URI."""
        return self._custom_redirect_uri
