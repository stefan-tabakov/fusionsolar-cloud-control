from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FusionSolarCloudControlCoordinator


class FusionSolarBaseEntity(CoordinatorEntity[FusionSolarCloudControlCoordinator]):
    """Base class for FusionSolar entities."""

    def __init__(self, coordinator: FusionSolarCloudControlCoordinator, plant) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._plant = plant

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._plant.id)},
            "name": self._plant.name,
            "manufacturer": "Huawei",
            "model": "FusionSolar Plant",
        }
