"""Huawei router selects."""

from abc import ABC
import asyncio
from typing import Final, final

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .classes import HuaweiWlanFilterMode
from .client.classes import MAC_ADDR
from .helpers import (
    generate_entity_id,
    generate_entity_name,
    generate_entity_unique_id,
    get_coordinator,
)
from .update_coordinator import (
    SELECT_WLAN_FILTER_MODE,
    SWITCH_WLAN_FILTER,
    HuaweiControllerDataUpdateCoordinator,
)

ENTITY_DOMAIN: Final = "select"

_FUNCTION_DISPLAYED_NAME_WLAN_FILTER_MODE: Final = "WiFi access control mode"
_FUNCTION_UID_WLAN_FILTER_MODE: Final = "wifi_access_control_mode"
_OPTIONS_WLAN_FILTER_MODE: Final = [
    HuaweiWlanFilterMode.BLACKLIST,
    HuaweiWlanFilterMode.WHITELIST,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects for Huawei Router component."""
    coordinator = get_coordinator(hass, config_entry)

    selects: list[HuaweiSelect] = [HuaweiWlanFilterModeSelect(coordinator)]

    async_add_entities(selects)


# ---------------------------
#   HuaweiSelect
# ---------------------------
class HuaweiSelect(
    CoordinatorEntity[HuaweiControllerDataUpdateCoordinator], SelectEntity, ABC
):
    def __init__(
        self,
        coordinator: HuaweiControllerDataUpdateCoordinator,
        select_name: str,
        device_mac: MAC_ADDR | None,
        options: list[str],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._select_name = select_name
        self._device_mac = device_mac
        self._attr_options = options
        self._attr_current_option = None
        self._attr_device_info = coordinator.get_device_info()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_router_online(self._device_mac)

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        return self.coordinator.get_select_state(self._select_name, self._device_mac)

    async def async_select_option(self, option: str) -> None:
        """Handle option changed."""
        await self.coordinator.set_select_state(
            self._select_name, option, self._device_mac
        )
        self.async_write_ha_state()

    @final
    def select_option(self, option: str) -> None:
        """Handle option changed."""
        return asyncio.run_coroutine_threadsafe(
            self.async_select_option(option), self.hass.loop
        ).result()


# ---------------------------
#   HuaweiSelect
# ---------------------------
class HuaweiWlanFilterModeSelect(HuaweiSelect):
    def __init__(
        self,
        coordinator: HuaweiControllerDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator, SELECT_WLAN_FILTER_MODE, None, _OPTIONS_WLAN_FILTER_MODE
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
            coordinator.primary_router_name,
        )
        self._attr_icon = "mdi:account-cancel"
        self._attr_entity_registry_enabled_default = False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.get_switch_state(SWITCH_WLAN_FILTER):
            return False
        return super().available

    async def async_select_option(self, option: str) -> None:
        """Handle option changed."""
        await super().async_select_option(option)
        await self.coordinator.calculate_device_access_switch_states()
        self.coordinator.async_update_listeners()
