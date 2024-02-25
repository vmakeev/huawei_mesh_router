from functools import wraps
import logging

from .classes import Feature
from .const import (
    URL_DEVICE_TOPOLOGY,
    URL_GUEST_NETWORK,
    URL_PORT_MAPPING,
    URL_SWITCH_NFC,
    URL_SWITCH_WIFI_80211R,
    URL_SWITCH_WIFI_TWT,
    URL_URL_FILTER,
    URL_WLAN_FILTER,
)
from .coreapi import APICALL_ERRCAT_UNAUTHORIZED, ApiCallError, HuaweiCoreApi

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   HuaweiFeaturesDetector
# ---------------------------
class HuaweiFeaturesDetector:
    def __init__(self, core_api: HuaweiCoreApi, logger: logging.Logger):
        """Initialize."""
        self._core_api = core_api
        self._logger = logger
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
    def log_feature(feature: Feature):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    _LOGGER.debug("Check feature '%s' availability", feature)
                    result = await func(*args, **kwargs)
                    if result:
                        _LOGGER.debug("Feature '%s' is available", feature)
                    else:
                        _LOGGER.debug("Feature '%s' is not available", feature)
                    return result
                except Exception:
                    _LOGGER.debug("Feature availability check failed on %s", feature)
                    raise

            return wrapper

        return decorator

    @log_feature(Feature.NFC)
    @unauthorized_as_false
    async def _is_nfc_available(self) -> bool:
        data = await self._core_api.get(URL_SWITCH_NFC)
        return data.get("nfcSwitch") is not None

    @log_feature(Feature.WIFI_80211R)
    @unauthorized_as_false
    async def _is_wifi_80211r_available(self) -> bool:
        data = await self._core_api.get(URL_SWITCH_WIFI_80211R)
        return data.get("WifiConfig", [{}])[0].get("Dot11REnable") is not None

    @log_feature(Feature.WIFI_TWT)
    @unauthorized_as_false
    async def _is_wifi_twt_available(self) -> bool:
        data = await self._core_api.get(URL_SWITCH_WIFI_TWT)
        return data.get("WifiConfig", [{}])[0].get("TWTEnable") is not None

    @log_feature(Feature.WLAN_FILTER)
    @unauthorized_as_false
    async def _is_wlan_filter_available(self) -> bool:
        data = await self._core_api.get(URL_WLAN_FILTER)
        return data is not None

    @log_feature(Feature.DEVICE_TOPOLOGY)
    @unauthorized_as_false
    async def _is_device_topology_available(self) -> bool:
        data = await self._core_api.get(URL_DEVICE_TOPOLOGY)
        return data is not None

    @log_feature(Feature.URL_FILTER)
    @unauthorized_as_false
    async def _is_url_filter_available(self) -> bool:
        data = await self._core_api.get(URL_URL_FILTER)
        return data is not None

    @log_feature(Feature.GUEST_NETWORK)
    @unauthorized_as_false
    async def _is_guest_network_available(self) -> bool:
        data = await self._core_api.get(URL_GUEST_NETWORK)
        return data is not None

    @log_feature(Feature.PORT_MAPPING)
    @unauthorized_as_false
    async def _is_port_mapping_available(self) -> bool:
        data = await self._core_api.get(URL_PORT_MAPPING)
        return data is not None

    async def update(self) -> None:
        """Update the available features list."""
        if await self._is_nfc_available():
            self._available_features.add(Feature.NFC)

        if await self._is_wifi_80211r_available():
            self._available_features.add(Feature.WIFI_80211R)

        if await self._is_wifi_twt_available():
            self._available_features.add(Feature.WIFI_TWT)

        if await self._is_wlan_filter_available():
            self._available_features.add(Feature.WLAN_FILTER)

        if await self._is_device_topology_available():
            self._available_features.add(Feature.DEVICE_TOPOLOGY)

        if await self._is_url_filter_available():
            self._available_features.add(Feature.URL_FILTER)

        if await self._is_guest_network_available():
            self._available_features.add(Feature.GUEST_NETWORK)

        if await self._is_port_mapping_available():
            self._available_features.add(Feature.PORT_MAPPING)

    def is_available(self, feature: Feature) -> bool:
        """Return true if feature is available."""
        return feature in self._available_features
