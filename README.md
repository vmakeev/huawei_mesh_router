# Control Huawei mesh routers from Home Assistant

Home Assistant custom component for control Huawei mesh routers over LAN.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/vmakeev/huawei_mesh_router)](https://github.com/vmakeev/huawei_mesh_router/blob/master/LICENSE.md)

[![Release](https://img.shields.io/github/v/release/vmakeev/huawei_mesh_router)](https://github.com/vmakeev/huawei_mesh_router/releases/latest)
[![ReleaseDate](https://img.shields.io/github/release-date/vmakeev/huawei_mesh_router)](https://github.com/vmakeev/huawei_mesh_router/releases/latest)
![Maintained](https://img.shields.io/maintenance/yes/2022)

## Key features

- obtaining information about all routers and connected devices in the entire mesh network:
  - connected devices [tracking](#devices-tracking) and [tagging](#device-tags)
  - device connection parameters (frequency, signal strength, guest and hilink devices)
  - name of the specific router to which the device is connected
  - [number of connected devices](#number-of-connected-devices) (total and for each individual router)
- hardware and firmware version of the primary router
- control of the [NFC](#nfc-switch) (OneHop Connect) on each router separately
- control of the [Fast Roaming](#wi-fi-80211r-switch) function (802.11r)
- control of the [Target Wake Time](#wi-fi-twt-switch) (reduce power consumption of Wi-Fi 6 devices in sleep mode)
- [reboot buttons](#reboot)
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

## Devices tracking

Each tracked device exposes the following attributes:

|    Attribute     |                           Description                         | Only when connected |
|------------------|---------------------------------------------------------------|---------------------|
| `source_type`    | Always `router`                                               | No                  |
| `ip`             | Device IP address                                             | Yes                 |
| `mac`            | MAC address of the device                                     | No                  |
| `hostname`       | Device name according to the device itself                    | No                  |
| `connected_via`  | The name of the router through which the connection was made. | Yes                 |
| `interface_type` | Connection interface type (`5GHz`, `2.4GHz`, `LAN`)           | Yes                 |
| `rssi`           | Signal strength for wireless connections                      | Yes                 |
| `is_guest`       | Is the device connected to the guest network                  | Yes                 |
| `is_hilink`      | Is the device connected via HiLink                            | Yes                 |
| `is_router`      | Is the device are router                                      | Yes                 |
| `tags`           | List of [tags](#device-tags) that marked the device           | No                  |
| `friendly_name`  | Device name provided by the router                            | No                  |

Tracked device names, including routers, can be changed in [your mesh control interface](http://192.168.3.1/html/index.html#/devicecontrol), after which the component will update them in Home Assistant

An example of a markdown card that displays some of the information about the tracked device:

```
My phone: Rssi
{{- " **" + state_attr('device_tracker.my_phone', 'rssi') | string }}** *via*
{{- " **" + state_attr('device_tracker.my_phone', 'connected_via') | string }}**
{{- " **(" + state_attr('device_tracker.my_phone', 'interface_type') | string }})**
```

Result:
My phone: Rssi **30** *via* **Kitchen router** (**5GHz**)

## Sensors

### Number of connected devices

The component provides the ability to obtain the number of connected devices both to the entire mesh network and to specific routers using sensors.

There are two sensors that are always present:
* `sensor.<integration_name>_total_clients_primary_router` - total number of devices connected to the mesh network
* `sensor.<integration_name>_clients_primary_router` - number of devices connected to the primary router

Also, one sensor is created for each additional router in the mesh network:
* `sensor.<integration_name>_clients_<router_name>`

_Note: Sensors for additional routers are located in their own devices._

Each sensor exposes the following attributes:

|         Attribute            |                                 Description                                  |
|------------------------------|------------------------------------------------------------------------------|
| `guest_clients`              | Number of devices connected to the guest network                             |
| `hilink_clients`             | Number of devices connected via HiLink                                       |
| `wireless_clients`           | Number of devices connected wirelessly                                       |
| `lan_clients`                | Number of devices connected by cable                                         |
| `wifi_2_4_clients`           | Number of devices connected to Wi-Fi 2.4 GHz                                 |
| `wifi_5_clients`             | Number of devices connected to Wi-Fi 5 GHz                                   |
| `tagged_<tag_name>_clients`  | Number of connected devices with a specific [tag](#device-tags) `<tag_name>` |
| `untagged_clients`           | Number of connected devices without any [tags](#device-tags)                 |

## Buttons

### Reboot

Allows you to reboot the selected router.

There is one button that is always present:
* `button.<integration_name>_reboot_primary_router`

Also, one button is created for each additional router in the mesh network:
* `button.<integration_name>_reboot_<router_name>`

_Note: Buttons for additional routers are located in their own devices._

## Switches

### NFC switch

Allows you to manage the [OneHop connect](https://consumer.huawei.com/ph/support/content/en-us11307411/) function on each router in the mesh network.

The switches will not be added to Home Assistant if the router does not support NFC.

SPrimary router have the following switch:
* `switch.<integration_name>_nfc_primary_router`

Also, one switch is created for each supported additional router in the mesh network:
* `switch.<integration_name>_nfc_<router_name>`

_Note: Switches for additional routers are located in their own devices._

### Wi-Fi 802.11r switch

Allows you to manage the fast roaming feature ([Wi-Fi 802.11r](https://support.huawei.com/enterprise/en/doc/EDOC1000178191/f0c65b61/80211r-fast-roaming))

The switch will not be added to Home Assistant if the router does not support Wi-Fi 802.11r.

### Wi-Fi TWT switch

Allows you to manage the Wi-Fi Target Wake Time ([TWT](https://forum.huawei.com/enterprise/en/what-is-twt-in-wifi-devices/thread/623758-869)) feature

The switch will not be added to Home Assistant if the router does not support Wi-Fi TWT.

## Customization

### Device tags

The component allows you to attach one or more tags to each client device in order to be able to use in automation the number of devices marked with a tag, connected to a specific router, or to the entire mesh network.

The component will attempt to load the device tag-to-MAC mapping from the file located at `<home assistant config folder>/.storage/huawei_mesh_<long_config_id>_tags`. If the file does not exist, then the component will create it with a usage example:

```
{
  "version": 1,
  "minor_version": 1,
  "key": "huawei_mesh_<long_config_id>_tags",
  "data": {
    "homeowners": [
      "place_mac_addresses_here"
    ],
    "visitors": [
      "place_mac_addresses_here"
    ]
  }
}
```

_Note: unfortunately, editing the list of tags and devices associated with them is currently available only through editing this file._

Each tag can have multiple devices associated with it. Each device can be associated with multiple tags.

Example:
```
{
  "version": 1,
  "minor_version": 1,
  "key": "huawei_mesh_<long_config_id>_tags",
  "data": {
    "my_awesome_tag": [
      "00:11:22:33:44:55",
      "A0:B1:C2:D3:E4:F5",
      "F5:E4:D3:C2:B1:A0"
    ],
    "another_tag": [
      "00:11:22:33:44:55",
      "A9:B8:C7:D6:E5:F4"
    ],
    "third_tag": [
      "99:88:77:66:55:44"
    ]
  }
}
```

**Usage example:**

|   Tag name   |          Tagged Devices           |
|--------------|-----------------------------------|
|  homeowners  | Michael's phone, Michael's laptop |
|  visitors    | Victoria's phone, Eugene's phone  |


- Michael's phone is connected to the "Garage" router
- Michael's laptop is connected to the "Living room" router
- Victoria's phone is connected to the "Living room" router
- Eugene's phone is connected to the "primary" router

In this scenario, the sensors for the number of connected devices will provide the following attributes:

|                 Sensor                        | Attributes and values |
|-----------------------------------------------|-----------------------|
| `sensor.huawei_mesh_3_clients_garage`         | `guest_clients`: 0 <br/> `hilink_clients`: 0<br/>`wireless_clients`: 1<br />`lan_clients`: 0<br />`wifi_2_4_clients`: 0<br />`wifi_5_clients`: 1<br />`tagged_homeowners_clients`: 1 _// Michael's phone_<br />`tagged_visitors_clients`: 0 <br />`untagged_clients`: 0 |
| `sensor.huawei_mesh_3_clients_living_room`    | `guest_clients`: 0 <br/> `hilink_clients`: 0<br/>`wireless_clients`: 2<br />`lan_clients`: 0<br />`wifi_2_4_clients`: 0<br />`wifi_5_clients`: 2<br />`tagged_homeowners_clients`: 1 _// Michael's laptop_<br />`tagged_visitors_clients`: 1 _// Victoria's phone_<br />`untagged_clients`: 0 |
| `sensor.huawei_mesh_3_clients_primary_router` | `guest_clients`: 0 <br/> `hilink_clients`: 2<br/>`wireless_clients`: 3<br />`lan_clients`: 0<br />`wifi_2_4_clients`: 0<br />`wifi_5_clients`: 3<br />`tagged_homeowners_clients`: 0<br />`tagged_visitors_clients`: 1 _// Eugene's phone_ <br />`untagged_clients`: 2 _// Garage and Living room routers_|
