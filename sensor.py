"""Sensor platform for FusionSolar Cloud Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import UnitOfEnergy

from .const import DOMAIN, PLANT_DAILY_ENERGY_SENSOR
from .coordinator import FusionSolarCloudControlCoordinator
from .entity import FusionSolarBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FusionSolar sensors from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    plants = data["plants"]
    coordinator = data["coordinator"]

    entities = [
        PlantDailyEnergySensor(coordinator, plant)
        for plant in plants
    ]

    async_add_entities(entities)


class PlantDailyEnergySensor(FusionSolarBaseEntity, SensorEntity):
    """Represents a FusionSolar Plant daily energy sensor (cumulative)."""

    def __init__(
        self, coordinator: FusionSolarCloudControlCoordinator, plant
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, plant)
        self._attr_translation_key = PLANT_DAILY_ENERGY_SENSOR
        self._attr_unique_id = f"{plant.id}_{PLANT_DAILY_ENERGY_SENSOR}"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:solar-power"

    @property
    def native_value(self) -> float | None:
        """Return the daily cumulative energy in kWh."""
        if self.coordinator.data and self._plant.id in self.coordinator.data:
            plant_data = self.coordinator.data[self._plant.id]
            if plant_data.day_power_kwh is not None:
                return round(float(plant_data.day_power_kwh), 2)
        return None
        
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not (super().available and self.coordinator.data and self._plant.id in self.coordinator.data):
            return False
            
        plant_data = self.coordinator.data[self._plant.id]
        # Entity is unavailable if API data is not available
        return plant_data.data_available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}
        
        if self.coordinator.data and self._plant.id in self.coordinator.data:
            plant_data = self.coordinator.data[self._plant.id]
            
            # Add other cumulative energy metrics
            if plant_data.month_power_kwh is not None:
                attributes["month_energy_kwh"] = round(float(plant_data.month_power_kwh), 2)
            
            if plant_data.year_power_kwh is not None:
                attributes["year_energy_kwh"] = round(float(plant_data.year_power_kwh), 2)
            
            if plant_data.total_power_kwh is not None:
                attributes["total_energy_kwh"] = round(float(plant_data.total_power_kwh), 2)
            
            # Add plant status if available
            if plant_data.plant_status:
                attributes["plant_status"] = plant_data.plant_status
        
        return attributes
