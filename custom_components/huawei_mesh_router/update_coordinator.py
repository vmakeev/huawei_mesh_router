"""Huawei Controller for Huawei Router."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Callable, Final, Iterable, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .classes import DEVICE_TAG, ConnectedDevice, HuaweiWlanFilterMode
from .client.classes import (
    MAC_ADDR,
    NODE_HILINK_TYPE_DEVICE,
    FilterMode,
    HuaweiClientDevice,
    HuaweiConnectionInfo,
    HuaweiDeviceNode,
    HuaweiFilterInfo,
    HuaweiRouterInfo,
)
from .client.huaweiapi import (
    CONNECTED_VIA_ID_PRIMARY,
    FEATURE_NFC,
    FEATURE_WIFI_80211R,
    FEATURE_WIFI_TWT,
    FEATURE_WLAN_FILTER,
    SWITCH_NFC,
    SWITCH_WIFI_80211R,
    SWITCH_WIFI_TWT,
    SWITCH_WLAN_FILTER,
    HuaweiApi,
)
from .const import ATTR_MANUFACTURER, DOMAIN

_LOGGER = logging.getLogger(__name__)

_PRIMARY_ROUTER_IDENTITY: Final = "primary_router"

SELECT_WLAN_FILTER_MODE: Final = "wlan_filter_mode_select"


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
        self._known_routers: dict[MAC_ADDR, ConnectedDevice] = {}

    @staticmethod
    def _get_active_mesh_routers(coordinator: HuaweiControllerDataUpdateCoordinator) -> dict[MAC_ADDR, ConnectedDevice]:
        result = {}
        for device in coordinator.connected_devices.values():
            if device.is_active and device.is_router:
                result[device.mac] = device
        return result

    def _get_difference(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator
    ) -> Tuple[Iterable[Tuple[MAC_ADDR, ConnectedDevice]], Iterable[Tuple[EntityRegistry, MAC_ADDR, ConnectedDevice]]]:
        """Return the difference between previously known and current lists of routers."""
        actual_routers: dict[MAC_ADDR, ConnectedDevice] = self._get_active_mesh_routers(coordinator)

        added: list[Tuple[MAC_ADDR, ConnectedDevice]] = []
        removed: list[Tuple[EntityRegistry, MAC_ADDR, ConnectedDevice]] = []

        for device_mac, router in actual_routers.items():
            if device_mac in self._known_routers:
                continue
            self._known_routers[device_mac] = router
            added.append((device_mac, router))

        unavailable_routers = {}
        for device_mac, existing_router in self._known_routers.items():
            if device_mac not in actual_routers:
                unavailable_routers[device_mac] = existing_router

        if unavailable_routers:
            er = entity_registry.async_get(coordinator.hass)
            for device_mac, unavailable_router in unavailable_routers.items():
                self._known_routers.pop(device_mac, None)
                removed.append((er, device_mac, unavailable_router))

        return added, removed

    def look_for_changes(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            on_router_added: Callable[[MAC_ADDR, ConnectedDevice], None] | None = None,
            on_router_removed: Callable[[EntityRegistry, MAC_ADDR, ConnectedDevice], None] | None = None
    ) -> None:
        """Look for difference between previously known and current lists of routers."""
        added, removed = self._get_difference(coordinator)

        if on_router_added:
            for mac, router in added:
                on_router_added(mac, router)

        if on_router_removed:
            for er, mac, router in removed:
                on_router_removed(er, mac, router)


# ---------------------------
#   TagsMap
# ---------------------------
class TagsMap:

    def __init__(self, tags_map_storage: Store):
        """Initialize."""
        self._storage: Store = tags_map_storage
        self._mac_to_tags: dict[MAC_ADDR, list[DEVICE_TAG]] = {}
        self._tag_to_macs: dict[DEVICE_TAG, list[MAC_ADDR]] = {}
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

    def get_tags(self, mac_address: MAC_ADDR) -> list[DEVICE_TAG]:
        """Return the tags of the device"""
        return self._mac_to_tags.get(mac_address, [])

    def get_all_tags(self) -> Iterable[DEVICE_TAG]:
        """Return all known tags."""
        return self._tag_to_macs.keys()

    def get_devices(self, tag: DEVICE_TAG) -> list[MAC_ADDR]:
        """Return the devices having specified tag."""
        return self._tag_to_macs.get(tag, [])


# ---------------------------
#   HuaweiControllerDataUpdateCoordinator
# ---------------------------
class HuaweiControllerDataUpdateCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, tags_map_storage: Store) -> None:
        """Initialize HuaweiController."""
        self._tags_map: TagsMap = TagsMap(tags_map_storage)
        self._connected_devices: dict[MAC_ADDR, ConnectedDevice] = {}
        self._wan_info: HuaweiConnectionInfo | None = None

        self._config: ConfigEntry = config_entry
        self._routersWatcher: RoutersWatcher = RoutersWatcher()

        self._apis: dict[MAC_ADDR, HuaweiApi] = {
            _PRIMARY_ROUTER_IDENTITY: HuaweiApi(
                host=config_entry.data[CONF_HOST],
                port=config_entry.data[CONF_PORT],
                use_ssl=config_entry.data[CONF_SSL],
                user=config_entry.data[CONF_USERNAME],
                password=config_entry.data[CONF_PASSWORD],
                verify_ssl=config_entry.data[CONF_VERIFY_SSL],
            )
        }
        self._router_infos: dict[MAC_ADDR, HuaweiRouterInfo] = {}
        self._switch_states: dict[str, bool] = {}
        self._select_states: dict[str, str] = {}
        self._wlan_filter_info: HuaweiFilterInfo | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.data[CONF_NAME],
            update_method=self.async_update,
            update_interval=timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL]),
        )

    @property
    def primary_router_name(self) -> str:
        return "Primary router"

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
    def connected_devices(self) -> dict[MAC_ADDR, ConnectedDevice]:
        """Return the connected devices."""
        return self._connected_devices

    @property
    def tags_map(self) -> TagsMap:
        """Return the tags map."""
        return self._tags_map

    @property
    def primary_router_api(self) -> HuaweiApi:
        return self._select_api(None)

    def is_router_online(self, device_mac: MAC_ADDR | None = None) -> bool:
        return self._apis.get(device_mac or _PRIMARY_ROUTER_IDENTITY) is not None

    def get_router_info(self, device_mac: MAC_ADDR | None = None) -> HuaweiRouterInfo | None:
        """Return the information of the router."""
        return self._router_infos.get(device_mac or _PRIMARY_ROUTER_IDENTITY)

    def get_wan_info(self) -> HuaweiConnectionInfo | None:
        """Return the information of the router."""
        return self._wan_info

    def get_configuration_url(self, device_mac: MAC_ADDR | None = None) -> str:
        """Return the router's configuration URL."""
        return self._select_api(device_mac).router_url

    def get_device_info(self, device_mac: MAC_ADDR | None = None) -> DeviceInfo | None:
        """Return the DeviceInfo."""
        router_info = self.get_router_info(device_mac)
        if not router_info:
            _LOGGER.debug("Device info not found for %s", device_mac)
            return None

        device_name = self.primary_router_name

        # trying to find displayed name of the dependent router
        if device_mac is not None:
            connected_device = self._connected_devices.get(device_mac)
            if connected_device:
                device_name = connected_device.name
            else:
                device_name = device_mac

        result = DeviceInfo(
            configuration_url=self.get_configuration_url(device_mac),
            identifiers={(DOMAIN, router_info.serial_number)},
            manufacturer=ATTR_MANUFACTURER,
            model=router_info.model,
            name=device_name,
            hw_version=router_info.hardware_version,
            sw_version=router_info.software_version,
        )
        return result

    def _safe_disconnect(self, api: HuaweiApi) -> None:
        """Disconnect from API."""
        try:
            self.hass.async_add_job(api.disconnect)
        except Exception as ex:
            _LOGGER.warning("Can not schedule disconnect: %s", str(ex))

    async def async_update(self) -> None:
        """Asynchronous update of all data."""
        _LOGGER.debug("Update started")
        await self._update_apis()
        await self._update_router_infos()
        await self._update_wan_info()
        await self._update_wlan_filter_info()
        await self._update_connected_devices()
        await self._update_switches()
        await self._update_selects()
        _LOGGER.debug("Update completed")

    async def _update_wan_info(self) -> None:
        _LOGGER.debug("Updating wan info")
        try:
            self._wan_info = await self._select_api(_PRIMARY_ROUTER_IDENTITY).get_wan_connection_info()
        except Exception as ex:
            _LOGGER.error("Can not update wan info: %s", str(ex))
        _LOGGER.debug("Wan info updated")

    async def _update_wlan_filter_info(self) -> None:
        _LOGGER.debug("Updating wlan filter info")
        try:
            primary_api = self.primary_router_api
            if await primary_api.is_feature_available(FEATURE_WIFI_80211R):
                _, info_5g = await primary_api.get_wlan_filter_info()
                # ignore 2.4GHz information
                self._wlan_filter_info = info_5g
            else:
                self._wlan_filter_info = None
        except Exception as ex:
            _LOGGER.error("Can not update wlan filter info: %s", str(ex))
        _LOGGER.debug("Wlan filter info updated")

    async def _update_router_infos(self) -> None:
        """Asynchronous update of routers information."""
        _LOGGER.debug("Updating routers info")
        for (device_mac, api) in self._apis.items():
            try:
                self._router_infos[device_mac] = await api.get_router_info()
                _LOGGER.debug("Router info: updated for '%s'", device_mac)
            except Exception as ex:
                _LOGGER.error("Can not update router info for '%s': %s", device_mac, str(ex))
        _LOGGER.debug("Routers info updated")

    def unload(self) -> None:
        """Unload the coordinator and disconnect from API."""
        for router_api in self._apis.values():
            self._safe_disconnect(router_api)

    async def _update_apis(self) -> None:
        """Asynchronous update of available apis."""

        @callback
        def on_router_added(device_mac: MAC_ADDR, router: ConnectedDevice) -> None:
            """When a new mesh router is detected."""
            if device_mac not in self._apis:
                _LOGGER.debug("New router '%s' discovered at %s", device_mac, router.ip_address)
                router_api = HuaweiApi(
                    host=router.ip_address,
                    port=80,
                    use_ssl=False,
                    user=self._config.data[CONF_USERNAME],
                    password=self._config.data[CONF_PASSWORD],
                    verify_ssl=False,
                )
                self._apis[device_mac] = router_api

        @callback
        def on_router_removed(_, device_mac: MAC_ADDR, __) -> None:
            """When a known mesh router becomes unavailable."""
            _LOGGER.debug("Router '%s' disconnected", device_mac)
            router_api = self._apis.pop(device_mac, None)
            if router_api:
                self._safe_disconnect(router_api)

        self._routersWatcher.look_for_changes(self, on_router_added, on_router_removed)

    async def _update_selects(self) -> None:
        """Asynchronous update of selects states."""
        _LOGGER.debug("Updating selects states")

        primary_api = self._select_api(_PRIMARY_ROUTER_IDENTITY)

        new_states: dict[str, str] = {}

        if await primary_api.is_feature_available(FEATURE_WLAN_FILTER):
            mode = self._wlan_filter_info.mode if self._wlan_filter_info else None
            if mode is None:
                state = None
            elif mode == FilterMode.WHITELIST:
                state = HuaweiWlanFilterMode.WHITELIST
            elif mode == FilterMode.BLACKLIST:
                state = HuaweiWlanFilterMode.BLACKLIST
            else:
                _LOGGER.debug("Unsupported FilterMode %s", mode)
                state = None
            new_states[SELECT_WLAN_FILTER_MODE] = state
            _LOGGER.debug("WLan filter mode select state updated to %s", state)

        _LOGGER.debug("Selects states updated")
        self._select_states = new_states

    async def _update_switches(self) -> None:
        """Asynchronous update of switch states."""
        _LOGGER.debug("Updating switches states")

        primary_api = self._select_api(_PRIMARY_ROUTER_IDENTITY)

        new_states: dict[str, bool] = {}

        if await primary_api.is_feature_available(FEATURE_WIFI_80211R):
            state = await primary_api.get_switch_state(SWITCH_WIFI_80211R)
            new_states[SWITCH_WIFI_80211R] = state
            _LOGGER.debug("80211r switch state updated to %s", state)

        if await primary_api.is_feature_available(FEATURE_WIFI_TWT):
            state = await primary_api.get_switch_state(SWITCH_WIFI_TWT)
            new_states[SWITCH_WIFI_TWT] = state
            _LOGGER.debug("TWT switch state updated to %s", state)

        if await primary_api.is_feature_available(FEATURE_NFC):
            state = await primary_api.get_switch_state(SWITCH_NFC)
            new_states[SWITCH_NFC] = state
            _LOGGER.debug("Nfc switch (primary router) state updated to %s", state)

        if await primary_api.is_feature_available(FEATURE_WLAN_FILTER):
            state = await primary_api.get_switch_state(SWITCH_WLAN_FILTER)
            new_states[SWITCH_WLAN_FILTER] = state
            _LOGGER.debug("WLan filter switch state updated to %s", state)

        for mac, api in self._apis.items():
            device = self._connected_devices.get(mac)
            if device and device.is_active:
                try:
                    if await api.is_feature_available(FEATURE_NFC):
                        state = await api.get_switch_state(SWITCH_NFC)
                        new_states[f"{SWITCH_NFC}_{device.mac}"] = state
                        _LOGGER.debug("Nfc switch (%s) state updated to %s", device.name, state)
                except Exception as ex:
                    _LOGGER.error("Can not get NFC switch state for device %s: %s", mac, str(ex))

        self._switch_states = new_states

    async def _update_connected_devices(self) -> None:
        """Asynchronous update of connected devices."""
        _LOGGER.debug("Updating connected devices")
        primary_api = self._select_api(_PRIMARY_ROUTER_IDENTITY)
        devices_data = await primary_api.get_known_devices()
        devices_topology = await primary_api.get_devices_topology()

        # recursively search all HiLink routers with connected devices
        def get_mesh_routers(devices: Iterable[HuaweiDeviceNode]) -> Iterable[HuaweiDeviceNode]:
            for candidate in devices:
                if candidate.hilink_type == NODE_HILINK_TYPE_DEVICE:
                    yield candidate
                for connected_router in get_mesh_routers(candidate.connected_devices):
                    yield connected_router

        mesh_routers = get_mesh_routers(devices_topology)

        # [MAC_ADDRESS_OF_DEVICE, { "name": PARENT_ROUTER_NAME, "id": PARENT_ROUTER_MAC}]
        devices_to_routers: dict[MAC_ADDR, Any] = {}
        for mesh_router in mesh_routers:
            # find same device in devices_data by MAC address
            router = next(
                (
                    item for item in devices_data if item.mac_address == mesh_router.mac_address
                ),
                # if device information not found
                HuaweiClientDevice({"ActualName": mesh_router.mac_address, "MACAddress": mesh_router.mac_address})
            )
            # devices_to_routers[device_mac] = router_info
            for mesh_connected_device in mesh_router.connected_devices:
                devices_to_routers[mesh_connected_device.mac_address] = {
                    "name": router.actual_name,
                    "id": router.mac_address
                }

        # [MAC_ADDRESS_OF_DEVICE, Whitelist | Blacklist]
        devices_to_filters: dict[MAC_ADDR, HuaweiWlanFilterMode] = {}
        if self._wlan_filter_info:
            for blacklisted in self._wlan_filter_info.blacklist:
                devices_to_filters[blacklisted.mac_address] = HuaweiWlanFilterMode.BLACKLIST
            for whitelisted in self._wlan_filter_info.whitelist:
                devices_to_filters[whitelisted.mac_address] = HuaweiWlanFilterMode.WHITELIST

        if not self._tags_map.is_loaded:
            await self._tags_map.load()

        for device_data in devices_data:
            mac: MAC_ADDR = device_data.mac_address
            host_name: str = device_data.host_name or f'device_{mac}'
            name: str = device_data.actual_name or host_name
            is_active: bool = device_data.is_active
            tags = self._tags_map.get_tags(mac)
            filter_mode = devices_to_filters.get(mac)

            if mac in self._connected_devices:
                device = self._connected_devices[mac]
            else:
                device = ConnectedDevice(name, host_name, mac, is_active, tags, filter_mode)
                self._connected_devices[device.mac] = device

            if is_active:
                """if nothing is found in the devices_to_routers, then the device is connected to the primary router"""
                connected_via = devices_to_routers.get(mac,
                                                       {
                                                           "name": self.primary_router_name,
                                                           "id": CONNECTED_VIA_ID_PRIMARY
                                                       })
                device.update_device_data(name, host_name, True, tags, filter_mode,
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
                device.update_device_data(name, host_name, False, tags, filter_mode)

        _LOGGER.debug("Connected devices updated")

    def _select_api(self, device_mac: MAC_ADDR | None) -> HuaweiApi:
        """Return the api for the specified device."""
        api = self._apis.get(device_mac or _PRIMARY_ROUTER_IDENTITY)
        if not api:
            raise CoordinatorError(f"Can not find api for device '{device_mac}'")
        return api

    async def is_feature_available(self, feature: str, device_mac: MAC_ADDR | None = None) -> bool:
        """Return true if specified feature is known and available."""
        return await self._select_api(device_mac).is_feature_available(feature)

    def get_switch_state(self, switch_name: str, device_mac: MAC_ADDR | None = None) -> bool | None:
        """Return the state of the specified switch."""
        key = switch_name if not device_mac else f'{switch_name}_{device_mac}'
        return self._switch_states.get(key)

    async def set_switch_state(self, switch_name: str, state: bool, device_mac: MAC_ADDR | None = None) -> None:
        """Set state of the specified switch."""
        api = self._select_api(device_mac)

        await api.set_switch_state(switch_name, state)
        key = switch_name if not device_mac else f'{switch_name}_{device_mac}'
        self._switch_states[key] = state

    def get_select_state(self, select_name: str, device_mac: MAC_ADDR | None = None) -> str | None:
        """Return the state of the specified select."""
        key = select_name if not device_mac else f'{select_name}_{device_mac}'
        return self._select_states.get(key)

    async def set_select_state(self, select_name: str, state: str, device_mac: MAC_ADDR | None = None) -> None:
        """Set state of the specified select."""
        api = self._select_api(device_mac)

        if select_name == SELECT_WLAN_FILTER_MODE and await api.is_feature_available(FEATURE_WLAN_FILTER):
            if state == HuaweiWlanFilterMode.BLACKLIST:
                await api.set_wlan_filter_mode(FilterMode.BLACKLIST)
            elif state == HuaweiWlanFilterMode.WHITELIST:
                await api.set_wlan_filter_mode(FilterMode.WHITELIST)
            else:
                raise CoordinatorError(f"Unsupported HuaweiWlanFilterMode: {state}")
        else:
            raise CoordinatorError(f"Unsupported select name: {select_name}")

        key = select_name if not device_mac else f'{select_name}_{device_mac}'
        self._select_states[key] = state

    async def execute_action(self, action_name: str, device_mac: MAC_ADDR | None = None) -> None:
        """Perform the specified action."""
        api = self._select_api(device_mac)
        await api.execute_action(action_name)
