"""Huawei Mesh Router component classes."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

from homeassistant.backports.enum import StrEnum

from .client.classes import MAC_ADDR, HuaweiFilterItem

DEVICE_TAG = str


# ---------------------------
#   ZoneInfo
# ---------------------------
@dataclass()
class ZoneInfo:
    name: str
    entity_id: str


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
