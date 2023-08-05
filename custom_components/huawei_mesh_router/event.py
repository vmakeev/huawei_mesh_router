"""Huawei Mesh Router events."""
import logging
from dataclasses import dataclass
from typing import Final, Any

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .classes import EventTypes
from .helpers import (
    get_coordinator,
    generate_entity_id,
    generate_entity_name,
    generate_entity_unique_id,
)
from .update_coordinator import HuaweiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_EVENT_DISPLAYED_NAME_ROUTER: Final = "Routers"
_EVENT_UID_ROUTER: Final = "routers"

_EVENT_DISPLAYED_NAME_DEVICE: Final = "Devices"
_EVENT_UID_DEVICE_CONNECTED: Final = "devices"

ENTITY_DOMAIN: Final = "event"

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up events for Huawei component."""
    coordinator = get_coordinator(hass, config_entry)

    events = [
        HuaweiEvent(
            coordinator,
            HuaweiEventEntityDescription(
                key=_EVENT_UID_ROUTER,
                event_types=[EventTypes.ROUTER_ADDED, EventTypes.ROUTER_REMOVED],
                name=generate_entity_name(_EVENT_DISPLAYED_NAME_ROUTER),
                event_uid=_EVENT_UID_ROUTER,
                event_name=_EVENT_DISPLAYED_NAME_ROUTER,
            )
        ),
        HuaweiEvent(
            coordinator,
            HuaweiEventEntityDescription(
                key=_EVENT_UID_DEVICE_CONNECTED,
                event_types=[EventTypes.DEVICE_CONNECTED, EventTypes.DEVICE_DISCONNECTED, EventTypes.DEVICE_CHANGED_ROUTER],
                name=generate_entity_name(_EVENT_DISPLAYED_NAME_DEVICE),
                event_uid=_EVENT_UID_DEVICE_CONNECTED,
                event_name=_EVENT_DISPLAYED_NAME_DEVICE,
            )
        ),
    ]

    async_add_entities(events)


@dataclass
class HuaweiEventEntityDescription(EventEntityDescription):
    event_uid: str | None = None
    event_name: str | None = None


class HuaweiEvent(EventEntity):

    def __init__(
            self,
            coordinator: HuaweiDataUpdateCoordinator,
            description: HuaweiEventEntityDescription
    ) -> None:
        """Initialize."""
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_device_info = coordinator.get_device_info()
        self._attr_unique_id = generate_entity_unique_id(
            coordinator, description.event_uid
        )
        self.entity_id = generate_entity_id(
            coordinator,
            ENTITY_DOMAIN,
            description.event_name
        )

    @callback
    def _async_handle_event(self, event: str, data: dict[str, Any]) -> None:
        """Handle the demo button event."""
        self._trigger_event(event, data)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.coordinator.config_entry.async_on_unload(
            self.coordinator.async_subscribe_event(
                self.entity_description.event_types,
                self._async_handle_event
            )
        )
        await super().async_added_to_hass()
