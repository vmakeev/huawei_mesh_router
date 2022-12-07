"""Support for additional sensors."""

from dataclasses import dataclass, field
import logging
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client.classes import MAC_ADDR
from .const import DATA_KEY_COORDINATOR, DOMAIN
from .helpers import (
    generate_entity_id,
    generate_entity_name,
    generate_entity_unique_id,
    get_past_moment,
)
from .update_coordinator import HuaweiControllerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_FUNCTION_DISPLAYED_NAME_WAN: Final = "Internet connection"
_FUNCTION_UID_WAN: Final = "internet_connection"

ENTITY_DOMAIN: Final = "binary_sensor"


# ---------------------------
#   HuaweiBinarySensorEntityDescription
# ---------------------------
@dataclass
class HuaweiBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes sensor entities."""
    function_name: str | None = None
    function_uid: str | None = None
    device_mac: MAC_ADDR | None = None
    device_name: str | None = None
    name: str | None = field(init=False)

    def __post_init__(self):
        self.name = generate_entity_name(self.function_name, self.device_name)


# ---------------------------
#   HuaweiWanSensorEntityDescription
# ---------------------------
@dataclass
class HuaweiWanSensorEntityDescription(HuaweiBinarySensorEntityDescription):
    """A class that describes sensor entities."""
    native_unit_of_measurement: str | None = None
    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC
    device_class: BinarySensorDeviceClass | str | None = BinarySensorDeviceClass.CONNECTIVITY


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors for Huawei component."""
    coordinator: HuaweiControllerDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_KEY_COORDINATOR]

    sensors = [
        HuaweiWanBinarySensor(
            coordinator,
            HuaweiWanSensorEntityDescription(
                key="wan",
                icon="mdi:web",
                device_mac=None,
                device_name=coordinator.primary_router_name,
                function_uid=_FUNCTION_UID_WAN,
                function_name=_FUNCTION_DISPLAYED_NAME_WAN
            ))
    ]

    async_add_entities(sensors)


# ---------------------------
#   HuaweiBinarySensor
# ---------------------------
class HuaweiBinarySensor(CoordinatorEntity[HuaweiControllerDataUpdateCoordinator], BinarySensorEntity):
    entity_description: HuaweiBinarySensorEntityDescription

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            description: HuaweiBinarySensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.get_device_info(description.device_mac)
        self._attr_unique_id = generate_entity_unique_id(
            coordinator,
            description.function_uid,
            description.device_mac
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            description.function_name,
            description.device_name
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
#   HuaweiWanBinarySensor
# ---------------------------
class HuaweiWanBinarySensor(HuaweiBinarySensor):
    entity_description: HuaweiBinarySensorEntityDescription

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            description: HuaweiBinarySensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)
        self._attr_is_on = None
        self._attr_extra_state_attributes = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        wan_info = self.coordinator.get_wan_info()
        if not wan_info:
            return

        self._attr_is_on = wan_info.connected
        self._attr_extra_state_attributes["external_ip"] = wan_info.address
        self._attr_extra_state_attributes["uptime_seconds"] = wan_info.uptime
        self._attr_extra_state_attributes["connected_at"] = get_past_moment(wan_info.uptime)
        super()._handle_coordinator_update()
