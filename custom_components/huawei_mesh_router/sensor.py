"""Support for additional sensors."""
import logging

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .const import DOMAIN
from .update_coordinator import HuaweiControllerDataUpdateCoordinator
from .connected_device import ConnectedDevice, HuaweiInterfaceType

ATTR_GUEST_CLIENTS = "guest_clients"
ATTR_HILINK_CLIENTS = "hilink_clients"

UNITS_CLIENTS = "clients"

_LOGGER = logging.getLogger(__name__)

INTERFACES_WLAN = [HuaweiInterfaceType.INTERFACE_5GHZ, HuaweiInterfaceType.INTERFACE_2_4GHZ]


# ---------------------------
#   HuaweiClientsSensorEntityDescription
# ---------------------------
@dataclass
class HuaweiClientsSensorEntityDescription(SensorEntityDescription):
    """A class that describes clients count sensor entities."""
    native_unit_of_measurement = UNITS_CLIENTS
    state_class = SensorStateClass.MEASUREMENT
    entity_category = EntityCategory.DIAGNOSTIC


# ---------------------------
#   HuaweiInterfaceStatsSensorEntityDescription
# ---------------------------
@dataclass
class HuaweiInterfaceStatsSensorEntityDescription(HuaweiClientsSensorEntityDescription):
    """A class that describes interface stats sensor entities."""
    interface_type: HuaweiInterfaceType = None


INTERFACE_STATS_DESCRIPTIONS: List[HuaweiInterfaceStatsSensorEntityDescription] = [
    HuaweiInterfaceStatsSensorEntityDescription(
        key="5_ghz_clients",
        interface_type=HuaweiInterfaceType.INTERFACE_5GHZ,
        icon="mdi:access-point",
    ),
    HuaweiInterfaceStatsSensorEntityDescription(
        key="2_4_ghz_clients",
        interface_type=HuaweiInterfaceType.INTERFACE_2_4GHZ,
        icon="mdi:access-point",
    ),
    HuaweiInterfaceStatsSensorEntityDescription(
        key="lan_clients",
        interface_type=HuaweiInterfaceType.INTERFACE_LAN,
        icon="mdi:lan",
    ),
]


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors for Huawei component."""
    coordinator: HuaweiControllerDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [
        GuestDevicesStatsSensor(coordinator),
        HiLinkDevicesStatsSensor(coordinator),
        WirelessDevicesStatsSensor(coordinator),
        TotalDevicesStatsSensor(coordinator)
    ]

    for description in INTERFACE_STATS_DESCRIPTIONS:
        sensors.append(
            HuaweiInterfaceStatsSensor(coordinator, description)
        )

    async_add_entities(sensors)


# ---------------------------
#   ConnectedDevicesStatsSensor
# ---------------------------
class HuaweiConnectedDevicesStatsSensor(CoordinatorEntity[HuaweiControllerDataUpdateCoordinator], SensorEntity, ABC):

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            description: HuaweiClientsSensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._actual_value: int = 0

        self._attr_device_info = coordinator.device_info
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        _LOGGER.debug("%s added to hass", self._attr_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._actual_value = sum(
            1 for _ in filter(
                lambda device: self._device_predicate(device),
                self.coordinator.connected_devices.values()
            )
        )

        super()._handle_coordinator_update()

    @abstractmethod
    def _device_predicate(self, device: ConnectedDevice) -> bool:
        """Matching devices filter."""
        raise NotImplementedError()

    @property
    def native_value(self) -> StateType | int:
        """Return the state."""
        return self._actual_value


# ---------------------------
#   GuestDevicesStatsSensor
# ---------------------------
class GuestDevicesStatsSensor(HuaweiConnectedDevicesStatsSensor):

    def __init__(self, coordinator: HuaweiControllerDataUpdateCoordinator) -> None:
        """Initialize."""
        description = HuaweiClientsSensorEntityDescription(
            key="guest_clients",
            icon="mdi:account-question",
            name="Guest clients",
        )

        super().__init__(coordinator, description)

        self._attr_name = f"{self.coordinator.name} guest clients"
        self._attr_unique_id = f"guest_clients_{self.coordinator.router_info.serial_number}"

    def _device_predicate(self, device: ConnectedDevice) -> bool:
        """Matching devices filter."""
        return device.is_active and device.is_guest


# ---------------------------
#   WirelessDevicesStatsSensor
# ---------------------------
class WirelessDevicesStatsSensor(HuaweiConnectedDevicesStatsSensor):

    def __init__(self, coordinator: HuaweiControllerDataUpdateCoordinator) -> None:
        """Initialize."""
        description = HuaweiClientsSensorEntityDescription(
            key="wireless_clients",
            icon="mdi:wifi",
            name="Wireless clients",
        )

        super().__init__(coordinator, description)

        self._attr_name = f"{self.coordinator.name} wireless clients"
        self._attr_unique_id = f"wireless_clients_{self.coordinator.router_info.serial_number}"

    def _device_predicate(self, device: ConnectedDevice) -> bool:
        """Matching devices filter."""
        return device.is_active and device.interface_type in INTERFACES_WLAN


# ---------------------------
#   TotalDevicesStatsSensor
# ---------------------------
class TotalDevicesStatsSensor(HuaweiConnectedDevicesStatsSensor):

    def __init__(self, coordinator: HuaweiControllerDataUpdateCoordinator) -> None:
        """Initialize."""
        description = HuaweiClientsSensorEntityDescription(
            key="total_clients",
            icon="mdi:account-multiple",
            name="Total clients",
        )

        super().__init__(coordinator, description)

        self._attr_name = f"{self.coordinator.name} total clients"
        self._attr_unique_id = f"total_clients_{self.coordinator.router_info.serial_number}"

    def _device_predicate(self, device: ConnectedDevice) -> bool:
        """Matching devices filter."""
        return device.is_active


# ---------------------------
#   HiLinkDevicesStatsSensor
# ---------------------------
class HiLinkDevicesStatsSensor(HuaweiConnectedDevicesStatsSensor):

    def __init__(self, coordinator: HuaweiControllerDataUpdateCoordinator) -> None:
        """Initialize."""
        description = HuaweiClientsSensorEntityDescription(
            key="hilink_clients",
            icon="mdi:access-point-plus",
            name="HiLink clients",
        )

        super().__init__(coordinator, description)

        self._attr_name = f"{self.coordinator.name} hilink clients"
        self._attr_unique_id = f"hilink_clients_{self.coordinator.router_info.serial_number}"

    def _device_predicate(self, device: ConnectedDevice) -> bool:
        """Matching devices filter."""
        return device.is_active and device.is_hilink


# ---------------------------
#   InterfaceStatsSensor
# ---------------------------
class HuaweiInterfaceStatsSensor(HuaweiConnectedDevicesStatsSensor):

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            description: HuaweiInterfaceStatsSensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

        self._interface_type: HuaweiInterfaceType = description.interface_type

        self._attr_name = f"{self.coordinator.name} interface stats {self._interface_type}"
        self._attr_unique_id = f"interface_stats_" \
                               f"{self._interface_type.lower()}_{self.coordinator.router_info.serial_number}"
        self._attrs: dict[str, Any] = {}

    def _device_predicate(self, device: ConnectedDevice) -> bool:
        """Matching devices filter."""
        return device.is_active and device.interface_type == self._interface_type

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attrs[ATTR_GUEST_CLIENTS] = sum(
            1 for _ in filter(
                lambda device: self._device_predicate(device) and device.is_guest,
                self.coordinator.connected_devices.values()
            )
        )

        self._attrs[ATTR_HILINK_CLIENTS] = sum(
            1 for _ in filter(
                lambda device: self._device_predicate(device) and device.is_hilink,
                self.coordinator.connected_devices.values()
            )
        )

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> StateType | int:
        """Return the state."""
        return self._actual_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attrs
