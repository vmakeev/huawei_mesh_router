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
PLATFORMS = [Platform.SWITCH, Platform.DEVICE_TRACKER, Platform.SENSOR]

SWITCHES_NFC = "nfc_switch"
SWITCHES_WIFI_80211R = "wifi_80211r_switch"
SWITCHES_WIFI_TWT = "wifi_twt_switch"

VENDOR_CLASS_ID_ROUTER = "router"

CONNECTED_VIA_ID_PRIMARY = "primary"
