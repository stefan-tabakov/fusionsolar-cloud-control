from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLANT_POWER_LIMIT_SLIDER
from .coordinator import FusionSolarCloudControlCoordinator
from .entity import FusionSolarBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FusionSolar numbers from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    plants = data["plants"]
    coordinator = data["coordinator"]

    entities = [
        PowerLimitSlider(coordinator, plant)
        for plant in plants
    ]

    async_add_entities(entities)


class PowerLimitSlider(FusionSolarBaseEntity, NumberEntity):
    """Represents a FusionSolar Plant Power Limit slider."""

    def __init__(
        self, coordinator: FusionSolarCloudControlCoordinator, plant
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, plant)
        self._attr_translation_key = PLANT_POWER_LIMIT_SLIDER
        self._attr_unique_id = f"{plant.id}_{PLANT_POWER_LIMIT_SLIDER}"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> float | None:
        """Return the current configured power limit as percentage of plant capacity."""
        if self.coordinator.data and self._plant.id in self.coordinator.data:
            plant_data = self.coordinator.data[self._plant.id]
            if plant_data.power_limit_percent is not None:
                return float(plant_data.power_limit_percent)
        return None
        
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not (super().available and self.coordinator.data and self._plant.id in self.coordinator.data):
            return False
            
        plant_data = self.coordinator.data[self._plant.id]
        # Entity is unavailable if API data is not available (e.g., due to rate limiting)
        return plant_data.data_available

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        _LOGGER.debug(f"Setting power limit for plant {self._plant.name} to {value}%")

        if self._plant.capacity > 0:
            power_kw = self._plant.capacity * (value / 100.0)
            success = await self.coordinator.async_set_plant_power_limit(self._plant.id, power_kw)
            if success:
                # Update coordinator data to reflect the successful control operation
                if self.coordinator.data and self._plant.id in self.coordinator.data:
                    self.coordinator.data[self._plant.id].power_limit_percent = value
                    self.coordinator.data[self._plant.id].is_plant_on = value > 0
                    self.async_write_ha_state()
                _LOGGER.debug("Plant %s power limit set to %s%% successfully", self._plant.name, value)
            else:
                _LOGGER.warning("Failed to set power limit for plant %s to %s%%", self._plant.name, value)
        else:
            _LOGGER.warning("Cannot set power limit for %s because its capacity is unknown.", self._plant.name)
