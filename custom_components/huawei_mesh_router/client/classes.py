"""Huawei api classes."""

from __future__ import annotations

from datetime import datetime, time
from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum
from typing import Any, Dict, Final, Iterable, TypeAlias

VENDOR_CLASS_ID_ROUTER: Final = "router"

NODE_HILINK_TYPE_DEVICE: Final = "Device"
NODE_HILINK_TYPE_NONE: Final = "None"

MAC_ADDR: TypeAlias = str

KILOBYTES_PER_SECOND: TypeAlias = int


# ---------------------------
#   Feature
# ---------------------------
class Feature(StrEnum):
    NFC = "feature_nfc"
    URL_FILTER = "feature_url_filter"
    WIFI_80211R = "feature_wifi_80211r"
    WIFI_TWT = "feature_wifi_twt"
    WLAN_FILTER = "feature_wlan_filter"
    DEVICE_TOPOLOGY = "feature_device_topology"
    GUEST_NETWORK = "feature_guest_network"
    PORT_MAPPING = "feature_port_mapping"
    TIME_CONTROL = "feature_time_control"


# ---------------------------
#   Switch
# ---------------------------
class Switch(StrEnum):
    NFC = "nfc_switch"
    WIFI_80211R = "wifi_80211r_switch"
    WIFI_TWT = "wifi_twt_switch"
    WLAN_FILTER = "wlan_filter_switch"
    GUEST_NETWORK = "guest_network_switch"


# ---------------------------
#   Action
# ---------------------------
class Action(StrEnum):
    REBOOT: Final = "reboot_action"


# ---------------------------
#   Frequency
# ---------------------------
class Frequency(StrEnum):
    WIFI_2_4_GHZ = "2.4GHz"
    WIFI_5_GHZ = "5GHz"


# ---------------------------
#   FilterAction
# ---------------------------
class FilterAction(Enum):
    ADD = 0
    REMOVE = 1


# ---------------------------
#   FilterMode
# ---------------------------
class FilterMode(IntEnum):
    BLACKLIST = 0
    WHITELIST = 1


# ---------------------------
#   HuaweiGuestNetworkDuration
# ---------------------------
class HuaweiGuestNetworkDuration(IntEnum):
    FOUR_HOURS = 1
    ONE_DAY = 2
    UNLIMITED = 3


# ---------------------------
#   HuaweiRsaPublicKey
# ---------------------------
@dataclass()
class HuaweiRsaPublicKey:
    rsan: str
    rsae: str
    signature: str


# ---------------------------
#   HuaweiGuestNetworkConfig
# ---------------------------
@dataclass()
class HuaweiGuestNetworkItem:
    item_id: str
    enabled: bool
    sec_opt: str
    can_enable: bool
    pwd_score: int
    valid_time: HuaweiGuestNetworkDuration
    ssid: str
    key: str
    frequency: str
    rest_rime: int


# ---------------------------
#   HuaweiFilterItem
# ---------------------------
@dataclass()
class HuaweiFilterItem:
    mac_address: MAC_ADDR
    name: str | None = None


# ---------------------------
#   HuaweiUrlFilterInfo
# ---------------------------
@dataclass()
class HuaweiUrlFilterInfo:
    filter_id: str
    url: str
    enabled: bool
    dev_manual: bool
    devices: list[HuaweiFilterItem]


# ---------------------------
#   DayOfWeek
# ---------------------------
class DayOfWeek(StrEnum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


# ---------------------------
#   HuaweiPortMappingItem
# ---------------------------
class HuaweiPortMappingItem:
    def __init__(
        self,
        id: str,
        name: str,
        enabled: bool,
        host_ip: str,
        host_mac: MAC_ADDR,
        host_name: str,
        application_id: str,
    ) -> None:
        self._id = id
        self._name = name
        self._enabled = enabled
        self._host_ip = host_ip
        self._host_name = host_name
        self._host_mac = host_mac
        self._application_id = application_id

    @classmethod
    def parse(cls, raw_data: dict[str, Any]) -> HuaweiPortMappingItem:
        id = raw_data.get("ID")
        if not id:
            raise ValueError("Id can not be empty")

        raw_enabled = raw_data.get("Enable")
        enabled = isinstance(raw_enabled, bool) and raw_enabled

        ip_address = raw_data.get("HostIPAddress", "")
        mac_address = raw_data.get("InternalHost", "")
        name = raw_data.get("Name", "")
        host_name = raw_data.get("HostName", "")
        application_id = raw_data.get("ApplicationID", "")

        return HuaweiPortMappingItem(
            id, name, enabled, ip_address, mac_address, host_name, application_id
        )

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def host_name(self) -> str:
        return self._host_name

    @property
    def host_ip(self) -> str:
        return self._host_ip

    @property
    def host_mac(self) -> str:
        return self._host_mac


# ---------------------------
#   HuaweiFilterItem
# ---------------------------
class HuaweiFilterInfo:
    def __init__(
        self,
        enabled: bool,
        whitelist: list[HuaweiFilterItem],
        blacklist: list[HuaweiFilterItem],
        mode: FilterMode,
    ) -> None:
        self._enabled = enabled
        self._whitelist = whitelist
        self._blacklist = blacklist
        self._mode = mode

    @classmethod
    def parse(cls, raw_data: dict[str, Any]) -> HuaweiFilterInfo:
        raw_enabled = raw_data.get("MACAddressControlEnabled")
        enabled = isinstance(raw_enabled, bool) and raw_enabled

        raw_mode = raw_data.get("MacFilterPolicy")
        if raw_mode == 0:
            mode = FilterMode.BLACKLIST
        elif raw_mode == 1:
            mode = FilterMode.WHITELIST
        else:
            raise ValueError("MacFilterPolicy must be in range [0..1]")

        def get_item(raw_item: dict[str, Any]) -> HuaweiFilterItem:
            return HuaweiFilterItem(
                name=raw_item.get("HostName"), mac_address=raw_item.get("MACAddress")
            )

        raw_whitelist = raw_data.get("WMACAddresses")
        whitelist = [get_item(item) for item in raw_whitelist]

        raw_blacklist = raw_data.get("BMACAddresses")
        blacklist = [get_item(item) for item in raw_blacklist]

        return HuaweiFilterInfo(enabled, whitelist, blacklist, mode)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def mode(self) -> FilterMode:
        return self._mode

    @property
    def whitelist(self) -> Iterable[HuaweiFilterItem]:
        return self._whitelist

    @property
    def blacklist(self) -> Iterable[HuaweiFilterItem]:
        return self._blacklist


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
    upload_rate: KILOBYTES_PER_SECOND
    download_rate: KILOBYTES_PER_SECOND


# ---------------------------
#   HuaweiClientDevice
# ---------------------------
class HuaweiClientDevice:
    def __init__(self, device_data: Dict) -> None:
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
        return (
            self.is_hilink and self._data.get("VendorClassID") == VENDOR_CLASS_ID_ROUTER
        )

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

    @property
    def upload_rate(self) -> KILOBYTES_PER_SECOND:
        """Return the upload rate in kilobytes per second."""
        return self._data.get("UpRate", 0)

    @property
    def download_rate(self) -> KILOBYTES_PER_SECOND:
        """Return the download rate in kilobytes per second."""
        return self._data.get("DownRate", 0)


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


# ---------------------------
#   HuaweiTimeAccessItem
# ---------------------------
class HuaweiTimeControlItemDay:
    def __init__(
        self, day_of_week: DayOfWeek, is_enabled: bool, start: time, end: time
    ):
        """Initialize."""
        self._day_of_week = day_of_week
        self._is_enabled = is_enabled
        self._start = start
        self._end = end

    @property
    def day_of_week(self) -> DayOfWeek:
        """Return the day of week."""
        return self._day_of_week

    @property
    def is_enabled(self) -> bool:
        """Return the state of the day."""
        return self._is_enabled

    @property
    def start(self) -> time:
        """Return the start time at this day."""
        return self._start

    @property
    def end(self) -> time:
        """Return the end time at this day."""
        return self._end


# ---------------------------
#   HuaweiTimeAccessItem
# ---------------------------
class HuaweiTimeControlItem:
    def __init__(self, data: Dict):
        """Initialize."""
        self._data = data
        self._days: dict[DayOfWeek, HuaweiTimeControlItemDay] = {}

        for day_of_week in DayOfWeek:

            enabled_value = self._data.get(f"{day_of_week.value}enable")
            is_enabled: bool = isinstance(enabled_value, bool) and enabled_value

            start_value = self._data.get(f"{day_of_week.value}From", "00:00")
            start: time = datetime.strptime(start_value, "%H:%M").time()

            end_value = self._data.get(f"{day_of_week.value}To", "00:00")
            end: time = datetime.strptime(end_value, "%H:%M").time()

            day: HuaweiTimeControlItemDay = HuaweiTimeControlItemDay(
                day_of_week, is_enabled, start, end
            )

            self._days[day_of_week] = day

    @property
    def id(self) -> str:
        """Return the state of the item."""
        return self._data.get("ID")

    @property
    def name(self) -> str:
        """Return the name of the item."""
        device_names = [
            item.get("HostName", "device") for item in self._data.get("DeviceNames", [])
        ]
        days = [
            active_day.day_of_week.value
            for active_day in filter(lambda x: x.is_enabled, self._days.values())
        ]

        device_names_str = (
            "for " + ", ".join(device_names)
            if len(device_names) > 0
            else "for some devices"
        )

        if len(days) == 7:
            days_str = "for every day"
        elif days == ["Saturday", "Sunday"]:
            days_str = "on weekends"
        elif days == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            days_str = "on working days"
        else:
            days_str = "on " + ", ".join(days)

        return f"Time limit rule {device_names_str} {days_str}"

    @property
    def enabled(self) -> bool:
        """Return the state of the item."""
        value = self._data.get("Enable")
        return isinstance(value, bool) and value

    @property
    def devices_mac(self) -> Iterable[MAC_ADDR]:
        """Return the state of the item."""
        return [device.get("MACAddress", "no_mac_addr") for device in self._data.get("Devices", [])]

    @property
    def days(self) -> dict[DayOfWeek, HuaweiTimeControlItemDay]:
        """Return the schedule for each day."""
        return self._days

    def update(self, source: HuaweiTimeControlItem) -> None:
        self._data = source._data
        self._days = source._days

    def set_enabled(self, enabled: bool) -> None:
        self._data["Enable"] = enabled
