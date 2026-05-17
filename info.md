# FusionSolar Cloud Control

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

Home Assistant integration for controlling Huawei FusionSolar plants via the SmartPVMS Northbound API.

## Features

- **Plant On/Off Switch**: Turn your solar plant on or off remotely
- **Power Limit Slider**: Set power output limit as a percentage of plant capacity
- **Current Power Sensor**: Monitor real-time power output from your inverters
- **Smart Rate Limiting**: Automatically respects API limits and stops polling at night
- **OAuth2 Authentication**: Secure authentication with Huawei FusionSolar

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "FusionSolar Cloud Control" and install
3. Restart Home Assistant
4. Go to Settings > Devices & Services > Add Integration > FusionSolar Cloud Control

### Manual Installation

1. Copy the `fusionsolar_cloud_control` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration > FusionSolar Cloud Control

## Configuration

The integration uses OAuth2 authentication. You'll need:
- Client ID from Huawei FusionSolar
- Client Secret from Huawei FusionSolar
- Redirect URI configured in your OAuth2 app

## API Rate Limits

The integration automatically respects Huawei's API rate limits:
- **Basic APIs**: 1000 calls/day
- **Control APIs**: 100 calls/day
- **Real-time Data**: 1 call per 5 minutes per plant

## Supported Regions

- EU (eu5.fusionsolar.huawei.com)
- Other regions can be configured via custom region setting

## License

MIT License - See LICENSE file for details
