"""Huawei Controller for Huawei Router."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable, Iterable

from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .connected_device import ConnectedDevice

from .client.huaweiapi import (
    HuaweiApi,
    CONNECTED_VIA_ID_PRIMARY,
    SWITCH_NFC,
    SWITCH_WIFI_TWT,
    SWITCH_WIFI_80211R,
    FEATURE_NFC,
    FEATURE_WIFI_80211R,
    FEATURE_WIFI_TWT,
)
from .client.classes import (
    HuaweiRouterInfo,
    HuaweiClientDevice,
    HuaweiDeviceNode,
    NODE_HILINK_TYPE_DEVICE,
)

from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
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

_LOGGER = logging.getLogger(__name__)


class CoordinatorError(Exception):

    def __init__(self, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message

    def __str__(self, *args, **kwargs) -> str:
        """ Return str(self). """
        return self._message


# ---------------------------
#   RoutersWatcher
# ---------------------------
class RoutersWatcher:

    def __init__(self) -> None:
        """Initialize."""
        self._known_routers: dict[str, ConnectedDevice] = {}

    @staticmethod
    def _get_active_mesh_routers(coordinator: HuaweiControllerDataUpdateCoordinator) -> dict[str, ConnectedDevice]:
        result = {}
        for device in coordinator.connected_devices.values():
            if device.is_active and device.is_router:
                result[device.mac] = device
        return result

    def watch_for_changes(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            on_router_added: Callable[[str, ConnectedDevice], None],
            on_router_removed: Callable[[EntityRegistry, str, ConnectedDevice], None]
    ) -> None:
        """Checks the difference between previously known and current lists of routers."""
        actual_routers: dict[str, ConnectedDevice] = self._get_active_mesh_routers(coordinator)

        for device_id, router in actual_routers.items():
            if device_id in self._known_routers:
                continue
            self._known_routers[device_id] = router
            on_router_added(device_id, router)

        unavailable_routers = {}
        for device_id, existing_router in self._known_routers.items():
            if device_id not in actual_routers:
                unavailable_routers[device_id] = existing_router

        if unavailable_routers:
            er = entity_registry.async_get(coordinator.hass)
            for device_id, unavailable_router in unavailable_routers.items():
                self._known_routers.pop(device_id, None)
                on_router_removed(er, device_id, unavailable_router)


# ---------------------------
#   TagsMap
# ---------------------------
class TagsMap:

    def __init__(self, tags_map_storage: Store):
        """Initialize."""
        self._storage: Store = tags_map_storage
        self._mac_to_tags: dict[str, list[str]] = {}
        self._tag_to_macs: dict[str, list[str]] = {}
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Return true when tags are loaded."""
        return self._is_loaded

    async def load(self):
        """Load the tags from the storage."""
        _LOGGER.debug("Stored tags loading started")

        self._mac_to_tags.clear()
        self._tag_to_macs.clear()

        self._tag_to_macs = await self._storage.async_load()
        if not self._tag_to_macs:
            _LOGGER.debug("No stored tags found, creating sample")
            default_tags = {"homeowners": ["place_mac_addresses_here"], "visitors": ["place_mac_addresses_here"]}
            await self._storage.async_save(default_tags)
            self._tag_to_macs = default_tags

        for tag, devices_macs in self._tag_to_macs.items():
            for device_mac in devices_macs:
                if device_mac not in self._mac_to_tags:
                    self._mac_to_tags[device_mac] = []
                self._mac_to_tags[device_mac].append(tag)

        self._is_loaded = True

        _LOGGER.debug("Stored tags loading finished")

    def get_tags(self, mac_address: str) -> list[str]:
        """Return the tags of the device"""
        return self._mac_to_tags.get(mac_address, [])

    def get_all_tags(self) -> Iterable[str]:
        """Return all known tags."""
        return self._tag_to_macs.keys()

    def get_devices(self, tag: str) -> list[str]:
        """Return the devices having specified tag."""
        return self._tag_to_macs.get(tag, [])


# ---------------------------
#   HuaweiControllerDataUpdateCoordinator
# ---------------------------
class HuaweiControllerDataUpdateCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, tags_map_storage: Store) -> None:
        """Initialize HuaweiController."""
        self._tags_map: TagsMap = TagsMap(tags_map_storage)
        self._router_info: HuaweiRouterInfo | None = None
        self._switch_states: dict[str, bool] = {}
        self._connected_devices: dict[str, ConnectedDevice] = {}

        self._config: ConfigEntry = config_entry

        self._primary_api: HuaweiApi = HuaweiApi(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            use_ssl=config_entry.data[CONF_SSL],
            user=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            verify_ssl=config_entry.data[CONF_VERIFY_SSL],
        )

        self._routersWatcher: RoutersWatcher = RoutersWatcher()
        self._dependent_apis: dict[str, HuaweiApi] = {}

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
        """Return the host of the router."""
        return self.config_entry.data[CONF_HOST]

    @property
    def router_info(self) -> HuaweiRouterInfo | None:
        """Return the information of the router."""
        return self._router_info

    @property
    def connected_devices(self) -> dict[str, ConnectedDevice]:
        """Return the connected devices."""
        return self._connected_devices

    @property
    def configuration_url(self) -> str:
        """Return the router's configuration URL."""
        return self._primary_api.router_url

    @property
    def device_info(self) -> DeviceInfo:
        """Return the DeviceInfo."""
        return DeviceInfo(
            configuration_url=self.configuration_url,
            identifiers={(DOMAIN, self.router_info.serial_number)},
            manufacturer=ATTR_MANUFACTURER,
            model=self.router_info.model,
            name=self.name,
            hw_version=self.router_info.hardware_version,
            sw_version=self.router_info.software_version,
        )

    @property
    def tags_map(self) -> TagsMap:
        """Return the tags map."""
        return self._tags_map

    def _safe_disconnect(self, api: HuaweiApi) -> None:
        """Disconnect from API."""
        try:
            self.hass.async_add_job(api.disconnect)
        except Exception as ex:
            _LOGGER.warning("Can not schedule disconnect: %s", str(ex))

    async def async_update(self) -> None:
        """Asynchronous update of all data."""
        _LOGGER.debug("Update started")
        await self._update_router_data()
        await self._update_connected_devices()
        await self._update_dependent_apis()
        await self._update_switches()
        _LOGGER.debug("Update completed")

    async def _update_router_data(self) -> None:
        """Asynchronous update of router information."""
        _LOGGER.debug("Updating router data")
        self._router_info = await self._primary_api.get_router_info()
        _LOGGER.debug('Router data updated')

    def unload(self) -> None:
        """Unload the coordinator and disconnect from API."""
        self._safe_disconnect(self._primary_api)
        for router_api in self._dependent_apis.values():
            self._safe_disconnect(router_api)

    async def _update_dependent_apis(self) -> None:

        @callback
        def on_router_added(device_mac: str, router: ConnectedDevice) -> None:
            """When a new mesh router is detected."""
            if device_mac not in self._dependent_apis:
                _LOGGER.debug('New router %s discovered at %s', device_mac, router.ip_address)
                router_api = HuaweiApi(
                    host=router.ip_address,
                    port=80,
                    use_ssl=False,
                    user=self._config.data[CONF_USERNAME],
                    password=self._config.data[CONF_PASSWORD],
                    verify_ssl=False,
                )
                self._dependent_apis[device_mac] = router_api

        @callback
        def on_router_removed(_, device_mac: str, __) -> None:
            """When a known mesh router becomes unavailable."""
            _LOGGER.debug('Router %s disconnected', device_mac)
            router_api = self._dependent_apis.pop(device_mac, None)
            if router_api:
                self._safe_disconnect(router_api)

        self._routersWatcher.watch_for_changes(self, on_router_added, on_router_removed)

    async def _update_switches(self) -> None:
        """Asynchronous update of NFC switch state."""
        _LOGGER.debug('Updating switches states')


        
        if await self._primary_api.is_feature_available(FEATURE_WIFI_80211R):
            state = await self._primary_api.get_switch_state(SWITCH_WIFI_80211R)            
            self._switch_states[SWITCH_WIFI_80211R] = state
            _LOGGER.debug('80211r switch state updated to %s', state)

        if await self._primary_api.is_feature_available(FEATURE_WIFI_TWT):
            state = await self._primary_api.get_switch_state(SWITCH_WIFI_TWT)
            self._switch_states[SWITCH_WIFI_TWT] = state
            _LOGGER.debug('TWT switch state updated to %s', state)

        if await self._primary_api.is_feature_available(FEATURE_NFC):
            state = await self._primary_api.get_switch_state(SWITCH_NFC)
            self._switch_states[SWITCH_NFC] = state
            _LOGGER.debug('Nfc switch (primary router) state updated to %s', state)

            for mac, api in self._dependent_apis.items():
                device = self._connected_devices.get(mac)
                if device and device.is_active:
                    try:
                        state = await api.get_switch_state(SWITCH_NFC)
                        self._switch_states[f"{SWITCH_NFC}_{device.mac}"] = state
                        _LOGGER.debug('Nfc switch (%s) state updated to %s', device.name, state)
                    except Exception as ex:
                        _LOGGER.error("Can not get NFC switch state for device %s: %s", mac, str(ex))

    async def _update_connected_devices(self) -> None:
        """Asynchronous update of connected devices."""
        _LOGGER.debug('Updating connected devices')
        devices_data = await self._primary_api.get_known_devices()
        devices_topology = await self._primary_api.get_devices_topology()

        """recursively search all HiLink routers with connected devices"""

        def get_mesh_routers(devices: Iterable[HuaweiDeviceNode]) -> Iterable[HuaweiDeviceNode]:
            for candidate in devices:
                if candidate.hilink_type == NODE_HILINK_TYPE_DEVICE:
                    yield candidate
                for connected_router in get_mesh_routers(candidate.connected_devices):
                    yield connected_router

        mesh_routers = get_mesh_routers(devices_topology)

        # [MAC_ADDRESS_OF_DEVICE, { "name": PARENT_ROUTER_NAME, "id": PARENT_ROUTER_MAC}]
        devices_to_routers: dict[str, Any] = {}
        for mesh_router in mesh_routers:
            """find same device in devices_data by MAC address"""
            router = next(
                (
                    item for item in devices_data if item.mac_address == mesh_router.mac_address
                ),
                # if device information not found
                HuaweiClientDevice({"ActualName": mesh_router.mac_address, "MACAddress": mesh_router.mac_address})
            )
            """devices_to_routers[device_mac] = router_info """
            for mesh_connected_device in mesh_router.connected_devices:
                devices_to_routers[mesh_connected_device.mac_address] = {
                    "name": router.actual_name,
                    "id": router.mac_address
                }

        if not self._tags_map.is_loaded:
            await self._tags_map.load()

        for device_data in devices_data:
            mac: str = device_data.mac_address
            host_name: str = device_data.host_name or f'device_{mac}'
            name: str = device_data.actual_name or host_name
            is_active: bool = device_data.is_active
            tags = self._tags_map.get_tags(mac)

            if mac in self._connected_devices:
                device = self._connected_devices[mac]
            else:
                device = ConnectedDevice(name, host_name, mac, is_active, tags)
                self._connected_devices[device.mac] = device

            if is_active:
                """if nothing is found in the devices_to_routers, then the device is connected to the primary router"""
                connected_via = devices_to_routers.get(mac,
                                                       {
                                                           "name": self.name or 'Primary router',
                                                           "id": CONNECTED_VIA_ID_PRIMARY
                                                       })
                device.update_device_data(name, host_name, True, tags,
                                          connected_via=connected_via.get("name"),
                                          ip_address=device_data.ip_address,
                                          interface_type=device_data.interface_type,
                                          rssi=device_data.rssi,
                                          is_guest=device_data.is_guest,
                                          is_hilink=device_data.is_hilink,
                                          is_router=device_data.is_router,
                                          connected_via_id=connected_via.get("id")
                                          )
            else:
                device.update_device_data(name, host_name, False, tags)

        _LOGGER.debug('Connected devices updated')

    async def is_feature_available(self, feature: str) -> bool:
        """Return true if specified feature is known and available."""
        return await self._primary_api.is_feature_available(feature)

    def get_switch_state(self, switch_name: str, device_mac: str | None) -> bool:
        """Return the state of the specified switch."""
        key = switch_name if not device_mac else f'{switch_name}_{device_mac}'
        return self._switch_states.get(key, False)

    async def set_switch_state(self, switch_name: str, state: bool, device_mac: str | None) -> None:
        """Set state of the specified switch"""
        api = self._primary_api if device_mac is None else self._dependent_apis.get(device_mac)
        if not api:
            raise CoordinatorError(f"Can not find api for device {device_mac}")

        await api.set_switch_state(switch_name, state)
        key = switch_name if not device_mac else f'{switch_name}_{device_mac}'
        self._switch_states[key] = state
