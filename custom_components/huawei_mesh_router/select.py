"""Huawei router selects."""

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Final, final

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .classes import ConnectedDevice, HuaweiWlanFilterMode, Select
from .client.classes import MAC_ADDR, Feature, Switch
from .helpers import (
    generate_entity_id,
    generate_entity_name,
    generate_entity_unique_id,
    get_coordinator,
)
from .options import HuaweiIntegrationOptions
from .update_coordinator import ActiveRoutersWatcher, HuaweiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ENTITY_DOMAIN: Final = "select"

_FUNCTION_DISPLAYED_NAME_WLAN_FILTER_MODE: Final = "WiFi access control mode"
_FUNCTION_UID_WLAN_FILTER_MODE: Final = "wifi_access_control_mode"
_OPTIONS_WLAN_FILTER_MODE: Final = [
    HuaweiWlanFilterMode.BLACKLIST,
    HuaweiWlanFilterMode.WHITELIST,
]

_FUNCTION_DISPLAYED_NAME_ZONE: Final = "Zone"
_FUNCTION_UID_ZONE: Final = "zone"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects for Huawei Router component."""
    coordinator = get_coordinator(hass, config_entry)
    integration_options = HuaweiIntegrationOptions(config_entry)

    selects: list[HuaweiSelect] = []

    if await coordinator.is_feature_available(Feature.WLAN_FILTER):
        selects.append(HuaweiWlanFilterModeSelect(coordinator))
    else:
        _LOGGER.debug("Feature '%s' is not supported", Feature.WLAN_FILTER)

    if integration_options.device_tracker_zones:
        selects.append(HuaweiRouterZoneSelect(coordinator, None))

    async_add_entities(selects)

    if integration_options.device_tracker_zones:
        watch_for_additional_routers(coordinator, config_entry, async_add_entities)


# ---------------------------
#   watch_for_additional_routers
# ---------------------------
def watch_for_additional_routers(
    coordinator: HuaweiDataUpdateCoordinator,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    router_watcher: ActiveRoutersWatcher = ActiveRoutersWatcher(coordinator)
    known_zone_selects: dict[MAC_ADDR, HuaweiRouterZoneSelect] = {}

    @callback
    def on_router_added(device_mac: MAC_ADDR, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        if not known_zone_selects.get(device_mac):
            entity = HuaweiRouterZoneSelect(coordinator, router)
            async_add_entities([entity])
            known_zone_selects[device_mac] = entity

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        router_watcher.look_for_changes(on_router_added)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
    coordinator_updated()


# ---------------------------
#   HuaweiSelect
# ---------------------------
class HuaweiSelect(CoordinatorEntity[HuaweiDataUpdateCoordinator], SelectEntity, ABC):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        select: Select,
        device_mac: MAC_ADDR | None,
        options: list[str],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._select = select
        self._device_mac = device_mac
        self._attr_options = options
        self._attr_device_info = coordinator.get_device_info(device_mac)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_router_online(self._device_mac)

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        return self.coordinator.get_select_state(self._select, self._device_mac)

    async def async_select_option(self, option: str) -> None:
        """Handle option changed."""
        await self.coordinator.set_select_state(self._select, option, self._device_mac)
        self.async_write_ha_state()

    @final
    def select_option(self, option: str) -> None:
        """Handle option changed."""
        return asyncio.run_coroutine_threadsafe(
            self.async_select_option(option), self.hass.loop
        ).result()


# ---------------------------
#   HuaweiMappedSelect
# ---------------------------
class HuaweiMappedSelect(HuaweiSelect, ABC):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        select: Select,
        device_mac: MAC_ADDR | None,
    ) -> None:
        """Initialize."""
        values_to_displayed = self._fetch_values_to_displayed(coordinator)
        super().__init__(
            coordinator, select, device_mac, list(values_to_displayed.values())
        )
        self._values_to_displayed = dict(values_to_displayed)
        self._displayed_to_values = {
            value: key for key, value in values_to_displayed.items()
        }

    def _get_value(self, displayed: str) -> str | None:
        result = self._displayed_to_values.get(displayed)
        return result

    def _get_displayed(self, value: str) -> str | None:
        result = self._values_to_displayed.get(value)
        return result

    def _process_updated_values(self, values_to_displayed: dict[str, str]):
        new_values_to_displayed = {**values_to_displayed}
        new_displayed_to_values = {
            value: key for key, value in values_to_displayed.items()
        }

        self._displayed_to_values = new_displayed_to_values
        self._values_to_displayed = new_values_to_displayed
        self._attr_options = list(self._values_to_displayed.values())

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        value = super().current_option
        option = self._get_displayed(value)
        return option

    async def async_select_option(self, option: str) -> None:
        """Handle option changed."""
        value = self._get_value(option)
        await super().async_select_option(value)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        values_to_displayed = self._fetch_values_to_displayed(self.coordinator)
        self._process_updated_values(values_to_displayed)
        super()._handle_coordinator_update()

    @abstractmethod
    def _fetch_values_to_displayed(self, coordinator):
        raise NotImplementedError()


# ---------------------------
#   HuaweiWlanFilterModeSelect
# ---------------------------
class HuaweiWlanFilterModeSelect(HuaweiSelect):
    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator, Select.WLAN_FILTER_MODE, None, _OPTIONS_WLAN_FILTER_MODE
        )
        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_WLAN_FILTER_MODE, coordinator.primary_router_name
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_UID_WLAN_FILTER_MODE, None
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_WLAN_FILTER_MODE,
        )
        self._attr_icon = "mdi:account-cancel"
        self._attr_entity_registry_enabled_default = False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.get_switch_state(Switch.WLAN_FILTER):
            return False
        return super().available

    async def async_select_option(self, option: str) -> None:
        """Handle option changed."""
        await super().async_select_option(option)
        await self.coordinator.calculate_device_access_switch_states()
        self.coordinator.async_update_listeners()


# ---------------------------
#   HuaweiRouterZoneSelect
# ---------------------------
class HuaweiRouterZoneSelect(HuaweiMappedSelect):
    def __init__(
        self, coordinator: HuaweiDataUpdateCoordinator, device: ConnectedDevice | None
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator, Select.ROUTER_ZONE, device.mac if device else None
        )

        self._attr_name = generate_entity_name(
            _FUNCTION_DISPLAYED_NAME_ZONE,
            device.name if device else coordinator.primary_router_name,
        )
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, _FUNCTION_UID_ZONE, self._device_mac
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            _FUNCTION_DISPLAYED_NAME_ZONE,
            device.name if device else None,
        )
        self._attr_icon = "mdi:map-marker-radius"

    def _fetch_values_to_displayed(self, coordinator):
        result = {"": ""}
        result.update({zone.entity_id: zone.name for zone in coordinator.zones})
        return result

    async def async_select_option(self, option: str) -> None:
        """Handle option changed."""
        await super().async_select_option(option)
        self.coordinator.async_update_listeners()
