# Control Huawei mesh routers from Home Assistant

Home Assistant custom component for control Huawei mesh routers over LAN.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/vmakeev/huawei_mesh_router)](https://github.com/vmakeev/huawei_mesh_router/blob/master/LICENSE.md)

[![Release](https://img.shields.io/github/v/release/vmakeev/huawei_mesh_router)](https://github.com/vmakeev/huawei_mesh_router/releases/latest)
[![ReleaseDate](https://img.shields.io/github/release-date/vmakeev/huawei_mesh_router)](https://github.com/vmakeev/huawei_mesh_router/releases/latest)
![Maintained](https://img.shields.io/maintenance/yes/2022)

## Key features

- obtaining information about all routers and connected devices in the entire mesh network:
  - connected devices tracking and tagging
  - device connection parameters (frequency, signal strength, guest and hilink devices)
  - name of the specific router to which the device is connected
  - number of connected devices (total and for each individual router)
- hardware and firmware version of the primary router
- internet connection details
- uptime of each router
- control of the NFC (OneHop Connect) on each router separately
- control of the Fast Roaming function (802.11r)
- control of the Target Wake Time (reduce power consumption of Wi-Fi 6 devices in sleep mode)
- reboot buttons
- automatic detection of available functions

## Supported models

|                                        Name                                        |  Model | Confirmed |           Notes                         |
|------------------------------------------------------------------------------------|--------|-----------|-----------------------------------------|
| [Huawei WiFi Mesh 3](https://consumer.huawei.com/en/routers/wifi-mesh3/)           | WS8100 |    Yes    | All features are available              |
| [Huawei WiFi AX3 Dual-core](https://consumer.huawei.com/en/routers/ax3-dual-core/) | WS7100 |    Yes    | No NFC switches (unsupported by router) |
| [Huawei WiFi AX3 Quad-core](https://consumer.huawei.com/en/routers/ax3-quad-core/) | WS7200 |    Yes    | ---                                     |
| [Huawei WiFi AX3 Pro](https://consumer.huawei.com/en/routers/ax3-pro/)             | WS7206 |    No     | ---                                     |
| Other routers with HarmonyOS                                                       | ------ |    No     | Will most likely work                   

## Installation

### Manual

Copy `huawei_mesh_router` folder from [latest release](https://github.com/vmakeev/huawei_mesh_router/releases/latest) to `custom_components` folder in your Home Assistant config folder and restart Home Assistant. The final path to folder should look like this: `<home-assistant-config-folder>/custom_components/huawei_mesh_router`

### HACS

[Add a custom repository](https://hacs.xyz/docs/faq/custom_repositories/) `https://github.com/vmakeev/huawei_mesh_router` with `Integration` category to [HACS](https://hacs.xyz/) and restart Home Assistant.

## Configuration

Configuration > [Integrations](https://my.home-assistant.io/redirect/integrations/) > Add Integration > [Huawei Mesh Router](https://my.home-assistant.io/redirect/config_flow_start/?domain=huawei_mesh_router)

By default, Huawei mesh routers use the username `admin`, although it is not displayed in the web interface and mobile applications.

![Integration](docs/images/integration.png)

## Devices tracking

The component allows you to track all devices connected to your mesh network. [Read more](docs/device-tracking.md)

You can attach one or more tags to each client device in order to be able to use in automation the number of devices marked with a tag, connected to a specific router, or to the entire mesh network. [Read more](docs/device-tags.md)

## Sensors

* Number of connected devices ([read more](docs/sensors.md#number-of-connected-devices))
* Uptime ([read more](docs/sensors.md#uptime))
* Internet connection ([read more](docs/sensors.md#internet-connection))

## Controls

### Buttons

* Reboot router ([read more](docs/controls.md#reboot))

### Switches

* NFC switch ([read more](docs/controls.md#nfc-switch))
* Wi-Fi 802.11r switch ([read more](docs/controls.md#wi-fi-80211r-switch))
* Wi-Fi TWT switch ([read more](docs/controls.md#wi-fi-6-twt-switch))
