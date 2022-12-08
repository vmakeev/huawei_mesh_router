# Devices tracking

The component allows you to track all devices connected to your mesh network.

Each tracked device exposes the following attributes:

|    Attribute     |                                          Description                                           | Only when connected |
|------------------|------------------------------------------------------------------------------------------------|---------------------|
| `source_type`    | Always `router`                                                                                | No                  |
| `ip`             | Device IP address                                                                              | Yes                 |
| `mac`            | MAC address of the device                                                                      | No                  |
| `hostname`       | Device name according to the device itself                                                     | No                  |
| `connected_via`  | The name of the router through which the connection was made                                   | Yes                 |
| `interface_type` | Connection interface type (`5GHz`, `2.4GHz`, `LAN`)                                            | Yes                 |
| `rssi`           | Signal strength for wireless connections                                                       | Yes                 |
| `is_guest`       | Is the device connected to the guest network                                                   | Yes                 |
| `is_hilink`      | Is the device connected via HiLink                                                             | Yes                 |
| `is_router`      | Is the device are router                                                                       | Yes                 |
| `tags`           | List of [tags](device-tags.md#device-tags) that marked the device                              | No                  |
| `filters_list`   | Blacklist, Whitelist or None (see [access control mode](controls.md#wifi-access-control-mode)) | No                  |
| `friendly_name`  | Device name provided by the router                                                             | No                  |

![alt text](images/device_tracker.png "Title")

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