"""Huawei Controller for Huawei Router."""
from __future__ import annotations

from datetime import timedelta
from functools import wraps
import logging
from typing import Any, Callable, Final, Iterable, Tuple

from homeassistant.components.zone.const import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
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

from .classes import (
    DEVICE_TAG,
    ConnectedDevice,
    HuaweiInterfaceType,
    HuaweiWlanFilterMode,
    ZoneInfo,
)
from .client.classes import (
    MAC_ADDR,
    NODE_HILINK_TYPE_DEVICE,
    FilterAction,
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
from .options import HuaweiIntegrationOptions

_LOGGER = logging.getLogger(__name__)

_PRIMARY_ROUTER_IDENTITY: Final = "primary_router"

SELECT_WLAN_FILTER_MODE: Final = "wlan_filter_mode_select"
SELECT_ROUTER_ZONE: Final = "router_zone_select"
SWITCH_DEVICE_ACCESS: Final = "wlan_device_access_switch"


class CoordinatorError(Exception):
    def __init__(self, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message

    def __str__(self, *args, **kwargs) -> str:
        """Return str(self)."""
        return self._message


# ---------------------------
#   HuaweiConnectedDevicesWatcher
# ---------------------------
class HuaweiConnectedDevicesWatcher:
    def __init__(self, devices_predicate: Callable[[ConnectedDevice], bool]) -> None:
        """Initialize."""
        self._known_devices: dict[MAC_ADDR, ConnectedDevice] = {}
        self._devices_predicate = devices_predicate

    def _get_difference(
        self, coordinator: HuaweiDataUpdateCoordinator
    ) -> Tuple[
        Iterable[Tuple[MAC_ADDR, ConnectedDevice]],
        Iterable[Tuple[EntityRegistry, MAC_ADDR, ConnectedDevice]],
    ]:
        """Return the difference between previously known and current lists of devices."""
        actual_devices: dict[MAC_ADDR, ConnectedDevice] = {}
        for device in coordinator.connected_devices.values():
            if self._devices_predicate(device):
                actual_devices[device.mac] = device

        added: list[Tuple[MAC_ADDR, ConnectedDevice]] = []
        removed: list[Tuple[EntityRegistry, MAC_ADDR, ConnectedDevice]] = []

        for device_mac, device in actual_devices.items():
            if device_mac in self._known_devices:
                continue
            self._known_devices[device_mac] = device
            added.append((device_mac, device))

        unavailable_devices = {}
        for device_mac, existing_device in self._known_devices.items():
            if device_mac not in actual_devices:
                unavailable_devices[device_mac] = existing_device

        if unavailable_devices:
            er = entity_registry.async_get(coordinator.hass)
            for device_mac, unavailable_device in unavailable_devices.items():
                self._known_devices.pop(device_mac, None)
                removed.append((er, device_mac, unavailable_device))

        return added, removed

    def look_for_changes(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        on_added: Callable[[MAC_ADDR, ConnectedDevice], None] | None = None,
        on_removed: Callable[[EntityRegistry, MAC_ADDR, ConnectedDevice], None]
        | None = None,
    ) -> None:
        """Look for difference between previously known and current lists of routers."""
        added, removed = self._get_difference(coordinator)

        if on_added:
            for mac, device in added:
                on_added(mac, device)

        if on_removed:
            for er, mac, device in removed:
                on_removed(er, mac, device)


# ---------------------------
#   ActiveRoutersWatcher
# ---------------------------
class ActiveRoutersWatcher(HuaweiConnectedDevicesWatcher):
    @staticmethod
    def filter(device: ConnectedDevice) -> bool:
        return device.is_active and device.is_router

    def __init__(self) -> None:
        """Initialize."""
        super().__init__(ActiveRoutersWatcher.filter)


# ---------------------------
#   ClientWirelessDevicesWatcher
# ---------------------------
class ClientWirelessDevicesWatcher(HuaweiConnectedDevicesWatcher):
    @staticmethod
    def filter(device: ConnectedDevice) -> bool:
        if device.is_router:
            return False
        return device.interface_type != HuaweiInterfaceType.INTERFACE_LAN

    def __init__(self) -> None:
        """Initialize."""
        super().__init__(ClientWirelessDevicesWatcher.filter)


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
            default_tags = {
                "homeowners": ["place_mac_addresses_here"],
                "visitors": ["place_mac_addresses_here"],
            }
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
#   ZonesMap
# ---------------------------
class ZonesMap:
    def __init__(self, zones_map_storage: Store):
        """Initialize."""
        self._storage: Store = zones_map_storage
        self._devices_to_zones: dict[str, str] = {}
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Return true when zones are loaded."""
        return self._is_loaded

    async def load(self):
        """Load the zones from the storage."""
        _LOGGER.debug("Stored zones loading started")
        self._devices_to_zones.clear()
        self._devices_to_zones = await self._storage.async_load() or {}
        self._is_loaded = True
        _LOGGER.debug("Stored zones loading finished")

    def get_zone_id(self, device_id: str) -> str | None:
        """Return the zone id of the device"""
        return self._devices_to_zones.get(device_id)

    async def set_zone_id(self, device_id: str, zone_id: str | None) -> None:
        """Set the zone id to the device"""
        if not self.is_loaded:
            await self.load()

        self._devices_to_zones[device_id] = zone_id
        await self._storage.async_save(self._devices_to_zones)


# ---------------------------
#   suppress_exceptions_when_unloaded
# ---------------------------
def suppress_exceptions_when_unloaded(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        coordinator = args[0]
        try:
            return await func(*args, **kwargs)
        except Exception as ex:
            if not coordinator.is_unloaded:
                raise
            else:
                _LOGGER.debug(
                    "Exception suppressed, coordinator is unloaded: %s", repr(ex)
                )

    return wrapper


# ---------------------------
#   suppress_update_exception
# ---------------------------
def suppress_update_exception(error_template: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            coordinator = args[0]
            try:
                return await func(*args, **kwargs)
            except Exception as ex:
                if coordinator.is_unloaded:
                    _LOGGER.debug(error_template, repr(ex))
                else:
                    _LOGGER.warning(error_template, repr(ex))

        return wrapper

    return decorator


# ---------------------------
#   HuaweiControllerDataUpdateCoordinator
# ---------------------------
class HuaweiDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        integration_options: HuaweiIntegrationOptions,
        tags_map_storage: Store | None,
        zones_map_storage: Store | None,
    ) -> None:
        """Initialize HuaweiController."""
        self._is_unloaded = False
        self._integration_options = integration_options

        self._tags_map: TagsMap | None = (
            TagsMap(tags_map_storage)
            if self._integration_options.devices_tags and tags_map_storage
            else None
        )

        self._zones_map: ZonesMap | None = (
            ZonesMap(zones_map_storage)
            if self._integration_options.device_tracker_zones and zones_map_storage
            else None
        )

        self._connected_devices: dict[MAC_ADDR, ConnectedDevice] = {}
        self._wan_info: HuaweiConnectionInfo | None = None

        self._config: ConfigEntry = config_entry
        self._routersWatcher: ActiveRoutersWatcher = ActiveRoutersWatcher()

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
            update_interval=timedelta(
                seconds=self._integration_options.update_interval
            ),
        )

    @property
    def primary_router_name(self) -> str:
        return "Primary router"

    @property
    def is_unloaded(self) -> bool:
        return self._is_unloaded

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
        if self._integration_options.devices_tags:
            return self._tags_map
        else:
            raise CoordinatorError("Devices tags are disabled by integration options.")

    @property
    def zones_map(self) -> ZonesMap:
        """Return the zones map."""
        if self._integration_options.device_tracker_zones:
            return self._zones_map
        else:
            raise CoordinatorError(
                "Devices tracker zones are disabled by integration options."
            )

    @property
    def zones(self) -> Iterable[ZoneInfo]:
        return self._zones

    @property
    def primary_router_api(self) -> HuaweiApi:
        return self._select_api(None)

    def is_router_online(self, device_mac: MAC_ADDR | None = None) -> bool:
        return self._apis.get(device_mac or _PRIMARY_ROUTER_IDENTITY) is not None

    def get_router_info(
        self, device_mac: MAC_ADDR | None = None
    ) -> HuaweiRouterInfo | None:
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

    @suppress_exceptions_when_unloaded
    async def async_update(self) -> None:
        """Asynchronous update of all data."""
        _LOGGER.debug("Update started")
        await self._update_zones()
        await self._update_wlan_filter_info()
        await self._update_connected_devices()
        await self._update_apis()
        await self._update_router_infos()
        await self._update_wan_info()
        await self._update_switches()
        await self._update_selects()
        _LOGGER.debug("Update completed")

    @suppress_update_exception("Can not update zones %s")
    async def _update_zones(self) -> None:
        if not self._integration_options.device_tracker_zones:
            return
        _LOGGER.debug("Updating zones")

        if not self._zones_map.is_loaded:
            await self._zones_map.load()

        def get_zones() -> Iterable[ZoneInfo]:
            er = entity_registry.async_get(self.hass)
            for er_entity_id, er_entry in er.entities.items():
                if er_entry.domain == ZONE_DOMAIN:
                    yield ZoneInfo(
                        name=er_entry.name or er_entry.original_name,
                        entity_id=er_entity_id,
                    )

        self._zones = list(sorted(get_zones(), key=lambda zone: zone.name))

        _LOGGER.debug("Zones updated: %s", self._zones)

    @suppress_update_exception("Can not update wan info: %s")
    async def _update_wan_info(self) -> None:
        _LOGGER.debug("Updating wan info")
        self._wan_info = await self._select_api(
            _PRIMARY_ROUTER_IDENTITY
        ).get_wan_connection_info()
        _LOGGER.debug("Wan info updated")

    @suppress_update_exception("Can not update wlan filter info: %s")
    async def _update_wlan_filter_info(self) -> None:
        _LOGGER.debug("Updating wlan filter info")
        primary_api = self.primary_router_api
        if await primary_api.is_feature_available(FEATURE_WIFI_80211R):
            _, info_5g = await primary_api.get_wlan_filter_info()
            # ignore 2.4GHz information
            self._wlan_filter_info = info_5g
        else:
            self._wlan_filter_info = None
        _LOGGER.debug("Wlan filter info updated")

    @suppress_update_exception("Can not update router infos: %s")
    async def _update_router_infos(self) -> None:
        """Asynchronous update of routers information."""
        _LOGGER.debug("Updating routers info")
        for (device_mac, api) in self._apis.items():
            await self._update_router_info(device_mac, api)
        _LOGGER.debug("Routers info updated")

    @suppress_update_exception("Can not update router info: %s")
    async def _update_router_info(self, device_mac: MAC_ADDR, api: HuaweiApi) -> None:
        """Asynchronous update of router information."""
        _LOGGER.debug("Updating router %s info", device_mac)
        self._router_infos[device_mac] = await api.get_router_info()
        _LOGGER.debug("Router info: updated for '%s'", device_mac)

    def unload(self) -> None:
        """Unload the coordinator and disconnect from API."""
        self._is_unloaded = True
        _LOGGER.debug("Coordinator is unloaded")
        for router_api in self._apis.values():
            self._safe_disconnect(router_api)

    @suppress_update_exception("Can not update apis: %s")
    async def _update_apis(self) -> None:
        """Asynchronous update of available apis."""

        @callback
        def on_router_added(device_mac: MAC_ADDR, router: ConnectedDevice) -> None:
            """When a new mesh router is detected."""
            if device_mac not in self._apis:
                _LOGGER.debug(
                    "New router '%s' discovered at %s", device_mac, router.ip_address
                )
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

        _LOGGER.debug("Updating apis")
        self._routersWatcher.look_for_changes(self, on_router_added, on_router_removed)

    @suppress_update_exception("Can not update selects: %s")
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
                _LOGGER.warning("Unsupported FilterMode %s", mode)
                state = None
            new_states[SELECT_WLAN_FILTER_MODE] = state
            _LOGGER.debug("WLan filter mode select state updated to %s", state)

        if self._integration_options.device_tracker_zones:
            _LOGGER.debug("Updating Zone select for %s", _PRIMARY_ROUTER_IDENTITY)
            state = self._zones_map.get_zone_id(_PRIMARY_ROUTER_IDENTITY)
            new_states[f"{SELECT_ROUTER_ZONE}"] = state
            _LOGGER.debug(
                "Zone (%s) state updated to %s", _PRIMARY_ROUTER_IDENTITY, state
            )

            for mac, api in self._apis.items():
                if mac == _PRIMARY_ROUTER_IDENTITY:
                    continue
                device = self._connected_devices.get(mac)
                _LOGGER.debug(
                    "Updating Zone select for %s", device.name if device else mac
                )
                if device and device.is_active:
                    state = self._zones_map.get_zone_id(device.mac)
                else:
                    state = None
                new_states[f"{SELECT_ROUTER_ZONE}_{mac}"] = state
                _LOGGER.debug(
                    "Zone (%s) state updated to %s",
                    device.name if device else mac,
                    state,
                )

        _LOGGER.debug("Selects states updated")
        self._select_states = new_states

    @suppress_update_exception("Can not update switches: %s")
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
            if mac == _PRIMARY_ROUTER_IDENTITY:
                continue
            device = self._connected_devices.get(mac)
            if device and device.is_active:
                await self.update_router_nfc_switch(api, device, new_states)

        if self._integration_options.wifi_access_switches:
            await self.calculate_device_access_switch_states(new_states)

        self._switch_states = new_states
        _LOGGER.debug("Switches states updated")

    @suppress_update_exception("Can not update NFC switch state: %s")
    async def update_router_nfc_switch(self, api, device, new_states):
        if await api.is_feature_available(FEATURE_NFC):
            _LOGGER.debug("Updating nfc switch for %s", device.name)
            state = await api.get_switch_state(SWITCH_NFC)
            new_states[f"{SWITCH_NFC}_{device.mac}"] = state
            _LOGGER.debug("Nfc switch (%s) state updated to %s", device.name, state)

    async def calculate_device_access_switch_states(
        self, states: dict[str, bool] | None = None
    ) -> None:
        """Update device access switch states."""
        if not self._integration_options.wifi_access_switches:
            return

        states = states or self._switch_states
        primary_api = self._select_api(_PRIMARY_ROUTER_IDENTITY)

        if await primary_api.is_feature_available(FEATURE_WLAN_FILTER):
            for device in self.connected_devices.values():
                if not ClientWirelessDevicesWatcher.filter(device):
                    continue
                if not self._wlan_filter_info:
                    continue

                if self._wlan_filter_info.mode == FilterMode.WHITELIST:
                    state = device.filter_mode == HuaweiWlanFilterMode.WHITELIST
                elif self._wlan_filter_info.mode == FilterMode.BLACKLIST:
                    state = device.filter_mode != HuaweiWlanFilterMode.BLACKLIST
                else:
                    state = None

                states[f"{SWITCH_DEVICE_ACCESS}_{device.mac}"] = state
                _LOGGER.debug(
                    "Device access switch (%s) state updated to %s", device.name, state
                )

    @suppress_update_exception("Can not update connected devices: %s")
    async def _update_connected_devices(self) -> None:
        """Asynchronous update of connected devices."""
        _LOGGER.debug("Updating connected devices")
        primary_api = self._select_api(_PRIMARY_ROUTER_IDENTITY)
        devices_data = await primary_api.get_known_devices()
        devices_topology = await primary_api.get_devices_topology()

        # recursively search all HiLink routers with connected devices
        def get_mesh_routers(
            devices: Iterable[HuaweiDeviceNode],
        ) -> Iterable[HuaweiDeviceNode]:
            for candidate in devices:
                if candidate.hilink_type == NODE_HILINK_TYPE_DEVICE:
                    yield candidate
                for connected_router in get_mesh_routers(candidate.connected_devices):
                    yield connected_router

        mesh_routers = get_mesh_routers(devices_topology)

        # [MAC_ADDRESS_OF_DEVICE, { "name": PARENT_ROUTER_NAME, "id": PARENT_ROUTER_MAC, "zone": ROUTER_ZONE}]
        devices_to_routers: dict[MAC_ADDR, Any] = {}
        for mesh_router in mesh_routers:
            # find same device in devices_data by MAC address
            router = next(
                (
                    item
                    for item in devices_data
                    if item.mac_address == mesh_router.mac_address
                ),
                # if device information not found
                HuaweiClientDevice(
                    {
                        "ActualName": mesh_router.mac_address,
                        "MACAddress": mesh_router.mac_address,
                    }
                ),
            )
            # devices_to_routers[device_mac] = router_info
            for mesh_connected_device in mesh_router.connected_devices:
                devices_to_routers[mesh_connected_device.mac_address] = {
                    "name": router.actual_name,
                    "id": router.mac_address,
                }

        # [MAC_ADDRESS_OF_DEVICE, Whitelist | Blacklist]
        devices_to_filters: dict[MAC_ADDR, HuaweiWlanFilterMode] = {}
        if self._wlan_filter_info:
            for blacklisted in self._wlan_filter_info.blacklist:
                devices_to_filters[
                    blacklisted.mac_address
                ] = HuaweiWlanFilterMode.BLACKLIST
            for whitelisted in self._wlan_filter_info.whitelist:
                devices_to_filters[
                    whitelisted.mac_address
                ] = HuaweiWlanFilterMode.WHITELIST

        if self._integration_options.devices_tags and not self._tags_map.is_loaded:
            await self._tags_map.load()

        for device_data in devices_data:
            mac: MAC_ADDR = device_data.mac_address
            host_name: str = device_data.host_name or f"device_{mac}"
            name: str = device_data.actual_name or host_name
            is_active: bool = device_data.is_active
            filter_mode = devices_to_filters.get(mac)

            tags = (
                self._tags_map.get_tags(mac)
                if self._integration_options.devices_tags
                else []
            )

            if mac in self._connected_devices:
                device = self._connected_devices[mac]
            else:
                device = ConnectedDevice(
                    name, host_name, mac, is_active, tags, filter_mode
                )
                self._connected_devices[device.mac] = device

            if is_active:
                """if nothing is found in the devices_to_routers, then the device is connected to the primary router"""
                connected_via = devices_to_routers.get(
                    mac,
                    {"name": self.primary_router_name, "id": CONNECTED_VIA_ID_PRIMARY},
                )

                zone_id = None

                if self._integration_options.device_tracker_zones:
                    if device_data.is_router:
                        zone_id = self._zones_map.get_zone_id(mac)
                    elif connected_via.get("id") == CONNECTED_VIA_ID_PRIMARY:
                        zone_id = self._zones_map.get_zone_id(_PRIMARY_ROUTER_IDENTITY)
                    else:
                        zone_id = self._zones_map.get_zone_id(connected_via.get("id"))

                zone_name = (
                    next(
                        (
                            zone.name
                            for zone in self._zones
                            if zone.entity_id == zone_id
                        ),
                        None,
                    )
                    if zone_id
                    else None
                )

                device.update_device_data(
                    name,
                    host_name,
                    True,
                    tags,
                    filter_mode,
                    connected_via=connected_via.get("name"),
                    ip_address=device_data.ip_address,
                    interface_type=device_data.interface_type,
                    rssi=device_data.rssi,
                    is_guest=device_data.is_guest,
                    is_hilink=device_data.is_hilink,
                    is_router=device_data.is_router,
                    connected_via_id=connected_via.get("id"),
                    zone=ZoneInfo(name=zone_name, entity_id=zone_id)
                    if zone_id
                    else None,
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

    async def is_feature_available(
        self, feature: str, device_mac: MAC_ADDR | None = None
    ) -> bool:
        """Return true if specified feature is known and available."""
        return await self._select_api(device_mac).is_feature_available(feature)

    def get_switch_state(
        self, switch_name: str, device_mac: MAC_ADDR | None = None
    ) -> bool | None:
        """Return the state of the specified switch."""
        key = switch_name if not device_mac else f"{switch_name}_{device_mac}"
        return self._switch_states.get(key)

    async def set_switch_state(
        self, switch_name: str, state: bool, device_mac: MAC_ADDR | None = None
    ) -> None:
        """Set state of the specified switch."""

        key = switch_name if not device_mac else f"{switch_name}_{device_mac}"

        if switch_name == SWITCH_DEVICE_ACCESS:
            api = self._select_api(_PRIMARY_ROUTER_IDENTITY)
            # add to whitelist when ON, add to blacklist otherwise
            filter_mode = FilterMode.WHITELIST if state else FilterMode.BLACKLIST
            await api.apply_wlan_filter(filter_mode, FilterAction.ADD, device_mac)
        else:
            api = self._select_api(device_mac)
            await api.set_switch_state(switch_name, state)

        self._switch_states[key] = state

    def get_select_state(
        self, select_name: str, device_mac: MAC_ADDR | None = None
    ) -> str | None:
        """Return the state of the specified select."""
        key = select_name if not device_mac else f"{select_name}_{device_mac}"
        state = self._select_states.get(key)
        return state

    async def set_select_state(
        self, select_name: str, state: str, device_mac: MAC_ADDR | None = None
    ) -> None:
        """Set state of the specified select."""
        api = self._select_api(device_mac)

        # WLAN Filter Mode select
        if select_name == SELECT_WLAN_FILTER_MODE and await api.is_feature_available(
            FEATURE_WLAN_FILTER
        ):
            if state == HuaweiWlanFilterMode.BLACKLIST:
                await api.set_wlan_filter_mode(FilterMode.BLACKLIST)
            elif state == HuaweiWlanFilterMode.WHITELIST:
                await api.set_wlan_filter_mode(FilterMode.WHITELIST)
            else:
                raise CoordinatorError(f"Unsupported HuaweiWlanFilterMode: {state}")

        # Router's zone select
        elif select_name == SELECT_ROUTER_ZONE:
            await self._zones_map.set_zone_id(
                device_mac or _PRIMARY_ROUTER_IDENTITY, state
            )

        # Unknown select
        else:
            raise CoordinatorError(f"Unsupported select name: {select_name}")

        key = select_name if not device_mac else f"{select_name}_{device_mac}"
        self._select_states[key] = state

    async def execute_action(
        self, action_name: str, device_mac: MAC_ADDR | None = None
    ) -> None:
        """Perform the specified action."""
        api = self._select_api(device_mac)
        await api.execute_action(action_name)
