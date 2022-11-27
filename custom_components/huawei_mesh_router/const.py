from homeassistant.const import Platform

DOMAIN = "huawei_mesh_router"

STORAGE_VERSION = 1

DEFAULT_HOST = "192.168.3.1"
DEFAULT_USER = "admin"
DEFAULT_PORT = 80
DEFAULT_SSL = False
DEFAULT_PASS = ""
DEFAULT_NAME = "Huawei Mesh 3"
DEFAULT_VERIFY_SSL = False
DEFAULT_SCAN_INTERVAL = 30

ATTR_MANUFACTURER = "Huawei"
PLATFORMS = [Platform.SWITCH, Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.BUTTON]
