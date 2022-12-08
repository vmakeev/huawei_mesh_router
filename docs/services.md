# Services

The component provides access to some services that can be used in your automations or other use cases.

## Access lists

See also: [access control mode](controls.md#wifi-access-control-mode)

### Add device to the blacklist

Service name: `huawei_mesh_router.blacklist_add`

Example:
```
service: huawei_mesh_router.blacklist_add
data:
  mac_address: "11:22:33:44:55:66"
```

![Service call](images/service_blacklist_add.png)

Adds a device with the specified MAC address to the blacklist. If the device is on the whitelist, it will automatically be removed from it.

### Add device to the whitelist

Service name: `huawei_mesh_router.whitelist_add`

Example:
```
service: huawei_mesh_router.whitelist_add
data:
  mac_address: "11:22:33:44:55:66"
```

![Service call](images/service_whitelist_add.png)

Adds a device with the specified MAC address to the whitelist. If the device is on the blacklist, it will automatically be removed from it.

### Remove device from the blacklist

Service name: `huawei_mesh_router.blacklist_remove`

Example:
```
service: huawei_mesh_router.blacklist_remove
data:
  mac_address: "11:22:33:44:55:66"
```

![Service call](images/service_blacklist_remove.png)

Removes a device with the specified MAC address from the blacklist.

### Remove device from the whitelist

Service name: `huawei_mesh_router.whitelist_remove`

Example:
```
service: huawei_mesh_router.whitelist_remove
data:
  mac_address: "11:22:33:44:55:66"
```

![Service call](images/service_whitelist_remove.png)

Removes a device with the specified MAC address from the whitelist.