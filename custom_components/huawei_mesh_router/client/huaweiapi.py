from aiohttp import ClientResponse
import logging
from typing import Any, Iterable
from functools import wraps

from .coreapi import HuaweiCoreApi, ApiCallError, APICALL_ERRCAT_UNAUTHORIZED
from .classes import HuaweiRouterInfo, HuaweiClientDevice, HuaweiDeviceNode

SWITCH_NFC = "nfc_switch"
SWITCH_WIFI_80211R = "wifi_80211r_switch"
SWITCH_WIFI_TWT = "wifi_twt_switch"

ACTION_REBOOT = "reboot_action"

CONNECTED_VIA_ID_PRIMARY = "primary"

FEATURE_NFC = "feature_nfc"
FEATURE_WIFI_80211R = "feature_wifi_80211r"
FEATURE_WIFI_TWT = "feature_wifi_twt"

_URL_DEVICE_INFO = "api/system/deviceinfo"
_URL_HOST_INFO = "api/system/HostInfo"
_URL_DEVICE_TOPOLOGY = "api/device/topology"
_URL_SWITCH_NFC = "api/bsp/nfc_switch"
_URL_SWITCH_WIFI_80211R = "api/ntwk/WlanGuideBasic?type=notshowpassall"
_URL_SWITCH_WIFI_TWT = "api/ntwk/WlanGuideBasic?type=notshowpassall"

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   UnsupportedActionError
# ---------------------------
class UnsupportedActionError(Exception):

    def __init__(self, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message

    def __str__(self, *args, **kwargs) -> str:
        """ Return str(self). """
        return self._message


# ---------------------------
#   HuaweiFeaturesDetector
# ---------------------------
class HuaweiFeaturesDetector:
    def __init__(self, core_api: HuaweiCoreApi):
        """Initialize."""
        self._core_api = core_api
        self._available_features = set()
        self._is_initialized = False

    @staticmethod
    def unauthorized_as_false(func):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> bool:
            try:
                return await func(*args, **kwargs)
            except ApiCallError as ace:
                if ace.category == APICALL_ERRCAT_UNAUTHORIZED:
                    return False
                raise

        return wrapper

    @staticmethod
    def log_feature(feature_name: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    _LOGGER.debug("Check feature '%s' availability", feature_name)
                    result = await func(*args, **kwargs)
                    if result:
                        _LOGGER.debug("Feature '%s' is available", feature_name)
                    else:
                        _LOGGER.debug("Feature '%s' is not available", feature_name)
                    return result
                except Exception:
                    _LOGGER.debug("Feature availability check failed on %s", feature_name)
                    raise

            return wrapper

        return decorator

    @log_feature(FEATURE_NFC)
    @unauthorized_as_false
    async def _is_nfc_available(self) -> bool:
        data = await self._core_api.get(_URL_SWITCH_NFC)
        return data.get('nfcSwitch') is not None

    @log_feature(FEATURE_WIFI_80211R)
    @unauthorized_as_false
    async def _is_wifi_80211r_available(self) -> bool:
        data = await self._core_api.get(_URL_SWITCH_WIFI_80211R)
        return data.get('WifiConfig', [{}])[0].get('Dot11REnable') is not None

    @log_feature(FEATURE_WIFI_TWT)
    @unauthorized_as_false
    async def _is_wifi_twt_available(self) -> bool:
        data = await self._core_api.get(_URL_SWITCH_WIFI_TWT)
        return data.get('WifiConfig', [{}])[0].get('TWTEnable') is not None

    async def update(self) -> None:
        """Update the available features list."""
        if await self._is_nfc_available():
            self._available_features.add(FEATURE_NFC)

        if await self._is_wifi_80211r_available():
            self._available_features.add(FEATURE_WIFI_80211R)

        if await self._is_wifi_twt_available():
            self._available_features.add(FEATURE_WIFI_TWT)

    def is_available(self, feature: str) -> bool:
        """Return true if feature is available."""
        return feature in self._available_features


# ---------------------------
#   HuaweiApi
# ---------------------------
class HuaweiApi:

    def __init__(
            self,
            host: str,
            port: int,
            use_ssl: bool,
            user: str,
            password: str,
            verify_ssl: bool
    ) -> None:
        """Initialize."""
        self._core_api = HuaweiCoreApi(host, port, use_ssl, user, password, verify_ssl)
        self._is_features_updated = False
        self._features = HuaweiFeaturesDetector(self._core_api)
        self._logger = logging.getLogger(f"{__name__} ({host})")
        self._logger.debug("New instance of HuaweiApi created")

    async def authenticate(self) -> None:
        """Perform authentication."""
        await self._core_api.authenticate()

    async def disconnect(self) -> None:
        """Disconnect from api."""
        await self._core_api.disconnect()

    async def _ensure_features_updated(self):
        if not self._is_features_updated:
            self._logger.debug("Updating available features")
            await self._features.update()
            self._is_features_updated = True
            self._logger.debug("Available features updated")

    @property
    def router_url(self) -> str:
        """URL address of the router."""
        return self._core_api.router_url

    async def is_feature_available(self, feature: str) -> bool:
        """Return true if specified feature is known and available."""
        await self._ensure_features_updated()
        return self._features.is_available(feature)

    @staticmethod
    def _router_data_check_authorized(response: ClientResponse, result: dict[str, Any]) -> bool:
        if response.status == 404:
            return False
        if result is None or result.get("EmuiVersion", "-") == "-":
            return False
        return True

    async def get_router_info(self) -> HuaweiRouterInfo:
        """Return the router information."""
        data = await self._core_api.get(
            _URL_DEVICE_INFO,
            check_authorized=HuaweiApi._router_data_check_authorized
        )

        return HuaweiRouterInfo(
            name=data.get("FriendlyName"),
            model=data.get("cust_device_name"),
            serial_number=data.get("SerialNumber"),
            software_version=data.get("SoftwareVersion"),
            hardware_version=data.get("HardwareVersion"),
            harmony_os_version=data.get('HarmonyOSVersion')
        )

    async def get_switch_state(self, name: str) -> bool:
        """Return the specified switch state."""
        await self._ensure_features_updated()

        if name == SWITCH_NFC and self._features.is_available(FEATURE_NFC):
            data = await self._core_api.get(_URL_SWITCH_NFC)
            return data.get('nfcSwitch') == 1

        elif name == SWITCH_WIFI_80211R and self._features.is_available(FEATURE_WIFI_80211R):
            data = await self._core_api.get(_URL_SWITCH_WIFI_80211R)
            setting_value = data.get('WifiConfig', [{}])[0].get('Dot11REnable')
            return isinstance(setting_value, bool) and setting_value

        elif name == SWITCH_WIFI_TWT and self._features.is_available(FEATURE_WIFI_TWT):
            data = await self._core_api.get(_URL_SWITCH_WIFI_TWT)
            setting_value = data.get('WifiConfig', [{}])[0].get('TWTEnable')
            return isinstance(setting_value, bool) and setting_value

        else:
            raise UnsupportedActionError(f"Unsupported switch name: {name}")

    async def set_switch_state(self, name: str, state: bool) -> None:
        """Set the specified switch state."""
        await self._ensure_features_updated()

        if name == SWITCH_NFC and self._features.is_available(FEATURE_NFC):
            await self._core_api.post(_URL_SWITCH_NFC, {"nfcSwitch": 1 if state else 0})

        elif name == SWITCH_WIFI_80211R and self._features.is_available(FEATURE_WIFI_80211R):
            await self._core_api.post(
                _URL_SWITCH_WIFI_80211R,
                {"Dot11REnable": state},
                extra_data={"action": "11rSetting"}
            )

        elif name == SWITCH_WIFI_TWT and self._features.is_available(FEATURE_WIFI_TWT):
            await self._core_api.post(
                _URL_SWITCH_WIFI_TWT,
                {"TWTEnable": state},
                extra_data={"action": "TWTSetting"}
            )
        else:
            raise UnsupportedActionError(f"Unsupported switch name: {name}")

    async def get_known_devices(self) -> Iterable[HuaweiClientDevice]:
        """Return the known devices."""
        return [HuaweiClientDevice(item) for item in await self._core_api.get(_URL_HOST_INFO)]

    @staticmethod
    def _get_device(node: dict[str, Any]) -> HuaweiDeviceNode:
        device = HuaweiDeviceNode(node.get("MACAddress"), node.get("HiLinkType"))
        connected_devices = node.get("ConnectedDevices", [])
        for connected_device in connected_devices:
            inner_node = HuaweiApi._get_device(connected_device)
            device.add_device(inner_node)
        return device

    async def get_devices_topology(self) -> Iterable[HuaweiDeviceNode]:
        """Return the devices topology."""
        return [self._get_device(item) for item in await self._core_api.get(_URL_DEVICE_TOPOLOGY)]

    async def execute_action(self, action_name: str) -> None:
        """Execute specified action."""
        if action_name == ACTION_REBOOT:
            await self._core_api.post('api/service/reboot.cgi', {})
        else:
            raise UnsupportedActionError(f"Unsupported action name: {action_name}")
