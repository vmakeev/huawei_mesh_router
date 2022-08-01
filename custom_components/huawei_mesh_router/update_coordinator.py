"""Huawei Controller for Huawei Router."""

import logging
from datetime import timedelta
from typing import Dict

from aiohttp import ClientResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .connected_device import ConnectedDevice
from .router_info import RouterInfo

from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
    SWITCHES_NFC,
    SWITCHES_WIFI_80211R,
    SWITCHES_WIFI_TWT,
)

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)

from .huaweiapi import HuaweiApi

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   router_data_check_authorized
# ---------------------------
def router_data_check_authorized(response: ClientResponse, result: Dict) -> bool:
    if response.status == 404:
        return False
    if result is None or result.get("EmuiVersion", "-") == "-":
        return False
    return True


# ---------------------------
#   HuaweiControllerDataUpdateCoordinator
# ---------------------------
class HuaweiControllerDataUpdateCoordinator(DataUpdateCoordinator):
    """HuaweiController Class"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize HuaweiController."""
        self._router_info: RouterInfo | None = None
        self._switch_states: Dict[str, bool] = {}
        self._connected_devices: Dict[str, ConnectedDevice] = {}

        self._api: HuaweiApi = HuaweiApi(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            use_ssl=config_entry.data[CONF_SSL],
            user=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            verify_ssl=config_entry.data[CONF_VERIFY_SSL],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.data[CONF_NAME],
            update_method=self.async_update,
            update_interval=timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL]),
        )

    @property
    def unique_id(self) -> str:
        """Return the system descriptor."""
        entry = self.config_entry

        if entry.unique_id:
            return entry.unique_id

        return entry.entry_id

    @property
    def cfg_host(self) -> str:
        return self.config_entry.data[CONF_HOST]

    @property
    def router_info(self) -> RouterInfo | None:
        return self._router_info

    @property
    def switches(self) -> Dict[str, bool]:
        return self._switch_states

    @property
    def connected_devices(self) -> Dict[str, ConnectedDevice]:
        return self._connected_devices

    @property
    def configuration_url(self) -> str:
        return self._api.router_url

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            configuration_url=self.configuration_url,
            identifiers={(DOMAIN, self.router_info.serial_number)},
            manufacturer=ATTR_MANUFACTURER,
            model=self.router_info.model,
            name=self.name,
            hw_version=self.router_info.hardware_version,
            sw_version=self.router_info.software_version,
        )

    async def async_update(self) -> None:
        _LOGGER.debug("Update started")
        await self._update_router_data()
        await self._update_nfc_switch()
        await self._update_wifi_basic_switches()
        await self._update_connected_devices()
        _LOGGER.debug("Update completed")

    async def _update_router_data(self) -> None:
        _LOGGER.debug("Updating router data")
        data = await self._api.get("api/system/deviceinfo", check_authorized=router_data_check_authorized)
        self._router_info = RouterInfo(
            serial_number=data.get("SerialNumber"),
            software_version=data.get("SoftwareVersion"),
            hardware_version=data.get("HardwareVersion"),
            friendly_name=data.get("FriendlyName"),
            harmony_os_version=data.get('HarmonyOSVersion'),
            cust_device_name=data.get('custinfo', {}).get('CustDeviceName'),
            cust_device_type=data.get('custinfo', {}).get('CustDeviceType')
        )
        _LOGGER.debug('Router data updated')

    def unload(self) -> None:
        self._api.disconnect()

    async def _update_nfc_switch(self) -> None:
        _LOGGER.debug('Updating nfc switch state')
        data = await self._api.get("api/bsp/nfc_switch")
        self._switch_states[SWITCHES_NFC] = data.get('nfcSwitch') == 1
        _LOGGER.debug('Nfc switch state updated to %s', self._switch_states[SWITCHES_NFC])

    async def _update_wifi_basic_switches(self) -> None:
        _LOGGER.debug('Updating 80211r and TWT switch states')
        data = await self._api.get("api/ntwk/WlanGuideBasic?type=notshowpassall")
        self._switch_states[SWITCHES_WIFI_80211R] = data.get('WifiConfig', [{}])[0].get('Dot11REnable')
        self._switch_states[SWITCHES_WIFI_TWT] = data.get('WifiConfig', [{}])[0].get('TWTEnable')
        _LOGGER.debug('80211r switch state updated to %s, TWT switch state updated to %s',
                      self._switch_states[SWITCHES_WIFI_80211R],
                      self._switch_states[SWITCHES_WIFI_TWT])

    async def _update_connected_devices(self) -> None:
        _LOGGER.debug('Updating connected devices')
        devices_data = await self._api.get("api/system/HostInfo")
        devices_topology = await self._api.get("api/device/topology")

        mesh_routers = filter(lambda item: item.get('HiLinkType') == "Device",
                              devices_topology)

        devices_to_routers = {}
        for mesh_router in mesh_routers:
            router_name = next((item.get('ActualName') for item in devices_data
                                if item.get('MACAddress') == mesh_router.get('MACAddress')),
                               mesh_router.get('MACAddress'))
            if 'ConnectedDevices' in mesh_router:
                for mesh_connected_device in mesh_router.get('ConnectedDevices', []):
                    if 'MACAddress' in mesh_connected_device:
                        devices_to_routers[mesh_connected_device['MACAddress']] = router_name

        for device_data in devices_data:
            mac: str = device_data['MACAddress']
            host_name: str = device_data.get('HostName', f'device_{mac}')
            name: str = device_data.get('ActualName', host_name)
            is_active: bool = device_data.get('Active', False)

            if mac in self._connected_devices:
                device = self._connected_devices[mac]
            else:
                device = ConnectedDevice(name, host_name, mac, is_active)
                self._connected_devices[device.mac] = device

            if is_active:
                connected_via = devices_to_routers.get(mac, self.name or 'Primary router')
                device.update_device_data(name, host_name, True,
                                          connected_via=connected_via,
                                          ip_address=device_data.get('IPAddress'),
                                          interface_type=device_data.get('InterfaceType'),
                                          rssi=device_data.get('rssi'),
                                          is_guest=device_data.get('IsGuest'),
                                          is_hilink=device_data.get('HiLinkDevice')
                                          )
            else:
                device.update_device_data(name, host_name, False)

        _LOGGER.debug('Connected devices updated')

    # ---------------------------
    #   set_value_async
    # ---------------------------
    async def async_set_value(self, path: str, value: Dict, extra_data: Dict | None = None) -> Dict:
        """Change value using Huawei API"""
        result = await self._api.post(path, value, extra_data=extra_data)
        await self.async_request_refresh()
        return result

    # ---------------------------
    #   get_value_async
    # ---------------------------
    async def async_get_value(self, path: str) -> Dict:
        """Retrieve value using Huawei API"""
        return await self._api.get(path)
