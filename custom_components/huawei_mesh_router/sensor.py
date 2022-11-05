"""Support for additional sensors."""
import logging

from dataclasses import dataclass
from typing import Any, Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .const import DOMAIN, CONNECTED_VIA_ID_PRIMARY
from .update_coordinator import HuaweiControllerDataUpdateCoordinator, RoutersWatcher
from .connected_device import ConnectedDevice, HuaweiInterfaceType

UNITS_CLIENTS = "clients"

_LOGGER = logging.getLogger(__name__)


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
#   _generate_clients_sensor_name
# ---------------------------
def _generate_clients_sensor_name(coordinator: HuaweiControllerDataUpdateCoordinator, source_name: str) -> str:
    return f"{coordinator.name} clients ({source_name})"


# ---------------------------
#   _generate_sensor_unique_id
# ---------------------------
def _generate_sensor_unique_id(coordinator: HuaweiControllerDataUpdateCoordinator, sensor_name: str) -> str:
    return f"{sensor_name}_{coordinator.router_info.serial_number}"


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
        HuaweiConnectedDevicesSensor(coordinator,
                                     HuaweiClientsSensorEntityDescription(
                                         key="total",
                                         icon="mdi:account-multiple",
                                         name=_generate_clients_sensor_name(coordinator, "total")
                                     ),
                                     lambda device: device.is_active),
        HuaweiConnectedDevicesSensor(coordinator,
                                     HuaweiClientsSensorEntityDescription(
                                         key="primary",
                                         icon="mdi:router-wireless",
                                         name=_generate_clients_sensor_name(coordinator, "primary router")
                                     ),
                                     lambda device:
                                     device.is_active and device.connected_via_id == CONNECTED_VIA_ID_PRIMARY)
    ]

    async_add_entities(sensors)

    watcher: RoutersWatcher = RoutersWatcher()

    @callback
    def on_router_added(mac: str, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        entity = HuaweiConnectedDevicesSensor(coordinator,
                                              HuaweiClientsSensorEntityDescription(
                                                  key=mac,
                                                  icon="mdi:router-wireless",
                                                  name=_generate_clients_sensor_name(coordinator, router.name)
                                              ),
                                              lambda device, via_id=mac:
                                              device.is_active and device.connected_via_id == via_id)
        async_add_entities([entity])

    @callback
    def on_router_removed(er: EntityRegistry, mac: str, router: ConnectedDevice) -> None:
        """When a known mesh router becomes unavailable."""
        sensor_name = _generate_clients_sensor_name(coordinator, router.name)
        unique_id = _generate_sensor_unique_id(coordinator, sensor_name)
        entity_id = er.async_get_entity_id(Platform.SENSOR, DOMAIN, unique_id)
        if entity_id:
            er.async_remove(entity_id)
        else:
            _LOGGER.warning("Can not remove unavailable sensor '%s': entity id not found.", unique_id)

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        watcher.watch_for_changes(coordinator, on_router_added, on_router_removed)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
    coordinator_updated()


# ---------------------------
#   HuaweiRouterConnectedDevicesSensor
# ---------------------------
class HuaweiConnectedDevicesSensor(CoordinatorEntity[HuaweiControllerDataUpdateCoordinator], SensorEntity):

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            description: HuaweiClientsSensorEntityDescription,
            devices_predicate: Callable[[ConnectedDevice], bool]
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._actual_value: int = 0
        self._attrs: dict[str, Any] = {}
        self._devices_predicate: Callable[[ConnectedDevice], bool] = devices_predicate

        self._attr_name = description.name
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = _generate_sensor_unique_id(coordinator, description.name)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        _LOGGER.debug("%s added to hass", self._attr_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        total_clients: int = 0
        guest_clients: int = 0
        hilink_clients: int = 0
        wireless_clients: int = 0
        lan_clients: int = 0
        wifi_2_4_clients: int = 0
        wifi_5_clients: int = 0

        for device in self.coordinator.connected_devices.values():

            if not self._devices_predicate(device):
                continue

            total_clients += 1

            if device.is_guest:
                guest_clients += 1
            if device.is_hilink:
                hilink_clients += 1

            if device.interface_type == HuaweiInterfaceType.INTERFACE_LAN:
                lan_clients += 1
            elif device.interface_type == HuaweiInterfaceType.INTERFACE_2_4GHZ:
                wireless_clients += 1
                wifi_2_4_clients += 1
            elif device.interface_type == HuaweiInterfaceType.INTERFACE_5GHZ:
                wireless_clients += 1
                wifi_5_clients += 1

        self._actual_value = total_clients

        self._attrs["guest_clients"] = guest_clients
        self._attrs["hilink_clients"] = hilink_clients
        self._attrs["wireless_clients"] = wireless_clients
        self._attrs["lan_clients"] = lan_clients
        self._attrs["wifi_2_4_clients"] = wifi_2_4_clients
        self._attrs["wifi_5_clients"] = wifi_5_clients

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> StateType | int:
        """Return the state."""
        return self._actual_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attrs
