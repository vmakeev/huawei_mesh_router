# Control Huawei WiFi Mesh 3 routers from Home Assistant

Home Assistant custom component for control [Huawei WiFi Mesh 3](https://consumer.huawei.com/en/routers/wifi-mesh3/) routers over LAN.

**0.7.2**

- sensors for the number of connected devices (total and for each individual router)
- enable/disable NFC
- enable/disable TWT (reduce power consumption of Wi-Fi 6 devices in sleep mode)
- control of the fast roaming function (802.11r)
- connected devices tracking
- obtaining of the specific router to which the device is connected
- obtaining of device connection parameters (frequency, signal strength, guest and hilink devices)
- hardware and firmware version of the router

## Installation

Manually copy `huawei_mesh_router` folder from [latest release](https://github.com/vmakeev/huawei_mesh_router/releases/latest) to `custom_components` folder in your Home Assistant config folder and restart Home Assistant.

## Configuration

Configuration > [Integrations](https://my.home-assistant.io/redirect/integrations/) > Add Integration > [Huawei Mesh Router](https://my.home-assistant.io/redirect/config_flow_start/?domain=huawei_mesh_router)

By default, Huawei WiFi Mesh 3 routers use the username `admin`, although it is not displayed in the web interface and mobile applications.

## Devices tracking

Each tracked device exposes the following attributes:

|    Attribute     |    Description            | Only when connected |
|------------------|---------------------------|---------------------|
| `source_type`    | Always `router`           | No                  |
| `ip`             | Device IP address         | Yes                 |
| `mac`            | MAC address of the device | No                  |
| `hostname`       | Device name according to the device itself | No |
| `connected_via`  | The name of the router through which the connection was made. For the primary router - `Huawei Mesh 3` (or your configuration name) | Yes |
| `interface_type` | Connection interface type (`5GHz`, `2.4GHz`, `LAN`) | Yes |
| `rssi`           | Signal strength for wireless connections | Yes  |
| `is_guest`       | Is the device connected to the guest network | Yes |
| `is_hilink`      | Is the device connected via HiLink (usually other routers) | Yes |
| `friendly_name`  | Device name provided by the router | No         |

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

The component provides the ability to obtain the number of connected devices both to the entire mesh network and to specific routers using sensors. named 

There are two sensors that are always present:
* `sensor.<integration_name>_clients_total` - total number of devices connected to the mesh network
* `sensor.<integration_name>_clients_primary_router` - number of devices connected to the primary router

Also, one sensor is created for each additional router in the mesh network:
* `sensor.<integration_name>_clients_<router_name>`

_Note: when additional routers are disconnected from the network, their personal sensors are automatically deleted._

Each sensor exposes the following attributes:

|    Attribute       |    Description                                   |
|--------------------|--------------------------------------------------|
| `guest_clients`    | Number of devices connected to the guest network |
| `wireless_clients` | Number of devices connected wirelessly           |
| `lan_clients`      | Number of devices connected by cable             |
| `wifi_2_4_clients` | Number of devices connected to WiFi 2.4 GHz      |
| `wifi_5_clients`   | Number of devices connected to WiFi 5 GHz        |