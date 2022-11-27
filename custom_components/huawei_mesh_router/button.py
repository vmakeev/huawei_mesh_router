"""Huawei router switches."""
import asyncio
from abc import ABC
from typing import Any
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import (
    DOMAIN
)
from .connected_device import ConnectedDevice
from .update_coordinator import (HuaweiControllerDataUpdateCoordinator, RoutersWatcher)
from .client.huaweiapi import (
    ACTION_REBOOT,
)
from homeassistant.core import callback, HomeAssistant

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   _generate_button_unique_id
# ---------------------------
def _generate_button_unique_id(
        coordinator: HuaweiControllerDataUpdateCoordinator,
        action_name: str,
        device_mac: str | None
) -> str:
    if device_mac:
        return f"button_{action_name}_{device_mac}_{coordinator.router_info.serial_number}"
    else:
        return f"button_{action_name}_{coordinator.router_info.serial_number}"


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    """Set up switches for Huawei Router component."""
    coordinator: HuaweiControllerDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    buttons = [
        HuaweiRebootButton(coordinator, None)
    ]

    async_add_entities(buttons)

    watcher: RoutersWatcher = RoutersWatcher()

    @callback
    def on_router_added(_, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        entity = HuaweiRebootButton(coordinator, router)
        async_add_entities([entity])

    @callback
    def on_router_removed(er: EntityRegistry, mac: str, _) -> None:
        """When a known mesh router becomes unavailable."""
        unique_id = _generate_button_unique_id(coordinator, ACTION_REBOOT, mac)
        entity_id = er.async_get_entity_id(Platform.BUTTON, DOMAIN, unique_id)
        if entity_id:
            er.async_remove(entity_id)
        else:
            _LOGGER.warning("Can not remove unavailable button '%s': entity id not found.", unique_id)

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        watcher.watch_for_changes(coordinator, on_router_added, on_router_removed)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
    coordinator_updated()


# ---------------------------
#   HuaweiButton
# ---------------------------
class HuaweiButton(CoordinatorEntity[HuaweiControllerDataUpdateCoordinator], ButtonEntity, ABC):
    _update_url: str

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            action_name: str,
            device_mac: str | None
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._action_name: str = action_name
        self._device_mac: str = device_mac
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        if self._device_mac:
            _LOGGER.debug("Button %s (%s) added to hass", self._action_name, self._device_mac)
        else:
            _LOGGER.debug("Button %s added to hass", self._action_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    async def async_press(self) -> None:
        """Triggers the button press service."""
        await self.coordinator.execute_action(self._action_name, self._device_mac)

    def press(self) -> None:
        """Press the button."""
        return asyncio.run_coroutine_threadsafe(
            self.async_press(), self.hass.loop
        ).result()


# ---------------------------
#   HuaweiRebootButton
# ---------------------------
class HuaweiRebootButton(HuaweiButton):

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            device: ConnectedDevice | None
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, ACTION_REBOOT, device.mac if device else None)

        self._attr_name = f"{self.coordinator.name} Reboot ({device.name if device else 'primary router'})"
        self._attr_unique_id = _generate_button_unique_id(coordinator, ACTION_REBOOT, device.mac if device else None)
        self._attr_icon = "mdi:restart"
