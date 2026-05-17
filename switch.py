from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLANT_ON_OFF_SWITCH
from .coordinator import FusionSolarCloudControlCoordinator
from .entity import FusionSolarBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FusionSolar switches from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    plants = data["plants"]
    coordinator = data["coordinator"]

    entities = [
        OnOffSwitch(coordinator, plant)
        for plant in plants
    ]

    async_add_entities(entities)

class OnOffSwitch(FusionSolarBaseEntity, SwitchEntity):
    """Represents a FusionSolar Plant On/Off switch."""

    def __init__(
        self, coordinator: FusionSolarCloudControlCoordinator, plant
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, plant)
        self._attr_translation_key = PLANT_ON_OFF_SWITCH
        self._attr_unique_id = f"{plant.id}_{PLANT_ON_OFF_SWITCH}"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on (plant is working - either unlimited or limited > 0)."""
        if self.coordinator.data and self._plant.id in self.coordinator.data:
            plant_data = self.coordinator.data[self._plant.id]
            return plant_data.is_plant_on if plant_data.is_plant_on is not None else False
        return False
        
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not (super().available and self.coordinator.data and self._plant.id in self.coordinator.data):
            return False
            
        plant_data = self.coordinator.data[self._plant.id]
        # Entity is unavailable if API data is not available (e.g., due to rate limiting)
        return plant_data.data_available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        _LOGGER.debug(f"Turning on plant {self._plant.name}")
        success = await self.coordinator.async_turn_on_plant(self._plant.id)
        if success:
            # Update coordinator data to reflect the successful control operation
            if self.coordinator.data and self._plant.id in self.coordinator.data:
                self.coordinator.data[self._plant.id].is_plant_on = True
                self.async_write_ha_state()
            _LOGGER.debug("Plant %s turned on successfully", self._plant.name)
        else:
            _LOGGER.warning("Failed to turn on plant %s", self._plant.name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        _LOGGER.debug(f"Turning off plant {self._plant.name}")
        success = await self.coordinator.async_turn_off_plant(self._plant.id)
        if success:
            # Update coordinator data to reflect the successful control operation
            if self.coordinator.data and self._plant.id in self.coordinator.data:
                self.coordinator.data[self._plant.id].is_plant_on = False
                self.async_write_ha_state()
            _LOGGER.debug("Plant %s turned off successfully", self._plant.name)
        else:
            _LOGGER.warning("Failed to turn off plant %s", self._plant.name)
