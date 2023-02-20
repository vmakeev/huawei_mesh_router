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

from .classes import ConnectedDevice
from .client.classes import MAC_ADDR
from .client.huaweiapi import (
    FEATURE_NFC,
    FEATURE_URL_FILTER,
    FEATURE_WIFI_80211R,
    FEATURE_WIFI_TWT,
    FEATURE_WLAN_FILTER,
    SWITCH_NFC,
    SWITCH_URL_FILTER,
    SWITCH_WIFI_80211R,
    SWITCH_WIFI_TWT,
    SWITCH_WLAN_FILTER,
)
from .const import DOMAIN
from .helpers import (
    generate_entity_id,
    generate_entity_name,
    generate_entity_unique_id,
    get_coordinator,
)
from .options import HuaweiIntegrationOptions
from .update_coordinator import (
    SWITCH_DEVICE_ACCESS,
    ActiveRoutersWatcher,
    ClientWirelessDevicesWatcher,
    HuaweiDataUpdateCoordinator,
    HuaweiUrlFiltersWatcher,
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
    if await coordinator.is_feature_available(FEATURE_NFC, mac):
        if not known_nfc_switches.get(mac):
            entity = HuaweiNfcSwitch(coordinator, router)
            async_add_entities([entity])
            known_nfc_switches[mac] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported at %s", FEATURE_NFC, mac)


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
    if await coordinator.is_feature_available(FEATURE_WLAN_FILTER):
        if not known_access_switches.get(mac):
            entity = HuaweiDeviceAccessSwitch(coordinator, device)
            async_add_entities([entity])
            known_access_switches[mac] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported", FEATURE_WLAN_FILTER)


# ---------------------------
#   _add_url_filter_switch_if_available
# ---------------------------
async def _add_url_filter_switch_if_available(
    coordinator: HuaweiDataUpdateCoordinator,
    known_url_filter_switches: dict[str, HuaweiSwitch],
    url_filter: UrlFilter,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if await coordinator.is_feature_available(FEATURE_URL_FILTER):
        if not known_url_filter_switches.get(url_filter.filter_id):
            entity = HuaweiUrlFilterSwitch(coordinator, url_filter)
            async_add_entities([entity])
            known_url_filter_switches[url_filter.filter_id] = entity
    else:
        _LOGGER.debug("Feature '%s' is not supported", FEATURE_URL_FILTER)


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

    is_nfc_available: bool = await coordinator.is_feature_available(FEATURE_NFC)

    if is_nfc_available:
        switches.append(HuaweiNfcSwitch(coordinator, None))
    else:
        _LOGGER.debug("Feature '%s' is not supported", FEATURE_NFC)

    if await coordinator.is_feature_available(FEATURE_WIFI_80211R):
        switches.append(HuaweiWifi80211RSwitch(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", FEATURE_WIFI_80211R)

    if await coordinator.is_feature_available(FEATURE_WIFI_TWT):
        switches.append(HuaweiWifiTWTSwitch(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", FEATURE_WIFI_TWT)

    if await coordinator.is_feature_available(FEATURE_WLAN_FILTER):
        switches.append(HuaweiWlanFilterSwitch(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", FEATURE_WLAN_FILTER)

    async_add_entities(switches)

    watch_for_additional_routers(coordinator, config_entry, async_add_entities)
    watch_for_url_filters(coordinator, config_entry, async_add_entities)


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

    integration_options = HuaweiIntegrationOptions(config_entry)
    is_wifi_switches_enabled = integration_options.wifi_access_switches

    @callback
    def on_router_added(device_mac: MAC_ADDR, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        coordinator.hass.async_add_job(
            _add_nfc_if_available(
                coordinator, known_nfc_switches, device_mac, router, async_add_entities
            )
        )

    if is_wifi_switches_enabled:
        device_watcher: ClientWirelessDevicesWatcher = ClientWirelessDevicesWatcher(
            coordinator
        )
        known_access_switches: dict[MAC_ADDR, HuaweiSwitch] = {}

    @callback
    def on_wireless_device_added(device_mac: MAC_ADDR, device: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        coordinator.hass.async_add_job(
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
        router_watcher.look_for_changes(on_router_added)
        if is_wifi_switches_enabled:
            device_watcher.look_for_changes(on_wireless_device_added)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
    coordinator_updated()


def watch_for_url_filters(coordinator, config_entry, async_add_entities):
    integration_options = HuaweiIntegrationOptions(config_entry)
    is_url_filter_switches_enabled = integration_options.url_filter_switches

    known_url_filter_switches: dict[str, HuaweiSwitch] = {}
    filters_watcher: HuaweiUrlFiltersWatcher = HuaweiUrlFiltersWatcher(
        coordinator, lambda item: True
    )

    @callback
    def on_filter_added(filter_id: str, url_filter: UrlFilter) -> None:
        """When a new filter is found."""
        coordinator.hass.async_add_job(
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
#   HuaweiSwitch
# ---------------------------
class HuaweiSwitch(CoordinatorEntity[HuaweiDataUpdateCoordinator], SwitchEntity, ABC):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        switch_name: str,
        device_mac: MAC_ADDR | None = None,
        switch_id: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._switch_name: str = switch_name
        self._switch_id: str | None = switch_id
        self._device_mac: MAC_ADDR = device_mac
        self._attr_device_info = coordinator.get_device_info(device_mac)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        if self._device_mac:
            _LOGGER.debug(
                "Switch %s (%s) added to hass", self._switch_name, self._device_mac
            )
        else:
            _LOGGER.debug("Switch %s added to hass", self._switch_name)

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
            self._switch_name, self._device_mac, self._switch_id
        )

    async def _go_to_state(self, state: bool):
        """Perform transition to the specified state."""
        await self.coordinator.set_switch_state(
            self._switch_name, state, self._device_mac, self._switch_id
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
        super().__init__(coordinator, SWITCH_NFC, device.mac if device else None)

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
        super().__init__(coordinator, SWITCH_WIFI_80211R, None)

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
        super().__init__(coordinator, SWITCH_WIFI_TWT, None)

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
        super().__init__(coordinator, SWITCH_WLAN_FILTER, None)

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
#   HuaweiDeviceAccessSwitch
# ---------------------------
class HuaweiDeviceAccessSwitch(HuaweiSwitch):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        device: ConnectedDevice,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, SWITCH_DEVICE_ACCESS, device.mac)
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
        if not self.coordinator.get_switch_state(SWITCH_WLAN_FILTER):
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
            coordinator, SWITCH_URL_FILTER, switch_id=filter_info.filter_id
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
