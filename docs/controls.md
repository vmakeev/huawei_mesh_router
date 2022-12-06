# Controls

The component creates a separate device for each router connected to the mesh network. 

![Devices](images/integration_devices.png)

Each device has its own set of controls. 

The primary router has more controls than the additional ones.

**Primary router controls:**

![Primary device](images/device_primary_controls.png)

**Additional router controls:**

![Additional device](images/device_additional_controls.png)


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

Primary router have the following switch:
* `switch.<integration_name>_nfc_primary_router`

Also, one switch is created for each supported additional router in the mesh network:
* `switch.<integration_name>_nfc_<router_name>`

_Note: Switches for additional routers are located in their own devices._

### Wi-Fi 802.11r switch

Allows you to manage the fast roaming feature ([Wi-Fi 802.11r](https://support.huawei.com/enterprise/en/doc/EDOC1000178191/f0c65b61/80211r-fast-roaming))

The switch will not be added to Home Assistant if the router does not support Wi-Fi 802.11r.

### Wi-Fi 6 TWT switch

Allows you to manage the Wi-Fi Target Wake Time ([TWT](https://forum.huawei.com/enterprise/en/what-is-twt-in-wifi-devices/thread/623758-869)) feature

The switch will not be added to Home Assistant if the router does not support Wi-Fi TWT.