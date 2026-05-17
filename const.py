DOMAIN = "fusionsolar_cloud_control"

# Platforms
SWITCH = "switch"
NUMBER = "number"
SENSOR = "sensor"
PLATFORMS = [SWITCH, NUMBER, SENSOR]

# Sensor entity types
PLANT_DAILY_ENERGY_SENSOR = "plant_daily_energy_sensor"

# Plant controls
PLANT_ON_OFF_SWITCH = "plant_on_off_switch"
PLANT_POWER_LIMIT_SLIDER = "plant_power_limit_slider"
SCOPE = "pvms.openapi.basic pvms.openapi.control"

# Default OAuth2 configuration
DEFAULT_CLIENT_ID = ""
DEFAULT_CLIENT_SECRET = ""
DEFAULT_REGION = "eu5"
DEFAULT_REDIRECT_URI = "https://enka-energy-ha.duckdns.org:8123/auth/external/callback"

# OAuth2 URLs
AUTHORIZE_URL = "https://oauth2.fusionsolar.huawei.com/rest/dp/uidm/oauth2/v1/authorize"
TOKEN_URL = "https://oauth2.fusionsolar.huawei.com/rest/dp/uidm/oauth2/v1/token"

# Night mode defaults (no solar production expected)
DEFAULT_NIGHT_START = "22:00"  # 10 PM
DEFAULT_NIGHT_END = "05:00"    # 5 AM