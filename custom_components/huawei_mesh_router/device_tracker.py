"""Support for Huawei routers as device tracker."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .classes import ConnectedDevice
from .client.classes import MAC_ADDR
from .const import DATA_KEY_COORDINATOR, DOMAIN
from .update_coordinator import HuaweiControllerDataUpdateCoordinator

FILTER_ATTRS = ("ip_address", "connected_via_id", "vendor_class_id")


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for Huawei component."""
    coordinator: HuaweiControllerDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ][DATA_KEY_COORDINATOR]
    tracked: dict[MAC_ADDR, HuaweiTracker] = {}

    @callback
    def coordinator_updated():
        """Update the status of the device."""
        update_items(coordinator, async_add_entities, tracked)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))

    coordinator_updated()


# ---------------------------
#   update_items
# ---------------------------
@callback
def update_items(
    coordinator: HuaweiControllerDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    tracked: dict[MAC_ADDR, HuaweiTracker],
) -> None:
    """Update tracked device state from the hub."""
    new_tracked: list[HuaweiTracker] = []
    for mac, device in coordinator.connected_devices.items():
        if mac not in tracked:
            tracked[mac] = HuaweiTracker(device, coordinator)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


# ---------------------------
#   HuaweiTracker
# ---------------------------
class HuaweiTracker(CoordinatorEntity, ScannerEntity):
    """Representation of network device."""

    def __init__(
        self,
        device: ConnectedDevice,
        coordinator: HuaweiControllerDataUpdateCoordinator,
    ) -> None:
        """Initialize the tracked device."""
        self.device: ConnectedDevice = device
        super().__init__(coordinator)

    @property
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        return self.device.is_active

    @property
    def source_type(self) -> str:
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return self.device.name

    @property
    def hostname(self) -> str:
        """Return the hostname of the client."""
        return self.device.host_name

    @property
    def mac_address(self) -> MAC_ADDR:
        """Return the mac address of the client."""
        return self.device.mac

    @property
    def ip_address(self) -> str:
        """Return the ip address of the client."""
        return self.device.ip_address

    @property
    def unique_id(self) -> str:
        """Return an unique identifier for this device."""
        return f"{self.coordinator.unique_id}_{self.device.mac}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {k: v for k, v in self.device.all_attrs if k not in FILTER_ATTRS}

    @property
    def entity_registry_enabled_default(self) -> bool:
        return True
