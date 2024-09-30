"""Huawei router switches."""

from __future__ import annotations

from abc import ABC
import asyncio
import logging
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .classes import ConnectedDevice, EmulatedSwitch
from .client.classes import MAC_ADDR, Feature, Switch, HuaweiTimeControlItem
from .const import DOMAIN
from .helpers import (
    generate_entity_id,
    generate_entity_name,
    generate_entity_unique_id,
    get_coordinator,
)
from .options import HuaweiIntegrationOptions
from .update_coordinator import (
    ActiveRoutersWatcher,
    ClientWirelessDevicesWatcher,
    HuaweiDataUpdateCoordinator,
    HuaweiPortMappingsWatcher,
    HuaweiTimeControlItemsWatcher,
    HuaweiUrlFiltersWatcher,
    PortMapping,
    UrlFilter,
)

_LOGGER = logging.getLogger(__name__)

_FUNCTION_DISPLAYED_NAME_NFC: Final = "NFC"
_FUNCTION_UID_NFC: Final = "switch_nfc"

_FUNCTION_DISPLAYED_NAME_WIFI_802_11_R: Final = "WiFi 802.11r"
_FUNCTION_UID_WIFI_802_11_R: Final = "switch_wifi_802_11_r"

_FUNCTION_DISPLAYED_NAME_WIFI_TWT: Final = "WiFi 6 TWT"
_FUNCTION_ID_WIFI_TWT: Final = "switch_wifi_twt"

_FUNCTION_DISPLAYED_NAME_WLAN_FILTER: Final = "WiFi Access Control"
_FUNCTION_ID_WLAN_FILTER: Final = "switch_wifi_access_control"

_FUNCTION_DISPLAYED_NAME_DEVICE_ACCESS: Final = "Device WiFi Access"
_FUNCTION_ID_DEVICE_ACCESS: Final = "switch_device_access"

_FUNCTION_DISPLAYED_NAME_URL_FILTER: Final = "URL filter"
_FUNCTION_ID_URL_FILTER: Final = "switch_url_filter"

_FUNCTION_DISPLAYED_NAME_PORT_MAPPING: Final = "Port mapping"
_FUNCTION_ID_PORT_MAPPING: Final = "switch_port_mapping"

_FUNCTION_DISPLAYED_NAME_GUEST_NETWORK: Final = "Guest network"
_FUNCTION_ID_GUEST_NETWORK: Final = "switch_guest_network"

_FUNCTION_DISPLAYED_NAME_TIME_CONTROL: Final = "Time control"
_FUNCTION_ID_TIME_CONTROL: Final = "switch_time_control"

ENTITY_DOMAIN: Final = "switch"


# ---------------------------
#   _add_nfc_if_available
# ---------------------------
async def _add_nfc_if_available(
    coordinator: HuaweiDataUpdateCoordinator,
    known_nfc_switches: dict[MAC_ADDR, HuaweiSwitch],
    mac: MAC_ADDR,
    router: ConnectedDevice,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if await coordinator.is_feature_available(Feature.NFC, mac):
        if not known_nfc_switches.get(mac):
            entity = HuaweiNfcSwitch(coordinator, router)
            async_add_entities([entity])
            known_nfc_switches[mac] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported at %s", Feature.NFC, mac)


# ---------------------------
#   _add_access_switch_if_available
# ---------------------------
async def _add_access_switch_if_available(
    coordinator: HuaweiDataUpdateCoordinator,
    known_access_switches: dict[MAC_ADDR, HuaweiSwitch],
    mac: MAC_ADDR,
    device: ConnectedDevice,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if await coordinator.is_feature_available(Feature.WLAN_FILTER):
        if not known_access_switches.get(mac):
            entity = HuaweiDeviceAccessSwitch(coordinator, device)
            async_add_entities([entity])
            known_access_switches[mac] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.WLAN_FILTER)


# ---------------------------
#   _add_time_control_switch_if_available
# ---------------------------
async def _add_time_control_switch_if_available(
    coordinator: HuaweiDataUpdateCoordinator,
    known_time_control_switches: dict[MAC_ADDR, HuaweiSwitch],
    time_control: HuaweiTimeControlItem,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if await coordinator.is_feature_available(Feature.TIME_CONTROL):
        if not known_time_control_switches.get(time_control.id):
            entity = HuaweiTimeControlSwitch(coordinator, time_control)
            async_add_entities([entity])
            known_time_control_switches[time_control.id] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.TIME_CONTROL)


# ---------------------------
#   _add_url_filter_switch_if_available
# ---------------------------
async def _add_url_filter_switch_if_available(
    coordinator: HuaweiDataUpdateCoordinator,
    known_url_filter_switches: dict[str, HuaweiSwitch],
    url_filter: UrlFilter,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if await coordinator.is_feature_available(Feature.URL_FILTER):
        if not known_url_filter_switches.get(url_filter.filter_id):
            entity = HuaweiUrlFilterSwitch(coordinator, url_filter)
            async_add_entities([entity])
            known_url_filter_switches[url_filter.filter_id] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.URL_FILTER)


# ---------------------------
#   _add_port_mapping_switch_if_available
# ---------------------------
async def _add_port_mapping_switch_if_available(
    coordinator: HuaweiDataUpdateCoordinator,
    known_port_mapping_switches: dict[str, HuaweiSwitch],
    port_mapping: PortMapping,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if await coordinator.is_feature_available(Feature.PORT_MAPPING):
        if not known_port_mapping_switches.get(port_mapping.id):
            entity = HuaweiPortMappingSwitch(coordinator, port_mapping)
            async_add_entities([entity])
            known_port_mapping_switches[port_mapping.id] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.PORT_MAPPING)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for Huawei Router component."""
    coordinator = get_coordinator(hass, config_entry)

    switches: list[HuaweiSwitch] = []

    is_nfc_available: bool = await coordinator.is_feature_available(Feature.NFC)

    if is_nfc_available:
        switches.append(HuaweiNfcSwitch(coordinator, None))
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.NFC)

    if await coordinator.is_feature_available(Feature.WIFI_80211R):
        switches.append(HuaweiWifi80211RSwitch(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.WIFI_80211R)

    if await coordinator.is_feature_available(Feature.WIFI_TWT):
        switches.append(HuaweiWifiTWTSwitch(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.WIFI_TWT)

    if await coordinator.is_feature_available(Feature.WLAN_FILTER):
        switches.append(HuaweiWlanFilterSwitch(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.WLAN_FILTER)

    if await coordinator.is_feature_available(Feature.GUEST_NETWORK):
        switches.append(HuaweiGuestNetworkSwitch(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.GUEST_NETWORK)

    async_add_entities(switches)

    watch_for_additional_routers(coordinator, config_entry, async_add_entities)
    watch_for_wireless_devices(coordinator, config_entry, async_add_entities)
    watch_for_url_filters(coordinator, config_entry, async_add_entities)
    watch_for_port_mappings(coordinator, config_entry, async_add_entities)
    watch_for_time_control_items(coordinator, config_entry, async_add_entities)


# ---------------------------
#   watch_for_additional_routers
# ---------------------------
def watch_for_additional_routers(
    coordinator: HuaweiDataUpdateCoordinator,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    router_watcher: ActiveRoutersWatcher = ActiveRoutersWatcher(coordinator)
    known_nfc_switches: dict[MAC_ADDR, HuaweiSwitch] = {}

    @callback
    def on_router_added(device_mac: MAC_ADDR, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        coordinator.hass.async_create_task(
            _add_nfc_if_available(
                coordinator, known_nfc_switches, device_mac, router, async_add_entities
            )
        )

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        router_watcher.look_for_changes(on_router_added)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
    coordinator_updated()


# ---------------------------
#   watch_for_wireless_devices
# ---------------------------
def watch_for_wireless_devices(coordinator, config_entry, async_add_entities):
    integration_options = HuaweiIntegrationOptions(config_entry)
    is_wifi_switches_enabled = integration_options.wifi_access_switches

    known_access_switches: dict[MAC_ADDR, HuaweiSwitch] = {}
    device_watcher: ClientWirelessDevicesWatcher = ClientWirelessDevicesWatcher(
        coordinator
    )

    @callback
    def on_wireless_device_added(device_mac: MAC_ADDR, device: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        coordinator.hass.async_create_task(
            _add_access_switch_if_available(
                coordinator,
                known_access_switches,
                device_mac,
                device,
                async_add_entities,
            )
        )

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        if is_wifi_switches_enabled:
            device_watcher.look_for_changes(on_wireless_device_added)

    if is_wifi_switches_enabled:
        config_entry.async_on_unload(
            coordinator.async_add_listener(coordinator_updated)
        )
        coordinator_updated()


# ---------------------------
#   watch_for_url_filters
# ---------------------------
def watch_for_url_filters(coordinator, config_entry, async_add_entities):
    integration_options = HuaweiIntegrationOptions(config_entry)
    is_url_filter_switches_enabled = integration_options.url_filter_switches

    known_url_filter_switches: dict[str, HuaweiSwitch] = {}
    filters_watcher: HuaweiUrlFiltersWatcher = HuaweiUrlFiltersWatcher(coordinator)

    @callback
    def on_filter_added(filter_id: str, url_filter: UrlFilter) -> None:
        """When a new filter is found."""
        coordinator.hass.async_create_task(
            _add_url_filter_switch_if_available(
                coordinator,
                known_url_filter_switches,
                url_filter,
                async_add_entities,
            )
        )

    @callback
    def on_filter_removed(
        er: EntityRegistry, filter_id: str, url_filter: UrlFilter
    ) -> None:
        """When a known filter removed."""
        unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_URL_FILTER, filter_id
        )
        entity_id = er.async_get_entity_id(Platform.SWITCH, DOMAIN, unique_id)
        if entity_id:
            er.async_remove(entity_id)
            if filter_id in known_url_filter_switches:
                del known_url_filter_switches[filter_id]
        else:
            _LOGGER.warning(
                "Can not remove unavailable switch '%s': entity id not found.",
                unique_id,
            )

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        if is_url_filter_switches_enabled:
            filters_watcher.look_for_changes(on_filter_added, on_filter_removed)

    if is_url_filter_switches_enabled:
        config_entry.async_on_unload(
            coordinator.async_add_listener(coordinator_updated)
        )
        coordinator_updated()


# ---------------------------
#   watch_for_port_mappings
# ---------------------------
def watch_for_port_mappings(coordinator, config_entry, async_add_entities):
    integration_options = HuaweiIntegrationOptions(config_entry)
    is_port_mapping_switches_enabled = integration_options.port_mapping_switches

    known_port_mapping_switches: dict[str, HuaweiSwitch] = {}
    port_mappings_watcher: HuaweiPortMappingsWatcher = HuaweiPortMappingsWatcher(
        coordinator
    )

    @callback
    def on_port_mapping_added(port_mapping_id: str, port_mapping: PortMapping) -> None:
        """When a new port mapping is found."""
        coordinator.hass.async_create_task(
            _add_port_mapping_switch_if_available(
                coordinator,
                known_port_mapping_switches,
                port_mapping,
                async_add_entities,
            )
        )

    @callback
    def on_port_mapping_removed(
        er: EntityRegistry, port_mapping_id: str, port_mapping: PortMapping
    ) -> None:
        """When a known port mapping removed."""
        unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_PORT_MAPPING, port_mapping_id
        )
        entity_id = er.async_get_entity_id(Platform.SWITCH, DOMAIN, unique_id)
        if entity_id:
            er.async_remove(entity_id)
            if port_mapping_id in known_port_mapping_switches:
                del known_port_mapping_switches[port_mapping_id]
        else:
            _LOGGER.warning(
                "Can not remove unavailable switch '%s': entity id not found.",
                unique_id,
            )

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        if is_port_mapping_switches_enabled:
            port_mappings_watcher.look_for_changes(
                on_port_mapping_added, on_port_mapping_removed
            )

    if is_port_mapping_switches_enabled:
        config_entry.async_on_unload(
            coordinator.async_add_listener(coordinator_updated)
        )
        coordinator_updated()


# ---------------------------
#   watch_for_time_control_items
# ---------------------------
def watch_for_time_control_items(coordinator, config_entry, async_add_entities):
    integration_options = HuaweiIntegrationOptions(config_entry)
    is_time_control_switches_enabled = integration_options.time_control_switches

    known_time_control_switches: dict[str, HuaweiSwitch] = {}
    time_controls_watcher: HuaweiTimeControlItemsWatcher = (
        HuaweiTimeControlItemsWatcher(coordinator)
    )

    @callback
    def on_time_control_added(
        time_control_id: str, time_control: HuaweiTimeControlItem
    ) -> None:
        """When a new time control is found."""
        coordinator.hass.async_create_task(
            _add_time_control_switch_if_available(
                coordinator,
                known_time_control_switches,
                time_control,
                async_add_entities,
            )
        )

    @callback
    def on_time_control_removed(
        er: EntityRegistry, time_control_id: str, time_control: HuaweiTimeControlItem
    ) -> None:
        """When a known port mapping removed."""
        unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_TIME_CONTROL, time_control_id
        )
        entity_id = er.async_get_entity_id(Platform.SWITCH, DOMAIN, unique_id)
        if entity_id:
            er.async_remove(entity_id)
            if time_control_id in known_time_control_switches:
                del known_time_control_switches[time_control_id]
        else:
            _LOGGER.warning(
                "Can not remove unavailable switch '%s': entity id not found.",
                unique_id,
            )

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        if is_time_control_switches_enabled:
            time_controls_watcher.look_for_changes(
                on_time_control_added, on_time_control_removed
            )

    if is_time_control_switches_enabled:
        config_entry.async_on_unload(
            coordinator.async_add_listener(coordinator_updated)
        )
        coordinator_updated()


# ---------------------------
#   HuaweiSwitch
# ---------------------------
class HuaweiSwitch(CoordinatorEntity[HuaweiDataUpdateCoordinator], SwitchEntity, ABC):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        switch: Switch | EmulatedSwitch,
        device_mac: MAC_ADDR | None = None,
        switch_id: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._switch: Switch | EmulatedSwitch = switch
        self._switch_id: str | None = switch_id
        self._device_mac: MAC_ADDR = device_mac
        self._attr_device_info = coordinator.get_device_info(device_mac)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        if self._device_mac:
            _LOGGER.debug(
                "Switch %s (%s) added to hass", self._switch, self._device_mac
            )
        else:
            _LOGGER.debug("Switch %s added to hass", self._switch)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.is_router_online(self._device_mac)
            and self.is_on is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Return current status."""
        return self.coordinator.get_switch_state(
            self._switch, self._device_mac, self._switch_id
        )

    async def _go_to_state(self, state: bool):
        """Perform transition to the specified state."""
        await self.coordinator.set_switch_state(
            self._switch, state, self._device_mac, self._switch_id
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """async_turn_off."""
        await self._go_to_state(False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """async_turn_on."""
        await self._go_to_state(True)

    def turn_on(self, **kwargs: Any) -> None:
        """turn_on."""
        return asyncio.run_coroutine_threadsafe(
            self.async_turn_on(**kwargs), self.hass.loop
        ).result()

    def turn_off(self, **kwargs: Any) -> None:
        """turn_off."""
        return asyncio.run_coroutine_threadsafe(
            self.async_turn_off(**kwargs), self.hass.loop
        ).result()


# ---------------------------
#   HuaweiNfcSwitch
# ---------------------------
class HuaweiNfcSwitch(HuaweiSwitch):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        device: ConnectedDevice | None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, Switch.NFC, device.mac if device else None)

        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_NFC,
            device.name if device else coordinator.primary_router_name,
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_UID_NFC, device.mac if device else None
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_NFC,
            device.name if device else None,
        )
        self._attr_icon = "mdi:nfc"


# ---------------------------
#   HuaweiWifi80211RSwitch
# ---------------------------
class HuaweiWifi80211RSwitch(HuaweiSwitch):
    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, Switch.WIFI_80211R, None)

        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_WIFI_802_11_R, coordinator.primary_router_name
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_UID_WIFI_802_11_R
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_WIFI_802_11_R,
        )
        self._attr_icon = "mdi:wifi-settings"


# ---------------------------
#   HuaweiWifiTWTSwitch
# ---------------------------
class HuaweiWifiTWTSwitch(HuaweiSwitch):
    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, Switch.WIFI_TWT, None)

        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_WIFI_TWT, coordinator.primary_router_name
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_WIFI_TWT
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_WIFI_TWT,
        )
        self._attr_icon = "mdi:wifi-settings"


# ---------------------------
#   HuaweiWlanFilterSwitch
# ---------------------------
class HuaweiWlanFilterSwitch(HuaweiSwitch):
    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, Switch.WLAN_FILTER, None)

        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_WLAN_FILTER, coordinator.primary_router_name
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_WLAN_FILTER
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_WLAN_FILTER,
        )
        self._attr_icon = "mdi:access-point-check"
        self._attr_entity_registry_enabled_default = False

    async def _go_to_state(self, state: bool):
        """Perform transition to the specified state."""
        await super()._go_to_state(state)
        self.coordinator.async_update_listeners()


# ---------------------------
#   HuaweiGuestNetworkSwitch
# ---------------------------
class HuaweiGuestNetworkSwitch(HuaweiSwitch):
    def __init__(self, coordinator: HuaweiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, Switch.GUEST_NETWORK, None)

        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_GUEST_NETWORK, coordinator.primary_router_name
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_GUEST_NETWORK
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_GUEST_NETWORK,
        )
        self._attr_icon = "mdi:wifi-refresh"
        self._attr_entity_registry_enabled_default = True

    async def _go_to_state(self, state: bool):
        """Perform transition to the specified state."""
        await super()._go_to_state(state)
        self.coordinator.async_update_listeners()


# ---------------------------
#   HuaweiDeviceAccessSwitch
# ---------------------------
class HuaweiDeviceAccessSwitch(HuaweiSwitch):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        device: ConnectedDevice,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, EmulatedSwitch.DEVICE_ACCESS, device.mac)
        self._attr_device_info = None

        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_DEVICE_ACCESS, device.name
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_DEVICE_ACCESS, device.mac
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_DEVICE_ACCESS,
            device.name,
        )
        self._attr_icon = "mdi:account-lock"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.get_switch_state(Switch.WLAN_FILTER):
            return False
        return self.coordinator.is_router_online() and self.is_on is not None


# ---------------------------
#   HuaweiUrlFilterSwitch
# ---------------------------
class HuaweiUrlFilterSwitch(HuaweiSwitch):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        filter_info: UrlFilter,
    ) -> None:
        """Initialize."""
        self._filter_info = filter_info
        self._attr_extra_state_attributes = {}
        super().__init__(
            coordinator, EmulatedSwitch.URL_FILTER, switch_id=filter_info.filter_id
        )
        self._attr_device_info = None

        self._attr_name = f"{_FUNCTION_DISPLAYED_NAME_URL_FILTER}: {filter_info.url}"

        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_URL_FILTER, filter_info.filter_id
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_URL_FILTER,
            filter_info.url,
        )
        self._attr_icon = "mdi:link-lock"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        debug_data = (
            f"Id: {self._filter_info.filter_id}, URL: {self._filter_info.url}, enabled: {self._filter_info.enabled}, "
            f"dev_manual: {self._filter_info.dev_manual}, devices: {self._filter_info.devices}"
        )

        _LOGGER.debug("Switch %s: info is %s", self._switch_id, debug_data)

        self._attr_name = (
            f"{_FUNCTION_DISPLAYED_NAME_URL_FILTER}: {self._filter_info.url}"
        )

        self._attr_extra_state_attributes["url"] = self._filter_info.url
        self._attr_extra_state_attributes["devices"] = (
            self._filter_info.devices if self._filter_info.dev_manual else "All"
        )

        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_router_online() and self.is_on is not None


# ---------------------------
#   HuaweiPortMappingSwitch
# ---------------------------
class HuaweiPortMappingSwitch(HuaweiSwitch):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        port_mapping: PortMapping,
    ) -> None:
        """Initialize."""
        self._port_mapping = port_mapping
        self._attr_extra_state_attributes = {}
        super().__init__(
            coordinator, EmulatedSwitch.PORT_MAPPING, switch_id=port_mapping.id
        )
        self._attr_device_info = None

        self._attr_name = (
            f"{_FUNCTION_DISPLAYED_NAME_PORT_MAPPING}: {port_mapping.name}"
        )

        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_PORT_MAPPING, port_mapping.id
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_PORT_MAPPING,
            port_mapping.name,
        )
        self._attr_icon = "mdi:upload-network-outline"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        debug_data = f"Id: {self._port_mapping.id}, name: {self._port_mapping.name}, enabled: {self._port_mapping.enabled}"

        _LOGGER.debug("Switch %s: info is %s", self._switch_id, debug_data)

        self._attr_name = (
            f"{_FUNCTION_DISPLAYED_NAME_PORT_MAPPING}: {self._port_mapping.name}"
        )

        self._attr_extra_state_attributes["host_name"] = self._port_mapping.host_name
        self._attr_extra_state_attributes["host_ip"] = self._port_mapping.host_ip
        self._attr_extra_state_attributes["host_mac"] = self._port_mapping.host_mac

        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_router_online() and self.is_on is not None


# ---------------------------
#   HuaweiTimeControlSwitch
# ---------------------------
class HuaweiTimeControlSwitch(HuaweiSwitch):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        time_control: HuaweiTimeControlItem,
    ) -> None:
        """Initialize."""
        self._time_control = time_control
        self._attr_extra_state_attributes = {}
        super().__init__(
            coordinator, EmulatedSwitch.TIME_CONTROL, switch_id=time_control.id
        )
        self._attr_device_info = None

        self._attr_name = (
            f"{_FUNCTION_DISPLAYED_NAME_TIME_CONTROL}: {time_control.name}"
        )

        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_ID_TIME_CONTROL, time_control.id
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_TIME_CONTROL,
            time_control.name,
        )
        self._attr_icon = "mdi:timer-lock-outline"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        debug_data = f"Id: {self._time_control.id}, name: {self._time_control.name}, enabled: {self._time_control.enabled}"

        _LOGGER.debug("Switch %s: info is %s", self._switch_id, debug_data)

        self._attr_name = (
            f"{_FUNCTION_DISPLAYED_NAME_TIME_CONTROL}: {self._time_control.name}"
        )

        for day in self._time_control.days.values():
            self._attr_extra_state_attributes[day.day_of_week.value.lower()] = (
                {
                    "is_enabled": day.is_enabled,
                    "start_time": day.start,
                    "end_time": day.end,
                }
                if day.is_enabled
                else {"is_enabled": day.is_enabled}
            )

        if self.coordinator.connected_devices:
            device_index = 1
            for device_mac in self._time_control.devices_mac:
                device: ConnectedDevice = self.coordinator.connected_devices.get(
                    device_mac
                )
                if device:
                    self._attr_extra_state_attributes[f"device_{device_index}"] = {
                        "mac": device.mac,
                        "name": device.name,
                    }
                    device_index += 1

        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_router_online() and self.is_on is not None
