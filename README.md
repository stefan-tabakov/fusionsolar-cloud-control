# FusionSolar Cloud Control

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

Home Assistant integration for controlling Huawei FusionSolar plants via the SmartPVMS Northbound API.

## Features

- **Plant On/Off Switch**: Turn your solar plant on or off remotely
- **Power Limit Slider**: Set power output limit as a percentage of plant capacity  
- **Daily Energy Sensor**: Monitor cumulative daily energy production in kWh (perfect for utility meter calculations and 15-minute price interval forecasting)
- **Smart Rate Limiting**: Automatically respects API limits (5-minute polling during day, 30-minute during night)
- **Night Mode**: Reduces API calls when sun is down to save quota
- **OAuth2 Authentication**: Secure authentication with Huawei FusionSolar

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → Custom repositories
3. Add `https://github.com/stefan-tabakov/fusionsolar-cloud-control` as Integration type
4. Search for "FusionSolar Cloud Control" and install
5. Restart Home Assistant
6. Go to Settings → Devices & Services → Add Integration → FusionSolar Cloud Control

### Manual Installation

1. Copy the `fusionsolar_cloud_control` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration → FusionSolar Cloud Control

## Configuration

The integration uses OAuth2 authentication. You'll need to register an application in the Huawei FusionSolar portal:

1. Go to [Huawei FusionSolar](https://eu5.fusionsolar.huawei.com) → System Management → OpenAPI Management
2. Create a new OpenAPI 2.0 application
3. Set the redirect URI (e.g., `https://your-ha-instance.duckdns.org:8123/auth/external/callback`)
4. Note down the Client ID and Client Secret
5. During integration setup, enter:
   - Client ID
   - Client Secret  
   - Region (default: eu5)
   - Redirect URI

## API Rate Limits

The integration automatically respects Huawei's API rate limits:

| API Category | Rate Limit |
|-------------|------------|
| Basic APIs | 1000 calls/day |
| Control APIs | 100 calls/day |
| Real-time Data | 1 call per 5 minutes per plant |

**Optimization Features:**
- Day polling: Every 5 minutes (minimum allowed)
- Night polling: Every 30 minutes (configurable hours)
- Smart caching during rate limits

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| `{plant_name} On/Off` | Switch | Turn plant on/off |
| `{plant_name} Power Limit` | Number | Set power limit percentage (0–100%) |
| `{plant_name} Daily Energy` | Sensor | Cumulative daily energy in kWh |

### Sensor Attributes
- `month_energy_kwh`: Monthly cumulative energy
- `year_energy_kwh`: Yearly cumulative energy  
- `total_energy_kwh`: Total lifetime energy
- `plant_status`: Plant operational status

## Supported Regions

- EU: `eu5.fusionsolar.huawei.com`
- Global: `intl.fusionsolar.huawei.com`
- CN: `cn5.fusionsolar.huawei.com`

## Troubleshooting

### Rate Limit Errors (407)
The integration handles rate limits automatically by:
1. Reducing polling interval to 5 minutes minimum
2. Skipping device data fetches during night mode
3. Using cached data when rate limited
4. Implementing exponential backoff retries

### Missing Entities
If entities don't appear:
1. Check Home Assistant logs for errors
2. Verify OAuth2 credentials are correct
3. Ensure plants are visible in FusionSolar portal
4. Restart Home Assistant after configuration

## License

This project is provided as-is for personal use.
