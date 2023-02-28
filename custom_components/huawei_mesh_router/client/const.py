from typing import Final

WIFI_SECURITY_OPEN: Final = "none"
WIFI_SECURITY_ENCRYPTED: Final = "tkip"

SWITCH_NFC: Final = "nfc_switch"
SWITCH_WIFI_80211R: Final = "wifi_80211r_switch"
SWITCH_WIFI_TWT: Final = "wifi_twt_switch"
SWITCH_WLAN_FILTER: Final = "wlan_filter_switch"
SWITCH_URL_FILTER: Final = "url_filter_switch"
SWITCH_GUEST_NETWORK: Final = "guest_network_switch"

FREQUENCY_2_4_GHZ: Final = "2.4GHz"
FREQUENCY_5_GHZ: Final = "5GHz"

ACTION_REBOOT: Final = "reboot_action"

CONNECTED_VIA_ID_PRIMARY: Final = "primary"

FEATURE_NFC: Final = "feature_nfc"
FEATURE_URL_FILTER: Final = "feature_url_filter"
FEATURE_WIFI_80211R: Final = "feature_wifi_80211r"
FEATURE_WIFI_TWT: Final = "feature_wifi_twt"
FEATURE_WLAN_FILTER: Final = "feature_wlan_filter"
FEATURE_DEVICE_TOPOLOGY: Final = "feature_device_topology"
FEATURE_GUEST_NETWORK: Final = "feature_guest_network"

URL_DEVICE_INFO: Final = "api/system/deviceinfo"
URL_DEVICE_TOPOLOGY: Final = "api/device/topology"
URL_HOST_INFO: Final = "api/system/HostInfo"
URL_SWITCH_NFC: Final = "api/bsp/nfc_switch"
URL_SWITCH_WIFI_80211R: Final = "api/ntwk/WlanGuideBasic?type=notshowpassall"
URL_SWITCH_WIFI_TWT: Final = "api/ntwk/WlanGuideBasic?type=notshowpassall"
URL_REBOOT: Final = "api/service/reboot.cgi"
URL_REPEATER_INFO: Final = "api/ntwk/repeaterinfo"
URL_WANDETECT: Final = "api/ntwk/wandetect"
URL_WLAN_FILTER: Final = "api/ntwk/wlanfilterenhance"
URL_URL_FILTER: Final = "api/ntwk/urlfilter"
URL_GUEST_NETWORK: Final = "api/ntwk/guest_network?type=notshowpassall"
