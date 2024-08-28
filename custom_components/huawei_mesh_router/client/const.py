from typing import Final

WIFI_SECURITY_OPEN: Final = "none"
WIFI_SECURITY_ENCRYPTED: Final = "tkip"

CONNECTED_VIA_ID_PRIMARY: Final = "primary"

URL_DEVICE_INFO: Final = "api/system/deviceinfo"
URL_DEVICE_TOPOLOGY: Final = "api/device/topology"
URL_GUEST_NETWORK: Final = "api/ntwk/guest_network?type=notshowpassall"
URL_HOST_INFO: Final = "api/system/HostInfo"
URL_PORT_MAPPING: Final = "api/ntwk/portmapping"
URL_REBOOT: Final = "api/service/reboot.cgi"
URL_REPEATER_INFO: Final = "api/ntwk/repeaterinfo"
URL_SWITCH_NFC: Final = "api/bsp/nfc_switch"
URL_SWITCH_WIFI_80211R: Final = "api/ntwk/WlanGuideBasic?type=notshowpassall"
URL_SWITCH_WIFI_TWT: Final = "api/ntwk/WlanGuideBasic?type=notshowpassall"
URL_TIME_CONTROL: Final = "api/ntwk/timecontrol"
URL_URL_FILTER: Final = "api/ntwk/urlfilter"
URL_WAN_INFO: Final = "api/ntwk/wan?type=active"
URL_WANDETECT: Final = "api/ntwk/wandetect"
URL_WLAN_FILTER: Final = "api/ntwk/wlanfilterenhance"
