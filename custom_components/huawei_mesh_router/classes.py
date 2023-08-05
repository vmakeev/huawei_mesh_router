"""Huawei Mesh Router component classes."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Dict, Iterable, Tuple, Final

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from .client.classes import MAC_ADDR, HuaweiFilterItem
from .const import DOMAIN

DEVICE_TAG = str


# ---------------------------
#   ZoneInfo
# ---------------------------
@dataclass()
class ZoneInfo:
    name: str
    entity_id: str


# ---------------------------
#   Select
# ---------------------------
class Select(StrEnum):
    WLAN_FILTER_MODE = "wlan_filter_mode_select"
    ROUTER_ZONE = "router_zone_select"


# ---------------------------
#   EmulatedSwitch
# ---------------------------
class EmulatedSwitch(StrEnum):
    DEVICE_ACCESS = "wlan_device_access_switch"
    URL_FILTER = "url_filter_switch"


# ---------------------------
#   HuaweiInterfaceType
# ---------------------------
class HuaweiInterfaceType(StrEnum):
    INTERFACE_5GHZ = "5GHz"
    INTERFACE_2_4GHZ = "2.4GHz"
    INTERFACE_LAN = "LAN"


# ---------------------------
#   HuaweiWlanFilterMode
# ---------------------------
class HuaweiWlanFilterMode(StrEnum):
    BLACKLIST = "Blacklist"
    WHITELIST = "Whitelist"


# ---------------------------
#   UrlFilter
# ---------------------------
class UrlFilter:
    def __init__(
        self,
        filter_id: str,
        url: str,
        enabled: bool,
        dev_manual: bool,
        devices: Iterable[HuaweiFilterItem],
    ) -> None:
        self._filter_id = filter_id
        self._url = url
        self._dev_manual = dev_manual
        self._devices = list(devices)
        self._enabled = enabled

    def update_info(
        self,
        url: str,
        enabled: bool,
        dev_manual: bool,
        devices: Iterable[HuaweiFilterItem],
    ) -> None:
        self._url = url
        self._dev_manual = dev_manual
        self._devices = list(devices)
        self._enabled = enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    @property
    def filter_id(self) -> str:
        return self._filter_id

    @property
    def url(self) -> str:
        return self._url

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def dev_manual(self) -> bool:
        return self._dev_manual

    @property
    def devices(self) -> Iterable[HuaweiFilterItem]:
        return self._devices


# ---------------------------
#   ConnectedDevice
# ---------------------------
class ConnectedDevice:
    def __init__(
        self,
        name: str,
        host_name: str,
        mac: MAC_ADDR,
        is_active: bool,
        tags: list[str],
        filter_mode: HuaweiWlanFilterMode | None,
        **kwargs,
    ) -> None:
        self._name: str = name
        self._host_name: str = host_name
        self._mac: MAC_ADDR = mac
        self._is_active: bool = is_active
        self._tags: list[str] = tags
        self._filter_mode: HuaweiWlanFilterMode | None = filter_mode
        self._data: Dict = kwargs or {}

    def update_device_data(
        self,
        name: str,
        host_name: str,
        is_active: bool,
        tags: list[str],
        filter_mode: HuaweiWlanFilterMode | None,
        **kwargs,
    ):
        self._name: str = name
        self._host_name: str = host_name
        self._is_active: bool = is_active
        self._tags: list[DEVICE_TAG] = tags
        self._filter_mode: str = filter_mode
        self._data: Dict = kwargs or {}

    def __str__(self) -> str:
        return f"Device {self._name} ({self._host_name}), {'' if self._is_active else 'not '}active, data: {self._data}"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def host_name(self) -> str:
        """Return the host name of the device."""
        return self._host_name

    @property
    def ip_address(self) -> str | None:
        """Return the ip address of the device."""
        return self._data.get("ip_address")

    @property
    def mac(self) -> MAC_ADDR:
        """Return the mac address of the device."""
        return self._mac

    @property
    def connected_via_id(self) -> str | None:
        """Return the id of parent device."""
        return self._data.get("connected_via_id")

    @property
    def connected_via_name(self) -> str | None:
        """Return the name of parent device."""
        return self._data.get("connected_via")

    @property
    def zone(self) -> ZoneInfo | None:
        """Return the zone of the device."""
        return self._data.get("zone")

    @property
    def interface_type(self) -> HuaweiInterfaceType | None:
        """Return the connection interface type."""
        return self._data.get("interface_type")

    @property
    def is_active(self) -> bool:
        """Return true when device is connected to mesh."""
        return self._is_active

    @property
    def is_guest(self) -> bool:
        """Return true when device is guest."""
        return self._data.get("is_guest", False)

    @property
    def is_hilink(self) -> bool:
        """Return true when device is hilink."""
        return self._data.get("is_hilink", False)

    @property
    def is_router(self) -> bool:
        """Return true when device is hilink router."""
        return self._data.get("is_router", False)

    @property
    def tags(self) -> list[DEVICE_TAG]:
        """Return device tags list."""
        return self._tags

    @property
    def filter_mode(self) -> HuaweiWlanFilterMode | None:
        """Return filter mode."""
        return self._filter_mode

    @property
    def all_attrs(self) -> Iterable[Tuple[str, Any]]:
        """Return dictionary with additional attributes."""
        for key, value in self._data.items():
            yield key, value
        yield "tags", self._tags
        yield "filter_list", self._filter_mode


# ---------------------------
#   EventTypes
# ---------------------------
class EventTypes(StrEnum):
    ROUTER_ADDED = "added"
    ROUTER_REMOVED = "removed"
    DEVICE_CONNECTED = "connected"
    DEVICE_DISCONNECTED = "disconnected"
    DEVICE_CHANGED_ROUTER = "changed_router"


HANDLER_TYPE = Callable[[str, dict[str, Any]], None]

EVENT_TYPE_ROUTER: Final = DOMAIN + "_event"
EVENT_TYPE_DEVICE: Final = DOMAIN + "_device_event"


# ---------------------------
#   HuaweiEvents
# ---------------------------
class HuaweiEvents:
    def __init__(self, hass: HomeAssistant):
        self._hass: HomeAssistant = hass
        self._subscriptions: dict[
            CALLBACK_TYPE, tuple[HANDLER_TYPE, object | None]
        ] = {}

    # ---------------------------
    #   async_subscribe_event
    # ---------------------------
    @callback
    def async_subscribe_event(
        self, event_types: list[str], handler: HANDLER_TYPE
    ) -> Callable[[], None]:
        @callback
        def remove_subscription() -> None:
            """Remove update listener."""
            self._subscriptions.pop(remove_subscription)

        self._subscriptions[remove_subscription] = (handler, event_types)

        return remove_subscription

    # ---------------------------
    #   _fire
    # ---------------------------
    def _fire(self, event_type: str, event_data: dict[str, Any]) -> None:
        self._hass.bus.fire(event_type, event_data)

        event_subtype = event_data.get("type")
        if event_subtype:
            for handler, target_types in list(self._subscriptions.values()):
                if event_subtype in target_types:
                    handler(event_subtype, event_data)

    # ---------------------------
    #   fire_router_added
    # ---------------------------
    def fire_router_added(
        self,
        primary_router_serial: str | None,
        router_mac: MAC_ADDR,
        router_ip: str,
        router_name: str | None
    ) -> None:
        """Fire an event when a new router is discovered."""
        event_data = {
            "type": EventTypes.ROUTER_ADDED,
            "primary_router": primary_router_serial,
            "router": {"ip": router_ip, "mac": router_mac, "name": router_name},
        }
        self._fire(EVENT_TYPE_ROUTER, event_data)

    # ---------------------------
    #   fire_router_removed
    # ---------------------------
    def fire_router_removed(
        self,
        primary_router_serial: str | None,
        router_mac: MAC_ADDR,
        router_ip: str,
        router_name: str | None
    ) -> None:
        """Fire an event when a router becomes unavailable."""
        event_data = {
            "type": EventTypes.ROUTER_REMOVED,
            "primary_router": primary_router_serial,
            "router": {"ip": router_ip, "mac": router_mac, "name": router_name},
        }
        self._fire(EVENT_TYPE_ROUTER, event_data)

    # ---------------------------
    #   fire_device_connected
    # ---------------------------
    def fire_device_connected(
        self,
        primary_router_serial: str | None,
        device_mac: MAC_ADDR,
        device_ip: str,
        device_name: str | None,
        router_id: str,
        router_name: str
    ) -> None:
        """Fire an event when a new device is connected."""
        event_data = {
            "type": EventTypes.DEVICE_CONNECTED,
            "primary_router": primary_router_serial,
            "device": {"ip": device_ip, "mac": device_mac, "name": device_name},
            "router": {"id": router_id, "name": router_name}
        }
        self._fire(EVENT_TYPE_DEVICE, event_data)

    # ---------------------------
    #   fire_device_disconnected
    # ---------------------------
    def fire_device_disconnected(
        self,
        primary_router_serial: str | None,
        device_mac: MAC_ADDR,
        device_ip: str,
        device_name: str | None,
        router_id: str,
        router_name: str
    ) -> None:
        """Fire an event when a device becomes disconnected."""
        event_data = {
            "type": EventTypes.DEVICE_DISCONNECTED,
            "primary_router": primary_router_serial,
            "device": {"ip": device_ip, "mac": device_mac, "name": device_name},
            "router": {"id": router_id, "name": router_name}
        }
        self._fire(EVENT_TYPE_DEVICE, event_data)

    # ---------------------------
    #   fire_device_changed_router
    # ---------------------------
    def fire_device_changed_router(
        self,
        primary_router_serial: str | None,
        device_mac: MAC_ADDR,
        device_ip: str,
        device_name: str | None,
        old_router_id: str,
        old_router_name: str,
        actual_router_id: str,
        actual_router_name: str,
    ):
        event_data = {
            "type": EventTypes.DEVICE_CHANGED_ROUTER,
            "primary_router": primary_router_serial,
            "device": {"ip": device_ip, "mac": device_mac, "name": device_name},
            "router_from": {"id": old_router_id, "name": old_router_name},
            "router_to": {"id": actual_router_id, "name": actual_router_name}
        }
        self._fire(EVENT_TYPE_DEVICE, event_data)
