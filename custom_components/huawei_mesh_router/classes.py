"""Huawei Mesh Router component classes."""

from typing import Any, Dict, Iterable, Tuple

from homeassistant.backports.enum import StrEnum

from .client.classes import MAC_ADDR

DEVICE_TAG = str

# ---------------------------
#   HuaweiInterfaceType
# ---------------------------
class HuaweiInterfaceType(StrEnum):
    INTERFACE_5GHZ = "5GHz"
    INTERFACE_2_4GHZ = "2.4GHz"
    INTERFACE_LAN = "LAN"


# ---------------------------
#   ConnectedDevice
# ---------------------------
class ConnectedDevice:

    def __init__(self,
                 name: str,
                 host_name: str,
                 mac: MAC_ADDR,
                 is_active: bool,
                 tags: list[str],
                 **kwargs) -> None:
        self._name: str = name
        self._host_name: str = host_name
        self._mac: MAC_ADDR = mac
        self._is_active: bool = is_active
        self._tags: list[str] = tags
        self._data: Dict = kwargs or {}

    def update_device_data(self,
                           name: str,
                           host_name: str,
                           is_active: bool,
                           tags: list[str],
                           **kwargs):
        self._name: str = name
        self._host_name: str = host_name
        self._is_active: bool = is_active
        self._tags: list[DEVICE_TAG] = tags
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
    def all_attrs(self) -> Iterable[Tuple[str, Any]]:
        """Return dictionary with additional attributes."""
        for key, value in self._data.items():
            yield key, value
        yield "tags", self._tags
