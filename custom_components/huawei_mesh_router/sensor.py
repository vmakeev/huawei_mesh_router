"""Support for additional sensors."""

from dataclasses import dataclass
import logging
from typing import Any, Callable, Final

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory, generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .classes import DEVICE_TAG, ConnectedDevice, HuaweiInterfaceType
from .client.classes import MAC_ADDR
from .client.huaweiapi import CONNECTED_VIA_ID_PRIMARY
from .const import DOMAIN
from .update_coordinator import HuaweiControllerDataUpdateCoordinator, RoutersWatcher

UNITS_CLIENTS: Final = "clients"

_LOGGER = logging.getLogger(__name__)

_FUNCTION_DISPLAYED_NAME_TOTAL_CLIENTS: Final = "total clients"
_FUNCTION_UID_TOTAL_CLIENTS: Final = "sensor_total_clients"

_FUNCTION_DISPLAYED_NAME_CLIENTS: Final = "clients"
_FUNCTION_UID_CLIENTS: Final = "sensor_clients"

ENTITY_DOMAIN: Final = "sensor"
ENTITY_ID_FORMAT: Final = ENTITY_DOMAIN + ".{}"


# ---------------------------
#   HuaweiClientsSensorEntityDescription
# ---------------------------
@dataclass
class HuaweiClientsSensorEntityDescription(SensorEntityDescription):
    """A class that describes clients count sensor entities."""
    native_unit_of_measurement = UNITS_CLIENTS
    state_class = SensorStateClass.MEASUREMENT
    entity_category = EntityCategory.DIAGNOSTIC
    function_name: str | None = None
    function_uid: str | None = None
    device_mac: MAC_ADDR | None = None
    device_name: str | None = None


# ---------------------------
#   _generate_sensor_name
# ---------------------------
def _generate_sensor_name(
        sensor_function_displayed_name: str,
        device_name: str
) -> str:
    return f"{device_name} {sensor_function_displayed_name}"


# ---------------------------
#   _generate_sensor_id
# ---------------------------
def _generate_sensor_id(
        coordinator: HuaweiControllerDataUpdateCoordinator,
        sensor_function_displayed_name: str,
        device_name: str
) -> str:
    preferred_id = f"{coordinator.name} {sensor_function_displayed_name} {device_name}"
    return generate_entity_id(ENTITY_ID_FORMAT, preferred_id, hass=coordinator.hass)


# ---------------------------
#   _generate_sensor_unique_id
# ---------------------------
def _generate_sensor_unique_id(
        coordinator: HuaweiControllerDataUpdateCoordinator,
        sensor_function_id: str,
        device_mac: MAC_ADDR | None = None
) -> str:
    prefix = coordinator.unique_id
    suffix = coordinator.get_router_info().serial_number if not device_mac else device_mac
    return f"{prefix}_{sensor_function_id}_{suffix.lower()}"


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
                                         name=_generate_sensor_name(
                                             _FUNCTION_DISPLAYED_NAME_TOTAL_CLIENTS,
                                             coordinator.primary_router_name
                                         ),
                                         device_mac=None,
                                         device_name=coordinator.primary_router_name,
                                         function_uid=_FUNCTION_UID_TOTAL_CLIENTS,
                                         function_name=_FUNCTION_DISPLAYED_NAME_TOTAL_CLIENTS
                                     ),
                                     lambda device: device.is_active),
        HuaweiConnectedDevicesSensor(coordinator,
                                     HuaweiClientsSensorEntityDescription(
                                         key="primary",
                                         icon="mdi:router-wireless",
                                         name=_generate_sensor_name(
                                             _FUNCTION_DISPLAYED_NAME_CLIENTS,
                                             coordinator.primary_router_name
                                         ),
                                         device_mac=None,
                                         device_name=coordinator.primary_router_name,
                                         function_uid=_FUNCTION_UID_CLIENTS,
                                         function_name=_FUNCTION_DISPLAYED_NAME_CLIENTS
                                     ),
                                     lambda device:
                                     device.is_active and device.connected_via_id == CONNECTED_VIA_ID_PRIMARY)
    ]

    async_add_entities(sensors)

    watcher: RoutersWatcher = RoutersWatcher()
    known_client_sensors: dict[MAC_ADDR, HuaweiConnectedDevicesSensor] = {}

    @callback
    def on_router_added(mac: MAC_ADDR, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        if not known_client_sensors.get(mac):
            description = HuaweiClientsSensorEntityDescription(
                key=mac,
                icon="mdi:router-wireless",
                name=_generate_sensor_name(_FUNCTION_DISPLAYED_NAME_CLIENTS, router.name),
                device_mac=mac,
                device_name=router.name,
                function_uid=_FUNCTION_UID_CLIENTS,
                function_name=_FUNCTION_DISPLAYED_NAME_CLIENTS
            )
            entity = HuaweiConnectedDevicesSensor(
                coordinator,
                description,
                lambda device, via_id=mac:
                device.is_active and device.connected_via_id == via_id
            )
            async_add_entities([entity])
            known_client_sensors[mac] = entity

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        watcher.look_for_changes(coordinator, on_router_added)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))


# ---------------------------
#   HuaweiConnectedDevicesSensor
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
        self._device_mac = description.device_mac

        self._attr_name = description.name
        self._attr_device_info = coordinator.get_device_info(description.device_mac)
        self._attr_unique_id = _generate_sensor_unique_id(coordinator, description.function_uid, description.device_mac)
        self.entity_description = description
        self.entity_id = _generate_sensor_id(coordinator, description.function_name, description.device_name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_router_online(self._device_mac)

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

        untagged_clients: int = 0
        tagged_devices: dict[DEVICE_TAG, int] = {}
        for tag in self.coordinator.tags_map.get_all_tags():
            tagged_devices[tag] = 0

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

            if device.tags is None or len(device.tags) == 0:
                untagged_clients += 1
            else:
                for tag in device.tags:
                    if tag in tagged_devices:
                        tagged_devices[tag] += 1
                    else:
                        tagged_devices[tag] = 1

        self._actual_value = total_clients

        self._attrs["guest_clients"] = guest_clients
        self._attrs["hilink_clients"] = hilink_clients
        self._attrs["wireless_clients"] = wireless_clients
        self._attrs["lan_clients"] = lan_clients
        self._attrs["wifi_2_4_clients"] = wifi_2_4_clients
        self._attrs["wifi_5_clients"] = wifi_5_clients

        for tag, count in tagged_devices.items():
            self._attrs[f"tagged_{tag}_clients"] = count
        self._attrs[f"untagged_clients"] = untagged_clients

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> StateType | int:
        """Return the state."""
        return self._actual_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attrs
