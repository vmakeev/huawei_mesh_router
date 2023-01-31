"""Support for additional sensors."""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Callable, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .classes import DEVICE_TAG, ConnectedDevice, HuaweiInterfaceType
from .client.classes import MAC_ADDR
from .client.huaweiapi import CONNECTED_VIA_ID_PRIMARY
from .helpers import (
    generate_entity_id,
    generate_entity_name,
    generate_entity_unique_id,
    get_coordinator,
    get_past_moment,
)
from .options import HuaweiIntegrationOptions
from .update_coordinator import ActiveRoutersWatcher, HuaweiDataUpdateCoordinator

UNITS_CLIENTS: Final = "clients"

_LOGGER = logging.getLogger(__name__)

_FUNCTION_DISPLAYED_NAME_TOTAL_CLIENTS: Final = "total clients"
_FUNCTION_UID_TOTAL_CLIENTS: Final = "sensor_total_clients"

_FUNCTION_DISPLAYED_NAME_CLIENTS: Final = "clients"
_FUNCTION_UID_CLIENTS: Final = "sensor_clients"

_FUNCTION_DISPLAYED_NAME_UPTIME: Final = "uptime"
_FUNCTION_UID_UPTIME: Final = "sensor_uptime"

ENTITY_DOMAIN: Final = "sensor"


# ---------------------------
#   HuaweiSensorEntityDescription
# ---------------------------
@dataclass
class HuaweiSensorEntityDescription(SensorEntityDescription):
    """A class that describes sensor entities."""

    function_name: str | None = None
    function_uid: str | None = None
    device_mac: MAC_ADDR | None = None
    device_name: str | None = None
    name: str | None = None


# ---------------------------
#   HuaweiUptimeSensorEntityDescription
# ---------------------------
@dataclass
class HuaweiUptimeSensorEntityDescription(HuaweiSensorEntityDescription):
    """A class that describes sensor entities."""

    native_unit_of_measurement: str | None = None
    state_class: SensorStateClass | str | None = SensorStateClass.MEASUREMENT
    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC
    device_class: str | None = SensorDeviceClass.TIMESTAMP


# ---------------------------
#   HuaweiClientsSensorEntityDescription
# ---------------------------
@dataclass
class HuaweiClientsSensorEntityDescription(HuaweiSensorEntityDescription):
    """A class that describes clients count sensor entities."""

    native_unit_of_measurement: str | None = UNITS_CLIENTS
    state_class: SensorStateClass | str | None = SensorStateClass.MEASUREMENT
    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for Huawei component."""
    coordinator = get_coordinator(hass, config_entry)

    integration_options = HuaweiIntegrationOptions(config_entry)

    sensors = [
        HuaweiUptimeSensor(
            coordinator,
            HuaweiUptimeSensorEntityDescription(
                key="uptime",
                icon="mdi:timer-outline",
                name=generate_entity_name(
                    _FUNCTION_DISPLAYED_NAME_UPTIME, coordinator.primary_router_name
                ),
                device_mac=None,
                device_name=None,
                function_uid=_FUNCTION_UID_UPTIME,
                function_name=_FUNCTION_DISPLAYED_NAME_UPTIME,
            ),
        ),
        HuaweiConnectedDevicesSensor(
            coordinator,
            HuaweiClientsSensorEntityDescription(
                key="total",
                icon="mdi:account-multiple",
                name=generate_entity_name(
                    _FUNCTION_DISPLAYED_NAME_TOTAL_CLIENTS,
                    coordinator.primary_router_name,
                ),
                device_mac=None,
                device_name=None,
                function_uid=_FUNCTION_UID_TOTAL_CLIENTS,
                function_name=_FUNCTION_DISPLAYED_NAME_TOTAL_CLIENTS,
            ),
            integration_options,
            lambda device: device.is_active,
        ),
    ]

    if integration_options.router_clients_sensors:
        sensors.append(
            HuaweiConnectedDevicesSensor(
                coordinator,
                HuaweiClientsSensorEntityDescription(
                    key="primary",
                    icon="mdi:router-wireless",
                    name=generate_entity_name(
                        _FUNCTION_DISPLAYED_NAME_CLIENTS,
                        coordinator.primary_router_name,
                    ),
                    device_mac=None,
                    device_name=None,
                    function_uid=_FUNCTION_UID_CLIENTS,
                    function_name=_FUNCTION_DISPLAYED_NAME_CLIENTS,
                ),
                integration_options,
                lambda device: device.is_active
                and device.connected_via_id == CONNECTED_VIA_ID_PRIMARY,
            )
        )

    async_add_entities(sensors)

    watch_for_additional_routers(
        coordinator, config_entry, integration_options, async_add_entities
    )


# ---------------------------
#   watch_for_additional_routers
# ---------------------------
def watch_for_additional_routers(
    coordinator: HuaweiDataUpdateCoordinator,
    config_entry: ConfigEntry,
    integration_options: HuaweiIntegrationOptions,
    async_add_entities: AddEntitiesCallback,
):
    watcher: ActiveRoutersWatcher = ActiveRoutersWatcher()
    known_client_sensors: dict[MAC_ADDR, HuaweiConnectedDevicesSensor] = {}
    known_uptime_sensors: dict[MAC_ADDR, HuaweiUptimeSensor] = {}

    @callback
    def on_router_added(mac: MAC_ADDR, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        new_entities = []

        if integration_options.router_clients_sensors and not known_client_sensors.get(
            mac
        ):
            description = HuaweiClientsSensorEntityDescription(
                key=mac,
                icon="mdi:router-wireless",
                name=generate_entity_name(
                    _FUNCTION_DISPLAYED_NAME_CLIENTS,
                    router.name,
                ),
                device_mac=mac,
                device_name=router.name,
                function_uid=_FUNCTION_UID_CLIENTS,
                function_name=_FUNCTION_DISPLAYED_NAME_CLIENTS,
            )
            entity = HuaweiConnectedDevicesSensor(
                coordinator,
                description,
                integration_options,
                lambda device, via_id=mac: device.is_active
                and device.connected_via_id == via_id,
            )
            known_client_sensors[mac] = entity
            new_entities.append(entity)

        if not known_uptime_sensors.get(mac):
            description = HuaweiUptimeSensorEntityDescription(
                key="uptime",
                icon="mdi:timer-outline",
                name=generate_entity_name(
                    _FUNCTION_DISPLAYED_NAME_UPTIME,
                    router.name,
                ),
                device_mac=mac,
                device_name=router.name,
                function_uid=_FUNCTION_UID_UPTIME,
                function_name=_FUNCTION_DISPLAYED_NAME_UPTIME,
            )
            entity = HuaweiUptimeSensor(coordinator, description)
            known_uptime_sensors[mac] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        watcher.look_for_changes(coordinator, on_router_added)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
    coordinator_updated()


# ---------------------------
#   HuaweiSensor
# ---------------------------
class HuaweiSensor(CoordinatorEntity[HuaweiDataUpdateCoordinator], SensorEntity):
    entity_description: HuaweiSensorEntityDescription

    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        description: HuaweiSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.get_device_info(description.device_mac)
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, description.function_uid, description.device_mac
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            description.function_name,
            description.device_name,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_router_online(self.entity_description.device_mac)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        _LOGGER.debug("%s added to hass", self.name)


# ---------------------------
#   HuaweiUptimeSensor
# ---------------------------
class HuaweiUptimeSensor(HuaweiSensor):
    entity_description: HuaweiUptimeSensorEntityDescription
    _attr_native_value: datetime | None = None

    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        description: HuaweiUptimeSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        router_info = self.coordinator.get_router_info(
            self.entity_description.device_mac
        )
        if not router_info:
            return
        uptime_seconds = router_info.uptime
        self._attr_native_value = get_past_moment(uptime_seconds)
        self._attr_extra_state_attributes["seconds"] = uptime_seconds
        super()._handle_coordinator_update()


# ---------------------------
#   HuaweiConnectedDevicesSensor
# ---------------------------
class HuaweiConnectedDevicesSensor(HuaweiSensor):
    entity_description: HuaweiClientsSensorEntityDescription
    _attr_native_value: int = 0

    def __init__(
        self,
        coordinator: HuaweiDataUpdateCoordinator,
        description: HuaweiClientsSensorEntityDescription,
        integration_options: HuaweiIntegrationOptions,
        devices_predicate: Callable[[ConnectedDevice], bool],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

        self._integration_options = integration_options
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {}
        self._devices_predicate: Callable[[ConnectedDevice], bool] = devices_predicate

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        tags_enabled = self._integration_options.devices_tags

        total_clients: int = 0
        guest_clients: int = 0
        hilink_clients: int = 0
        wireless_clients: int = 0
        lan_clients: int = 0
        wifi_2_4_clients: int = 0
        wifi_5_clients: int = 0

        untagged_clients: int = 0
        tagged_devices: dict[DEVICE_TAG, int] = {}

        if tags_enabled:
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

            if tags_enabled:
                if device.tags is None or len(device.tags) == 0:
                    untagged_clients += 1
                else:
                    for tag in device.tags:
                        if tag in tagged_devices:
                            tagged_devices[tag] += 1
                        else:
                            tagged_devices[tag] = 1

        self._attr_native_value = total_clients

        self._attr_extra_state_attributes["guest_clients"] = guest_clients
        self._attr_extra_state_attributes["hilink_clients"] = hilink_clients
        self._attr_extra_state_attributes["wireless_clients"] = wireless_clients
        self._attr_extra_state_attributes["lan_clients"] = lan_clients
        self._attr_extra_state_attributes["wifi_2_4_clients"] = wifi_2_4_clients
        self._attr_extra_state_attributes["wifi_5_clients"] = wifi_5_clients

        if tags_enabled:
            for tag, count in tagged_devices.items():
                self._attr_extra_state_attributes[f"tagged_{tag}_clients"] = count
            self._attr_extra_state_attributes[f"untagged_clients"] = untagged_clients

        super()._handle_coordinator_update()
