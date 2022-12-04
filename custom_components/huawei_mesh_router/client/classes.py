"""Huawei api classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Final, Iterable, TypeAlias

VENDOR_CLASS_ID_ROUTER: Final = "router"

NODE_HILINK_TYPE_DEVICE: Final = "Device"
NODE_HILINK_TYPE_NONE: Final = "None"

MAC_ADDR: TypeAlias = str


# ---------------------------
#   HuaweiRouterInfo
# ---------------------------
@dataclass
class HuaweiRouterInfo:
    name: str
    model: str
    serial_number: str
    hardware_version: str
    software_version: str
    harmony_os_version: str
    uptime: int


# ---------------------------
#   HuaweiConnectionInfo
# ---------------------------
@dataclass
class HuaweiConnectionInfo:
    uptime: int
    connected: bool
    address: str | None


# ---------------------------
#   HuaweiClientDevice
# ---------------------------
class HuaweiClientDevice:

    def __init__(
            self,
            device_data: Dict
    ) -> None:
        """Initialize."""
        self._data: Dict = device_data

    def get_raw_value(self, property_name: str) -> Any | None:
        """Return the raw value from api response."""
        return self._data.get(property_name)

    @property
    def mac_address(self) -> MAC_ADDR | None:
        """Return the mac address of the device."""
        return self._data.get("MACAddress")

    @property
    def is_active(self) -> bool:
        """Return true when device is connected to network."""
        value = self._data.get("Active")
        return isinstance(value, bool) and value

    @property
    def rssi(self) -> int | None:
        """Return signal strength."""
        value = self._data.get("rssi")
        return value if isinstance(value, int) else None

    @property
    def is_hilink(self) -> bool:
        """Return true when device is hilink."""
        value = self._data.get("HiLinkDevice")
        return isinstance(value, bool) and value

    @property
    def is_guest(self) -> bool:
        """Return true when device is guest."""
        value = self._data.get("IsGuest")
        return isinstance(value, bool) and value

    @property
    def is_router(self) -> bool:
        """Return true when device is hilink router."""
        return self.is_hilink and self._data.get("VendorClassID") == VENDOR_CLASS_ID_ROUTER

    @property
    def actual_name(self) -> str | None:
        """Return the name of the device."""
        return self._data.get("ActualName")

    @property
    def host_name(self) -> str | None:
        """Return the host name of the device."""
        return self._data.get("HostName")

    @property
    def ip_address(self) -> str | None:
        """Return the ip address of the device."""
        return self._data.get("IPAddress")

    @property
    def interface_type(self) -> str | None:
        """Return the connection interface type."""
        return self._data.get("InterfaceType")


# ---------------------------
#   HuaweiClientDevice
# ---------------------------
class HuaweiDeviceNode:

    def __init__(self, mac: MAC_ADDR, hilink_type: str | None):
        """Initialize."""
        self._mac = mac
        self._hilink_type = hilink_type
        self._connected_devices: list[HuaweiDeviceNode] = []

    @property
    def mac_address(self) -> MAC_ADDR:
        """Return the mac address of the device."""
        return self._mac

    @property
    def hilink_type(self) -> str:
        """Return the hilink type of the device."""
        return self._hilink_type

    @property
    def connected_devices(self) -> Iterable[HuaweiDeviceNode]:
        """Return the nodes that are connected to the device."""
        return self._connected_devices

    def add_device(self, device: HuaweiDeviceNode) -> None:
        """Add connected node to the device."""
        self._connected_devices.append(device)
