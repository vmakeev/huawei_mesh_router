"""Huawei Mesh Router shared constants."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "huawei_mesh_router"

STORAGE_VERSION: Final = 1

DATA_KEY_COORDINATOR: Final = "coordinator"
DATA_KEY_PLATFORMS: Final = "platforms"
DATA_KEY_SERVICES: Final = "services_count"

OPT_WIFI_ACCESS_SWITCHES = "wifi_access_switches"
OPT_URL_FILTER_SWITCHES = "url_filter_switches"
OPT_ROUTER_CLIENTS_SENSORS = "router_clients_sensors"
OPT_DEVICES_TAGS = "devices_tags"
OPT_DEVICE_TRACKER = "device_tracker"
OPT_DEVICE_TRACKER_ZONES = "device_tracker_zones"

DEFAULT_HOST: Final = "192.168.3.1"
DEFAULT_USER: Final = "admin"
DEFAULT_PORT: Final = 80
DEFAULT_SSL: Final = False
DEFAULT_PASS: Final = ""
DEFAULT_NAME: Final = "Huawei Router"
DEFAULT_VERIFY_SSL: Final = False
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_WIFI_ACCESS_SWITCHES: Final = False
DEFAULT_ROUTER_CLIENTS_SENSORS: Final = False
DEFAULT_DEVICES_TAGS: Final = False
DEFAULT_DEVICE_TRACKER: Final = False
DEFAULT_DEVICE_TRACKER_ZONES: Final = False
DEFAULT_URL_FILTER_SWITCHES: Final = False

ATTR_MANUFACTURER: Final = "Huawei"
PLATFORMS: Final = [
    Platform.SWITCH,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]
