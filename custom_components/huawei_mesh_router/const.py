"""Huawei Mesh Router shared constants."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "huawei_mesh_router"

STORAGE_VERSION: Final = 1

DEFAULT_HOST: Final = "192.168.3.1"
DEFAULT_USER: Final = "admin"
DEFAULT_PORT: Final = 80
DEFAULT_SSL: Final = False
DEFAULT_PASS: Final = ""
DEFAULT_NAME: Final = "Huawei Router"
DEFAULT_VERIFY_SSL: Final = False
DEFAULT_SCAN_INTERVAL: Final = 30

ATTR_MANUFACTURER: Final = "Huawei"
PLATFORMS: Final = [Platform.SWITCH, Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR]
