"""Huawei Controller for Huawei Router."""

from __future__ import annotations

from datetime import timedelta
from functools import wraps
import logging
from typing import Any, Callable, Final, Iterable

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
from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .classes import (
    ConnectedDevice,
    EmulatedSwitch,
    HuaweiEvents,
    HuaweiInterfaceType,
    HuaweiWlanFilterMode,
    PortMapping,
    Select,
    UrlFilter,
    ZoneInfo,
)
from .client.classes import (
    MAC_ADDR,
    NODE_HILINK_TYPE_DEVICE,
    Action,
    Feature,
    FilterAction,
    FilterMode,
    HuaweiClientDevice,
    HuaweiConnectionInfo,
    HuaweiDeviceNode,
    HuaweiFilterInfo,
    HuaweiRouterInfo,
    HuaweiTimeControlItem,
    HuaweiUrlFilterInfo,
    Switch,
)
from .client.const import CONNECTED_VIA_ID_PRIMARY
from .client.huaweiapi import HuaweiApi
from .const import ATTR_MANUFACTURER, DOMAIN
from .options import HuaweiIntegrationOptions
from .utils import (
    HuaweiChangesWatcher,
    TagsMap,
    ZonesMap,
    _TItem,
    _TKey,
    get_readable_rate,
)

_PRIMARY_ROUTER_IDENTITY: Final = "primary_router"


class CoordinatorError(Exception):
    def __init__(self, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message

    def __str__(self, *args, **kwargs) -> str:
        """Return str(self)."""
        return self._message


# ---------------------------
#   HuaweiUrlFiltersWatcher
# ---------------------------
class HuaweiUrlFiltersWatcher(HuaweiChangesWatcher[str, UrlFilter]):
    def _get_actual_items(self) -> Iterable[_TItem]:
        return self._coordinator.url_filters.values()

    def _get_key(self, item: _TItem) -> _TKey:
        return item.filter_id

    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        self._coordinator = coordinator
        super().__init__(lambda item: True)

    def look_for_changes(
        self,
        on_added: Callable[[str, UrlFilter], None] | None = None,
        on_removed: Callable[[EntityRegistry, str, UrlFilter], None] | None = None,
    ) -> None:
        """Look for difference between previously known and current lists of items."""
        added, removed = self._get_difference(self._coordinator.hass)

        if on_added:
            for key, item in added:
                on_added(key, item)

        if on_removed:
            for er, key, item in removed:
                on_removed(er, key, item)


# ---------------------------
#   HuaweiTimeControlItemsWatcher
# ---------------------------
class HuaweiTimeControlItemsWatcher(HuaweiChangesWatcher[str, HuaweiTimeControlItem]):
    def _get_actual_items(self) -> Iterable[_TItem]:
        return self._coordinator.time_control_items.values()

    def _get_key(self, item: _TItem) -> _TKey:
        return item.id

    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        self._coordinator = coordinator
        super().__init__(lambda item: True)

    def look_for_changes(
        self,
        on_added: Callable[[str, HuaweiTimeControlItem], None] | None = None,
        on_removed: (
            Callable[[EntityRegistry, str, HuaweiTimeControlItem], None] | None
        ) = None,
    ) -> None:
        """Look for difference between previously known and current lists of items."""
        added, removed = self._get_difference(self._coordinator.hass)

        if on_added:
            for key, item in added:
                on_added(key, item)

        if on_removed:
            for er, key, item in removed:
                on_removed(er, key, item)


# ---------------------------
#   HuaweiPortMappingsWatcher
# ---------------------------
class HuaweiPortMappingsWatcher(HuaweiChangesWatcher[str, PortMapping]):
    def _get_actual_items(self) -> Iterable[_TItem]:
        return self._coordinator.port_mappings.values()

    def _get_key(self, item: _TItem) -> _TKey:
        return item.id

    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        self._coordinator = coordinator
        super().__init__(lambda item: True)

    def look_for_changes(
        self,
        on_added: Callable[[str, PortMapping], None] | None = None,
        on_removed: Callable[[EntityRegistry, str, PortMapping], None] | None = None,
    ) -> None:
        """Look for difference between previously known and current lists of items."""
        added, removed = self._get_difference(self._coordinator.hass)

        if on_added:
            for key, item in added:
                on_added(key, item)

        if on_removed:
            for er, key, item in removed:
                on_removed(er, key, item)


# ---------------------------
#   HuaweiConnectedDevicesWatcher
# ---------------------------
class HuaweiConnectedDevicesWatcher(HuaweiChangesWatcher[MAC_ADDR, ConnectedDevice]):
    def _get_actual_items(self) -> Iterable[_TItem]:
        return self._coordinator.connected_devices.values()

    def _get_key(self, item: _TItem) -> _TKey:
        return item.mac

    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        devices_predicate: Callable[[ConnectedDevice], bool],
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        super().__init__(devices_predicate)

    def look_for_changes(
        self,
        on_added: Callable[[MAC_ADDR, ConnectedDevice], None] | None = None,
        on_removed: (
            Callable[[EntityRegistry, MAC_ADDR, ConnectedDevice], None] | None
        ) = None,
    ) -> None:
        """Look for difference between previously known and current lists of items."""
        added, removed = self._get_difference(self._coordinator.hass)

        if on_added:
            for key, item in added:
                on_added(key, item)

        if on_removed:
            for er, key, item in removed:
                on_removed(er, key, item)


# ---------------------------
#   ActiveRoutersWatcher
# ---------------------------
class ActiveRoutersWatcher(HuaweiConnectedDevicesWatcher):
    @staticmethod
    def filter(device: ConnectedDevice) -> bool:
        return device.is_active and device.is_router

    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, ActiveRoutersWatcher.filter)


# ---------------------------
#   ClientWirelessDevicesWatcher
# ---------------------------
class ClientWirelessDevicesWatcher(HuaweiConnectedDevicesWatcher):
    @staticmethod
    def filter(device: ConnectedDevice) -> bool:
        if device.is_router:
            return False
        return device.interface_type in [
            HuaweiInterfaceType.INTERFACE_2_4GHZ,
            HuaweiInterfaceType.INTERFACE_5GHZ,
        ]

    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, ClientWirelessDevicesWatcher.filter)


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
                coordinator._logger.debug(
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
                    coordinator._logger.debug(error_template, repr(ex))
                else:
                    coordinator._logger.warning(error_template, repr(ex))

        return wrapper

    return decorator


# ---------------------------
#   HuaweiDataUpdateCoordinator
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
        self._is_initial_update: bool = True
        self._logger = logging.getLogger(f"{__name__} ({config_entry.data[CONF_NAME]})")
        self._is_unloaded: bool = False
        self._is_repeater: bool = False
        self._integration_options: HuaweiIntegrationOptions = integration_options

        self._events: HuaweiEvents = HuaweiEvents(hass)

        self._tags_map: TagsMap | None = (
            TagsMap(tags_map_storage, self._logger)
            if self._integration_options.devices_tags and tags_map_storage
            else None
        )

        self._zones_map: ZonesMap | None = (
            ZonesMap(zones_map_storage, self._logger)
            if self._integration_options.device_tracker_zones and zones_map_storage
            else None
        )

        self._connected_devices: dict[MAC_ADDR, ConnectedDevice] = {}
        self._wan_info: HuaweiConnectionInfo | None = None

        self._config: ConfigEntry = config_entry
        self._routersWatcher: ActiveRoutersWatcher = ActiveRoutersWatcher(self)

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
        self._switch_states: dict[Switch | EmulatedSwitch | str, bool] = {}
        self._select_states: dict[Select | str, str] = {}
        self._wlan_filter_info: HuaweiFilterInfo | None = None
        self._url_filters: dict[str, UrlFilter] = {}
        self._time_control_items: dict[str, HuaweiTimeControlItem] = {}
        self._port_mappings: dict[str, PortMapping] = {}

        super().__init__(
            hass,
            self._logger,
            name=config_entry.data[CONF_NAME],
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self._integration_options.update_interval
            ),
        )

    @property
    def primary_router_name(self) -> str:
        return "Primary router" if not self._is_repeater else self.name

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
    def url_filters(self) -> dict[str, UrlFilter]:
        """Return the url filters."""
        return self._url_filters

    @property
    def time_control_items(self) -> dict[str, HuaweiTimeControlItem]:
        """Return the time control items."""
        return self._time_control_items

    @property
    def port_mappings(self) -> dict[str, PortMapping]:
        """Return the port mappings."""
        return self._port_mappings

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

    @property
    def primary_router_serial_number(self) -> str | None:
        info = self.get_router_info()
        return info.serial_number if info else None

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
            self._logger.debug("Device info not found for %s", device_mac)
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
            self.hass.async_create_task(api.disconnect())
        except Exception as ex:
            self._logger.warning("Can not schedule disconnect: %s", str(ex))

    @suppress_exceptions_when_unloaded
    async def async_update(self) -> None:
        """Asynchronous update of all data."""
        self._logger.debug("Update started")
        await self._update_repeater_state()
        await self._update_zones()
        await self._update_wlan_filter_info()
        await self._update_connected_devices()
        await self._update_apis()
        await self._update_router_infos()
        await self._update_wan_info()
        await self._update_url_filter_info()
        await self._update_port_mappings()
        await self._update_time_control()
        await self._update_switches()
        await self._update_selects()
        self._logger.debug("Update completed")
        self._is_initial_update = False

    @suppress_update_exception("Can not update time control items %s")
    async def _update_time_control(self) -> None:

        if not self._integration_options.time_control_switches:
            return

        if not await self.primary_router_api.is_feature_available(Feature.TIME_CONTROL):
            return

        self._logger.debug("Updating time control items")

        time_control_items: dict[str, HuaweiTimeControlItem] = {
            item.id: item
            for item in await self.primary_router_api.get_time_control_items()
        }

        missing_item_ids: list[str] = []
        for existing_item in self._time_control_items.values():
            updated_item = time_control_items.get(existing_item.id)
            if not updated_item:
                missing_item_ids.append(existing_item.id)
                continue

            existing_item.update(updated_item)

        if missing_item_ids:
            for missing_id in missing_item_ids:
                del self._time_control_items[missing_id]

        for updated_item in time_control_items.values():
            if updated_item.id not in self._time_control_items:
                self._time_control_items[updated_item.id] = updated_item

        self._logger.debug("Time control items updated")

    @suppress_update_exception("Can not update port mappings %s")
    async def _update_port_mappings(self) -> None:

        if not self._integration_options.port_mapping_switches:
            return

        if not await self.primary_router_api.is_feature_available(Feature.PORT_MAPPING):
            return

        self._logger.debug("Updating port mappings")

        new_port_mappings = {
            item.id: item for item in await self.primary_router_api.get_port_mappings()
        }

        missing_port_mapping_ids: list[str] = []
        for existing_port_mapping in self._port_mappings.values():
            updated_port_mapping = new_port_mappings.get(existing_port_mapping.id)
            if not updated_port_mapping:
                missing_port_mapping_ids.append(existing_port_mapping.id)
                continue

            existing_port_mapping.update_info(
                name=updated_port_mapping.name,
                enabled=updated_port_mapping.enabled,
                host_name=updated_port_mapping.host_name,
                host_ip=updated_port_mapping.host_ip,
                host_mac=updated_port_mapping.host_mac,
            )

        if missing_port_mapping_ids:
            for missing_id in missing_port_mapping_ids:
                del self._port_mappings[missing_id]

        for updated_port_mapping in new_port_mappings.values():
            if updated_port_mapping.id not in self._port_mappings:
                self._port_mappings[updated_port_mapping.id] = PortMapping(
                    updated_port_mapping.id,
                    updated_port_mapping.name,
                    updated_port_mapping.enabled,
                    updated_port_mapping.host_name,
                    updated_port_mapping.host_ip,
                    updated_port_mapping.host_mac,
                )

        self._logger.debug("Port mappings updated")

    @suppress_update_exception("Can not update repeater state %s")
    async def _update_repeater_state(self) -> None:
        self._logger.debug("Updating repeater state")
        self._is_repeater = await self.primary_router_api.get_is_repeater()
        self._logger.debug("Repeater state updated: %s", self._is_repeater)

    @suppress_update_exception("Can not update zones %s")
    async def _update_zones(self) -> None:
        if not self._integration_options.device_tracker_zones:
            return
        self._logger.debug("Updating zones")

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

        self._logger.debug("Zones updated")

    @suppress_update_exception("Can not update wan info: %s")
    async def _update_wan_info(self) -> None:
        self._logger.debug("Updating wan info")
        self._wan_info = await self.primary_router_api.get_wan_connection_info()
        self._logger.debug("Wan info updated")

    @suppress_update_exception("Can not update wlan filter info: %s")
    async def _update_wlan_filter_info(self) -> None:
        self._logger.debug("Updating wlan filter info")
        primary_api = self.primary_router_api
        if await primary_api.is_feature_available(Feature.WLAN_FILTER):
            _, info_5g = await primary_api.get_wlan_filter_info()
            # ignore 2.4GHz information
            self._wlan_filter_info = info_5g
        else:
            self._wlan_filter_info = None
        self._logger.debug("Wlan filter info updated")

    @suppress_update_exception("Can not update router infos: %s")
    async def _update_router_infos(self) -> None:
        """Asynchronous update of routers information."""
        self._logger.debug("Updating routers info")
        for device_mac, api in self._apis.items():
            await self._update_router_info(device_mac, api)
        self._logger.debug("Routers info updated")

    @suppress_update_exception("Can not update router info: %s")
    async def _update_router_info(self, device_mac: MAC_ADDR, api: HuaweiApi) -> None:
        """Asynchronous update of router information."""
        self._logger.debug("Updating router %s info", device_mac)
        self._router_infos[device_mac] = await api.get_router_info()
        self._logger.debug("Router info: updated for '%s'", device_mac)

    def unload(self) -> None:
        """Unload the coordinator and disconnect from API."""
        self._is_unloaded = True
        self._logger.debug("Coordinator is unloaded")
        for router_api in self._apis.values():
            self._safe_disconnect(router_api)

    @suppress_update_exception("Can not update apis: %s")
    async def _update_apis(self) -> None:
        """Asynchronous update of available apis."""

        @callback
        def on_router_added(device_mac: MAC_ADDR, router: ConnectedDevice) -> None:
            """When a new mesh router is detected."""
            if device_mac not in self._apis:
                self._logger.debug(
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

                if not self._is_initial_update:
                    self._events.fire_router_added(
                        self.primary_router_serial_number,
                        device_mac,
                        router.ip_address,
                        router.name,
                    )

        @callback
        def on_router_removed(_, device_mac: MAC_ADDR, router: ConnectedDevice) -> None:
            """When a known mesh router becomes unavailable."""
            self._logger.debug("Router '%s' disconnected", device_mac)
            router_api = self._apis.pop(device_mac, None)
            if router_api:
                self._safe_disconnect(router_api)

            if not self._is_initial_update:
                self._events.fire_router_removed(
                    self.primary_router_serial_number,
                    device_mac,
                    router.ip_address,
                    router.name,
                )

        self._logger.debug("Updating apis")
        self._routersWatcher.look_for_changes(on_router_added, on_router_removed)

    @suppress_update_exception("Can not update selects: %s")
    async def _update_selects(self) -> None:
        """Asynchronous update of selects states."""
        self._logger.debug("Updating selects states")

        new_states: dict[Select | str, str] = {}

        if await self.primary_router_api.is_feature_available(Feature.WLAN_FILTER):
            mode = self._wlan_filter_info.mode if self._wlan_filter_info else None
            if mode is None:
                state = None
            elif mode == FilterMode.WHITELIST:
                state = HuaweiWlanFilterMode.WHITELIST
            elif mode == FilterMode.BLACKLIST:
                state = HuaweiWlanFilterMode.BLACKLIST
            else:
                self._logger.warning("Unsupported FilterMode %s", mode)
                state = None
            new_states[Select.WLAN_FILTER_MODE] = state
            self._logger.debug("WLan filter mode select state updated to %s", state)

        if self._integration_options.device_tracker_zones:
            self._logger.debug("Updating Zone select for %s", _PRIMARY_ROUTER_IDENTITY)
            state = self._zones_map.get_zone_id(_PRIMARY_ROUTER_IDENTITY)
            new_states[Select.ROUTER_ZONE] = state
            self._logger.debug(
                "Zone (%s) state updated to %s", _PRIMARY_ROUTER_IDENTITY, state
            )

            for mac, api in self._apis.items():
                if mac == _PRIMARY_ROUTER_IDENTITY:
                    continue
                device = self._connected_devices.get(mac)
                self._logger.debug(
                    "Updating Zone select for %s", device.name if device else mac
                )
                if device and device.is_active:
                    state = self._zones_map.get_zone_id(device.mac)
                else:
                    state = None
                new_states[f"{Select.ROUTER_ZONE}_{mac}"] = state
                self._logger.debug(
                    "Zone (%s) state updated to %s",
                    device.name if device else mac,
                    state,
                )

        self._logger.debug("Selects states updated")
        self._select_states = new_states

    @suppress_update_exception("Can not update URL filters: %s")
    async def _update_url_filter_info(self) -> None:
        """Asynchronous update of URL filters."""
        self._logger.debug("Updating URL filters")

        primary_api = self.primary_router_api

        if not await primary_api.is_feature_available(Feature.URL_FILTER):
            return

        url_filter_infos: dict[str, HuaweiUrlFilterInfo] = {
            item.filter_id: item for item in await primary_api.get_url_filter_info()
        }

        missing_filter_ids: list[str] = []
        for existing_filter in self._url_filters.values():
            updated_filter_info = url_filter_infos.get(existing_filter.filter_id)
            if not updated_filter_info:
                missing_filter_ids.append(existing_filter.filter_id)
                continue

            existing_filter.update_info(
                url=updated_filter_info.url,
                dev_manual=updated_filter_info.dev_manual,
                enabled=updated_filter_info.enabled,
                devices=updated_filter_info.devices,
            )

        if missing_filter_ids:
            for missing_id in missing_filter_ids:
                del self._url_filters[missing_id]

        for updated_filter_info in url_filter_infos.values():
            if updated_filter_info.filter_id not in self._url_filters:
                self._url_filters[updated_filter_info.filter_id] = UrlFilter(
                    updated_filter_info.filter_id,
                    updated_filter_info.url,
                    updated_filter_info.enabled,
                    updated_filter_info.dev_manual,
                    updated_filter_info.devices,
                )

        self._logger.debug("URL filters updated")

    @suppress_update_exception("Can not update switches: %s")
    async def _update_switches(self) -> None:
        """Asynchronous update of switch states."""
        self._logger.debug("Updating switches states")

        primary_api = self._select_api(_PRIMARY_ROUTER_IDENTITY)

        new_states: dict[Switch | EmulatedSwitch | str, bool] = {}

        if await primary_api.is_feature_available(Feature.WIFI_80211R):
            state = await primary_api.get_switch_state(Switch.WIFI_80211R)
            new_states[Switch.WIFI_80211R] = state
            self._logger.debug("80211r switch state updated to %s", state)

        if await primary_api.is_feature_available(Feature.WIFI_TWT):
            state = await primary_api.get_switch_state(Switch.WIFI_TWT)
            new_states[Switch.WIFI_TWT] = state
            self._logger.debug("TWT switch state updated to %s", state)

        if await primary_api.is_feature_available(Feature.NFC):
            state = await primary_api.get_switch_state(Switch.NFC)
            new_states[Switch.NFC] = state
            self._logger.debug("Nfc switch (primary router) state updated to %s", state)

        if await primary_api.is_feature_available(Feature.WLAN_FILTER):
            state = await primary_api.get_switch_state(Switch.WLAN_FILTER)
            new_states[Switch.WLAN_FILTER] = state
            self._logger.debug("WLan filter switch state updated to %s", state)

        if await primary_api.is_feature_available(Feature.GUEST_NETWORK):
            state = await primary_api.get_switch_state(Switch.GUEST_NETWORK)
            new_states[Switch.GUEST_NETWORK] = state
            self._logger.debug("Guest network switch state updated to %s", state)

        for mac, api in self._apis.items():
            if mac == _PRIMARY_ROUTER_IDENTITY:
                continue
            device = self._connected_devices.get(mac)
            if device and device.is_active:
                await self.update_router_nfc_switch(api, device, new_states)

        await self.calculate_device_access_switch_states(new_states)
        await self.calculate_url_filter_switch_states(new_states)
        await self.calculate_port_mapping_switches(new_states)
        await self.calculate_time_control_switch_states(new_states)

        self._switch_states = new_states
        self._logger.debug("Switches states updated")

    @suppress_update_exception("Can not update NFC switch state: %s")
    async def update_router_nfc_switch(
        self,
        api: HuaweiApi,
        device: ConnectedDevice,
        new_states: dict[Switch | str, bool],
    ):
        if await api.is_feature_available(Feature.NFC):
            self._logger.debug("Updating nfc switch for %s", device.name)
            state = await api.get_switch_state(Switch.NFC)
            new_states[f"{Switch.NFC}_{device.mac}"] = state
            self._logger.debug(
                "Nfc switch (%s) state updated to %s", device.name, state
            )

    async def calculate_device_access_switch_states(
        self, states: dict[Switch | EmulatedSwitch | str, bool] | None = None
    ) -> None:
        """Update device access switch states."""
        if not self._integration_options.wifi_access_switches:
            return

        states = states or self._switch_states

        if await self.primary_router_api.is_feature_available(Feature.WLAN_FILTER):
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

                states[f"{EmulatedSwitch.DEVICE_ACCESS}_{device.mac}"] = state
                self._logger.debug(
                    "Device access switch (%s) state updated to %s", device.name, state
                )

    async def calculate_url_filter_switch_states(
        self, states: dict[Switch | EmulatedSwitch | str, bool] | None = None
    ) -> None:
        """Update url filter switch states."""
        if not self._integration_options.url_filter_switches:
            return

        states = states or self._switch_states

        if await self.primary_router_api.is_feature_available(Feature.URL_FILTER):
            for item in self._url_filters.values():
                states[f"{EmulatedSwitch.URL_FILTER}_{item.filter_id}"] = item.enabled
                self._logger.debug(
                    "URL filter switch (%s) state updated to %s",
                    item.filter_id,
                    item.enabled,
                )

    async def calculate_time_control_switch_states(
        self, states: dict[Switch | EmulatedSwitch | str, bool] | None = None
    ) -> None:
        """Update time control switch states."""
        if not self._integration_options.time_control_switches:
            return

        states = states or self._switch_states

        if await self.primary_router_api.is_feature_available(Feature.TIME_CONTROL):
            for item in self._time_control_items.values():
                states[f"{EmulatedSwitch.TIME_CONTROL}_{item.id}"] = item.enabled
                self._logger.debug(
                    "Time control switch (%s) state updated to %s",
                    item.id,
                    item.enabled,
                )

    async def calculate_port_mapping_switches(
        self, states: dict[Switch | EmulatedSwitch | str, bool] | None = None
    ) -> None:
        """Update url filter switch states."""
        if not self._integration_options.port_mapping_switches:
            return

        states = states or self._switch_states

        if await self.primary_router_api.is_feature_available(Feature.PORT_MAPPING):
            for item in self._port_mappings.values():
                states[f"{EmulatedSwitch.PORT_MAPPING}_{item.id}"] = item.enabled
                self._logger.debug(
                    "Port mapping switch (%s) state updated to %s",
                    item.id,
                    item.enabled,
                )

    @suppress_update_exception("Can not update connected devices: %s")
    async def _update_connected_devices(self) -> None:
        """Asynchronous update of connected devices."""
        self._logger.debug("Updating connected devices")
        primary_api = self.primary_router_api

        devices_data = await primary_api.get_known_devices()

        if await primary_api.is_feature_available(Feature.DEVICE_TOPOLOGY):
            devices_topology = await primary_api.get_devices_topology()
        else:
            devices_topology = []

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
                devices_to_filters[blacklisted.mac_address] = (
                    HuaweiWlanFilterMode.BLACKLIST
                )
            for whitelisted in self._wlan_filter_info.whitelist:
                devices_to_filters[whitelisted.mac_address] = (
                    HuaweiWlanFilterMode.WHITELIST
                )

        if self._integration_options.devices_tags and not self._tags_map.is_loaded:
            await self._tags_map.load()

        for device_data in devices_data:
            mac: MAC_ADDR = device_data.mac_address
            ip_address: str = device_data.ip_address
            host_name: str = device_data.host_name or f"device_{mac}"
            name: str = device_data.actual_name or host_name
            is_active: bool = device_data.is_active
            filter_mode: HuaweiWlanFilterMode = devices_to_filters.get(mac)
            interface_type: HuaweiInterfaceType = device_data.interface_type

            # if nothing is found in the devices_to_routers, then the device is connected to the primary router
            connected_via = devices_to_routers.get(
                mac,
                {"name": self.primary_router_name, "id": CONNECTED_VIA_ID_PRIMARY},
            )

            tags = (
                self._tags_map.get_tags(mac)
                if self._integration_options.devices_tags
                else []
            )

            if mac in self._connected_devices:
                device = self._connected_devices[mac]
            else:
                device = ConnectedDevice(
                    name,
                    host_name,
                    mac,
                    is_active,
                    tags,
                    filter_mode,
                    interface_type=interface_type,
                    is_router=device_data.is_router,
                )
                self._connected_devices[device.mac] = device
                # new device = fire an event immediately
                if not self._is_initial_update:
                    self._events.fire_device_connected(
                        self.primary_router_serial_number,
                        mac,
                        ip_address,
                        name,
                        connected_via.get("id"),
                        connected_via.get("name"),
                    )

            # if state of the device is changed then firing an event
            if not self._is_initial_update and device.is_active != is_active:
                if is_active:
                    self._events.fire_device_connected(
                        self.primary_router_serial_number,
                        mac,
                        ip_address,
                        name,
                        connected_via.get("id"),
                        connected_via.get("name"),
                    )
                else:
                    self._events.fire_device_disconnected(
                        self.primary_router_serial_number,
                        mac,
                        ip_address,
                        name,
                        device.connected_via_id,
                        device.connected_via_name,
                    )

            if is_active:

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

                if not self._is_initial_update:
                    if (
                        device.connected_via_id
                        and device.connected_via_id != connected_via.get("id")
                    ):
                        self._events.fire_device_changed_router(
                            self.primary_router_serial_number,
                            mac,
                            ip_address,
                            name,
                            device.connected_via_id,
                            device.connected_via_name,
                            connected_via.get("id"),
                            connected_via.get("name"),
                        )

                device.update_device_data(
                    name,
                    host_name,
                    True,
                    tags,
                    filter_mode,
                    connected_via=connected_via.get("name"),
                    ip_address=ip_address,
                    interface_type=interface_type,
                    rssi=device_data.rssi,
                    is_guest=device_data.is_guest,
                    is_hilink=device_data.is_hilink,
                    is_router=device_data.is_router,
                    connected_via_id=connected_via.get("id"),
                    zone=(
                        ZoneInfo(name=zone_name, entity_id=zone_id) if zone_id else None
                    ),
                    upload_rate_kilobytes_s=device_data.upload_rate,
                    download_rate_kilobytes_s=device_data.download_rate,
                    upload_rate=get_readable_rate(device_data.upload_rate),
                    download_rate=get_readable_rate(device_data.download_rate),
                )
            else:
                device.update_device_data(
                    name,
                    host_name,
                    False,
                    tags,
                    filter_mode,
                    ip_address=ip_address,
                    interface_type=interface_type,
                    is_guest=device_data.is_guest,
                    is_hilink=device_data.is_hilink,
                    is_router=device_data.is_router,
                )

        self._logger.debug("Connected devices updated")

    def _select_api(self, device_mac: MAC_ADDR | None) -> HuaweiApi:
        """Return the api for the specified device."""
        api = self._apis.get(device_mac or _PRIMARY_ROUTER_IDENTITY)
        if not api:
            raise CoordinatorError(
                f"Can not find api for device '{device_mac or _PRIMARY_ROUTER_IDENTITY}'"
            )
        return api

    async def is_feature_available(
        self, feature: Feature, device_mac: MAC_ADDR | None = None
    ) -> bool:
        """Return true if specified feature is known and available."""
        return await self._select_api(device_mac).is_feature_available(feature)

    def get_switch_state(
        self,
        switch_name: Switch | EmulatedSwitch,
        device_mac: MAC_ADDR | None = None,
        switch_id: str | None = None,
    ) -> bool | None:
        """Return the state of the specified switch."""
        key = switch_name
        if switch_id:
            key = f"{key}_{switch_id}"
        if device_mac:
            key = f"{key}_{device_mac}"
        return self._switch_states.get(key)

    async def set_switch_state(
        self,
        switch: Switch | EmulatedSwitch,
        state: bool,
        device_mac: MAC_ADDR | None = None,
        switch_id: str | None = None,
    ) -> None:
        """Set state of the specified switch."""

        key = switch
        if switch_id:
            key = f"{key}_{switch_id}"
        if device_mac:
            key = f"{key}_{device_mac}"

        # Device access switch processing
        if switch == EmulatedSwitch.DEVICE_ACCESS:
            # add to whitelist when ON, add to blacklist otherwise
            filter_mode = FilterMode.WHITELIST if state else FilterMode.BLACKLIST
            await self.primary_router_api.apply_wlan_filter(
                filter_mode, FilterAction.ADD, device_mac
            )

        # URL filter switch processing
        elif switch == EmulatedSwitch.URL_FILTER:
            if not switch_id:
                raise CoordinatorError(
                    f"Can not set value: switch_id is required for {EmulatedSwitch.URL_FILTER}"
                )
            filter_item = self._url_filters.get(switch_id)
            if filter_item.enabled == state:
                return
            filter_item.set_enabled(state)

            filter_info = HuaweiUrlFilterInfo(
                filter_id=filter_item.filter_id,
                url=filter_item.url,
                enabled=filter_item.enabled,
                dev_manual=filter_item.dev_manual,
                devices=list(filter_item.devices),
            )

            await self.primary_router_api.apply_url_filter_info(filter_info)

        # Port mapping switch processing
        elif switch == EmulatedSwitch.PORT_MAPPING:
            if not switch_id:
                raise CoordinatorError(
                    f"Can not set value: switch_id is required for {EmulatedSwitch.PORT_MAPPING}"
                )
            port_mapping = self._port_mappings.get(switch_id)
            if port_mapping.enabled == state:
                return

            port_mapping.set_enabled(state)

            await self.primary_router_api.set_port_mapping_state(
                port_mapping.id, port_mapping.enabled
            )

        # Time control switch processing
        elif switch == EmulatedSwitch.TIME_CONTROL:
            if not switch_id:
                raise CoordinatorError(
                    f"Can not set value: switch_id is required for {EmulatedSwitch.TIME_CONTROL}"
                )
            time_control = self._time_control_items.get(switch_id)
            if time_control.enabled == state:
                return

            time_control.set_enabled(state)

            await self.primary_router_api.set_time_control_item_state(
                time_control.id, time_control.enabled
            )

        # other switches
        else:
            api = self._select_api(device_mac)
            await api.set_switch_state(switch, state)

        self._switch_states[key] = state

    def get_select_state(
        self, select: Select, device_mac: MAC_ADDR | None = None
    ) -> str | None:
        """Return the state of the specified select."""
        key = select if not device_mac else f"{select}_{device_mac}"
        state = self._select_states.get(key)
        return state

    async def set_select_state(
        self, select: Select, state: str, device_mac: MAC_ADDR | None = None
    ) -> None:
        """Set state of the specified select."""
        api = self._select_api(device_mac)

        # WLAN Filter Mode select
        if select == Select.WLAN_FILTER_MODE and await api.is_feature_available(
            Feature.WLAN_FILTER
        ):
            if state == HuaweiWlanFilterMode.BLACKLIST:
                await api.set_wlan_filter_mode(FilterMode.BLACKLIST)
            elif state == HuaweiWlanFilterMode.WHITELIST:
                await api.set_wlan_filter_mode(FilterMode.WHITELIST)
            else:
                raise CoordinatorError(f"Unsupported HuaweiWlanFilterMode: {state}")

        # Router's zone select
        elif select == Select.ROUTER_ZONE:
            await self._zones_map.set_zone_id(
                device_mac or _PRIMARY_ROUTER_IDENTITY, state
            )

        # Unknown select
        else:
            raise CoordinatorError(f"Unsupported select: {select}")

        key = select if not device_mac else f"{select}_{device_mac}"
        self._select_states[key] = state

    async def execute_action(
        self, action: Action, device_mac: MAC_ADDR | None = None
    ) -> None:
        """Perform the specified action."""
        api = self._select_api(device_mac)
        await api.execute_action(action)

    # ---------------------------
    #   async_subscribe_event
    # ---------------------------
    @callback
    def async_subscribe_event(
        self, event_types: list[str], handle_callback: CALLBACK_TYPE
    ) -> Callable[[], None]:
        return self._events.async_subscribe_event(event_types, handle_callback)
