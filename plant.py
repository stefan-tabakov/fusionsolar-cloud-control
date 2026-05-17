from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class PlantInfo:
    id: str
    code: str
    name: str
    address: str
    capacity: float


@dataclass(frozen=True)
class PlantRealTimeData:
    """Real-time metrics from getStationRealKpi API."""
    day_power_kwh: Optional[float]      # Today's cumulative energy
    day_income: Optional[float]         # Today's income in local currency
    month_power_kwh: Optional[float]     # This month's cumulative energy
    month_income: Optional[float]       # This month's income
    year_power_kwh: Optional[float]     # This year's cumulative energy
    year_income: Optional[float]        # This year's income
    total_power_kwh: Optional[float]     # Lifetime cumulative energy
    total_income: Optional[float]        # Lifetime income
    real_health_state: Optional[int]     # Plant health status
    plant_status: Optional[str]         # Plant operational status

async def create_plant_info(data: dict[str, any]) -> PlantInfo:
    """Create PlantInfo from raw API data."""
    plant_info = PlantInfo(
        id=_get_str_property(data, "plantCode"),
        code=_get_str_property(data, "plantCode"),
        name=_get_str_property(data, "plantName"),
        address=_get_str_property(data, "plantAddress"),
        capacity=_get_float_property(data, "capacity"),
    )

    return plant_info

def create_plant_realtime_data(data: dict) -> PlantRealTimeData:
    """Create PlantRealTimeData from raw API response."""
    # Extract dataItemMap from the response structure
    if isinstance(data, list) and len(data) > 0:
        data_item = data[0]
    elif isinstance(data, dict):
        data_item = data
    else:
        data_item = {}
    
    data_map = data_item.get("dataItemMap", {}) if isinstance(data_item, dict) else {}
    
    return PlantRealTimeData(
        day_power_kwh=_get_optional_float(data_map, "day_power"),
        day_income=_get_optional_float(data_map, "day_income"),
        month_power_kwh=_get_optional_float(data_map, "month_power"),
        month_income=_get_optional_float(data_map, "month_income"),
        year_power_kwh=_get_optional_float(data_map, "year_power"),
        year_income=_get_optional_float(data_map, "year_income"),
        total_power_kwh=_get_optional_float(data_map, "total_power"),
        total_income=_get_optional_float(data_map, "total_income"),
        real_health_state=_get_optional_int(data_map, "real_health_state"),
        plant_status=data_item.get("plantStatus") if isinstance(data_item, dict) else None,
    )

def _get_optional_float(data: dict, field: str) -> Optional[float]:
    """Get optional float property from data."""
    value = data.get(field)
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def _get_optional_int(data: dict, field: str) -> Optional[int]:
    """Get optional int property from data."""
    value = data.get(field)
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def _get_str_property(data: dict[str, any], field: str) -> str:
    """Get string property from data, with fallback to empty string."""
    value = data.get(field)
    return str(value) if value is not None else ""

def _get_float_property(data: dict[str, any], field: str) -> float:
    """Get float property from data, with fallback to 0.0."""
    value = data.get(field)
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0