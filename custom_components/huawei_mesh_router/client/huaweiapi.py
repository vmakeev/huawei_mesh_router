"""Huawei api extended functions."""

import logging
from typing import Any, Final, Iterable, Tuple

from aiohttp import ClientResponse

from .classes import (
    MAC_ADDR,
    Action,
    Feature,
    FilterAction,
    FilterMode,
    Frequency,
    HuaweiClientDevice,
    HuaweiConnectionInfo,
    HuaweiDeviceNode,
    HuaweiFilterInfo,
    HuaweiFilterItem,
    HuaweiGuestNetworkDuration,
    HuaweiGuestNetworkItem,
    HuaweiRouterInfo,
    HuaweiRsaPublicKey,
    HuaweiUrlFilterInfo,
    Switch,
)
from .const import (
    URL_DEVICE_INFO,
    URL_DEVICE_TOPOLOGY,
    URL_GUEST_NETWORK,
    URL_HOST_INFO,
    URL_REBOOT,
    URL_REPEATER_INFO,
    URL_SWITCH_NFC,
    URL_SWITCH_WIFI_80211R,
    URL_SWITCH_WIFI_TWT,
    URL_URL_FILTER,
    URL_WANDETECT,
    URL_WLAN_FILTER,
    URL_WAN_INFO,
    WIFI_SECURITY_ENCRYPTED,
    WIFI_SECURITY_OPEN,
)
from .coreapi import HuaweiCoreApi
from .crypto import rsa_encode
from .utils import HuaweiFeaturesDetector

_STATUS_CONNECTED: Final = "Connected"


# ---------------------------
#   UnsupportedActionError
# ---------------------------
class UnsupportedActionError(Exception):
    def __init__(self, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message

    def __str__(self, *args, **kwargs) -> str:
        """Return str(self)."""
        return self._message


# ---------------------------
#   InvalidActionError
# ---------------------------
class InvalidActionError(Exception):
    def __init__(self, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message

    def __str__(self, *args, **kwargs) -> str:
        """Return str(self)."""
        return self._message


class HuaweiApi:
    def __init__(
        self,
        host: str,
        port: int,
        use_ssl: bool,
        user: str,
        password: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize."""
        self._core_api = HuaweiCoreApi(host, port, use_ssl, user, password, verify_ssl)
        self._is_features_updated = False
        self._logger = logging.getLogger(f"{__name__} ({host})")
        self._features = HuaweiFeaturesDetector(self._core_api, self._logger)
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

    async def is_feature_available(self, feature: Feature) -> bool:
        """Return true if specified feature is known and available."""
        await self._ensure_features_updated()
        return self._features.is_available(feature)

    @staticmethod
    def _router_data_check_authorized(
        response: ClientResponse, result: dict[str, Any]
    ) -> bool:
        if response.status == 404:
            return False
        if result is None or result.get("EmuiVersion", "-") == "-":
            return False
        return True

    @staticmethod
    def _wan_info_check_authorized(
        response: ClientResponse, result: dict[str, Any]
    ) -> bool:
        if response.status == 404:
            return False
        if result is None or result.get("ExternalIPAddress", "-") == "-":
            return False
        return True

    async def get_router_info(self) -> HuaweiRouterInfo:
        """Return the router information."""
        data = await self._core_api.get(
            URL_DEVICE_INFO, check_authorized=HuaweiApi._router_data_check_authorized
        )

        return HuaweiRouterInfo(
            name=data.get("FriendlyName"),
            model=data.get("custinfo", {}).get("CustDeviceName"),
            serial_number=data.get("SerialNumber"),
            software_version=data.get("SoftwareVersion"),
            hardware_version=data.get("HardwareVersion"),
            harmony_os_version=data.get("HarmonyOSVersion"),
            uptime=data.get("UpTime"),
        )

    async def get_wan_connection_info(self) -> HuaweiConnectionInfo:
        data = await self._core_api.get(
            URL_WANDETECT, check_authorized=HuaweiApi._wan_info_check_authorized
        )
        rate_data = await self._core_api.get(URL_WAN_INFO)

        return HuaweiConnectionInfo(
            uptime=data.get("Uptime", 0),
            connected=data.get("Status") == _STATUS_CONNECTED,
            address=data.get("ExternalIPAddress"),
            upload_rate=rate_data.get("UpBandwidth", 0),
            download_rate=rate_data.get("DownBandwidth", 0)
        )

    async def get_switch_state(self, switch: Switch) -> bool:
        """Return the specified switch state."""
        await self._ensure_features_updated()

        if switch == Switch.NFC and self._features.is_available(Feature.NFC):
            data = await self._core_api.get(URL_SWITCH_NFC)
            return data.get("nfcSwitch") == 1

        elif switch == Switch.WIFI_80211R and self._features.is_available(
            Feature.WIFI_80211R
        ):
            data = await self._core_api.get(URL_SWITCH_WIFI_80211R)
            setting_value = data.get("WifiConfig", [{}])[0].get("Dot11REnable")
            return isinstance(setting_value, bool) and setting_value

        elif switch == Switch.WIFI_TWT and self._features.is_available(
            Feature.WIFI_TWT
        ):
            data = await self._core_api.get(URL_SWITCH_WIFI_TWT)
            setting_value = data.get("WifiConfig", [{}])[0].get("TWTEnable")
            return isinstance(setting_value, bool) and setting_value

        elif switch == Switch.WLAN_FILTER and self._features.is_available(
            Feature.WLAN_FILTER
        ):
            _, data = await self.get_wlan_filter_info()
            return data.enabled

        elif switch == Switch.GUEST_NETWORK and self._features.is_available(
            Feature.GUEST_NETWORK
        ):
            data_2g, data_5g = await self.get_guest_network_info()
            return (data_2g is not None and data_2g.enabled) or (
                data_5g is not None and data_5g.enabled
            )

        else:
            raise UnsupportedActionError(f"Unsupported switch: {switch}")

    async def set_switch_state(self, switch: Switch, state: bool) -> None:
        """Set the specified switch state."""
        await self._ensure_features_updated()

        if switch == Switch.NFC and self._features.is_available(Feature.NFC):
            await self._core_api.post(URL_SWITCH_NFC, {"nfcSwitch": 1 if state else 0})

        elif switch == Switch.WIFI_80211R and self._features.is_available(
            Feature.WIFI_80211R
        ):
            await self._core_api.post(
                URL_SWITCH_WIFI_80211R,
                {"Dot11REnable": state},
                extra_data={"action": "11rSetting"},
            )

        elif switch == Switch.WIFI_TWT and self._features.is_available(
            Feature.WIFI_TWT
        ):
            await self._core_api.post(
                URL_SWITCH_WIFI_TWT,
                {"TWTEnable": state},
                extra_data={"action": "TWTSetting"},
            )

        elif switch == Switch.WLAN_FILTER and self._features.is_available(
            Feature.WLAN_FILTER
        ):
            await self._set_wlan_filter_enabled(state)

        elif switch == Switch.GUEST_NETWORK and self._features.is_available(
            Feature.GUEST_NETWORK
        ):
            await self._set_guest_network_enabled(state)

        else:
            raise UnsupportedActionError(f"Unsupported switch: {switch}")

    async def get_known_devices(self) -> Iterable[HuaweiClientDevice]:
        """Return the known devices."""
        return [
            HuaweiClientDevice(item) for item in await self._core_api.get(URL_HOST_INFO)
        ]

    @staticmethod
    def _get_device(node: dict[str, Any]) -> HuaweiDeviceNode:
        device = HuaweiDeviceNode(node.get("MACAddress"), node.get("HiLinkType"))
        connected_devices = node.get("ConnectedDevices", [])
        for connected_device in connected_devices:
            inner_node = HuaweiApi._get_device(connected_device)
            device.add_device(inner_node)
        return device

    async def get_devices_topology(self) -> Iterable[HuaweiDeviceNode]:
        """Return the topology of the devices."""
        return [
            self._get_device(item)
            for item in await self._core_api.get(URL_DEVICE_TOPOLOGY)
        ]

    async def execute_action(self, action: Action) -> None:
        """Execute specified action."""
        if action == Action.REBOOT:
            await self._core_api.post(URL_REBOOT, {})
        else:
            raise UnsupportedActionError(f"Unsupported action name: {action}")

    async def apply_wlan_filter(
        self,
        filter_mode: FilterMode,
        filter_action: FilterAction,
        device_mac: MAC_ADDR,
        device_name: str | None = None,
    ) -> bool:
        """Apply filter to the device."""

        def verify_state(target_state: dict[str, Any]) -> bool:
            enabled = target_state.get("MACAddressControlEnabled")
            verification_result = isinstance(enabled, bool) and enabled
            if not verification_result:
                self._logger.warning("WLAN Filtering is not enabled")
            return verification_result

        state_2g, state_5g = await self._get_filter_states()

        if state_2g is None:
            self._logger.debug("Can not find actual 2.4GHz filter state")
            return False

        if state_5g is None:
            self._logger.debug("Can not find actual 5GHz filter state")
            return False

        if not verify_state(state_2g) or not verify_state(state_5g):
            self._logger.debug("Verification failed")
            return False

        need_action_2g, whitelist_2g, blacklist_2g = await self._process_access_lists(
            state_2g, filter_mode, filter_action, device_mac, device_name
        )
        if whitelist_2g is None or blacklist_2g is None or need_action_2g is None:
            self._logger.debug("Processing 2.4GHz filter failed")
            return False

        need_action_5g, whitelist_5g, blacklist_5g = await self._process_access_lists(
            state_5g, filter_mode, filter_action, device_mac, device_name
        )
        if whitelist_5g is None or blacklist_5g is None or need_action_5g is None:
            self._logger.debug("Processing 5GHz filter failed")
            return False

        if not need_action_2g and not need_action_5g:
            return True

        command = {
            "config2g": {
                "MACAddressControlEnabled": True,
                "WMacFilters": whitelist_2g,
                "ID": state_2g.get("ID"),
                "MacFilterPolicy": state_2g.get("MacFilterPolicy"),
                "BMacFilters": blacklist_2g,
                "FrequencyBand": state_2g.get("FrequencyBand"),
            },
            "config5g": {
                "MACAddressControlEnabled": True,
                "WMacFilters": whitelist_5g,
                "ID": state_5g.get("ID"),
                "MacFilterPolicy": state_5g.get("MacFilterPolicy"),
                "BMacFilters": blacklist_5g,
                "FrequencyBand": state_5g.get("FrequencyBand"),
            },
        }

        await self._core_api.post(URL_WLAN_FILTER, command)
        return True

    async def _set_wlan_filter_enabled(self, value: bool) -> bool:
        """Enable or disable wlan filtering."""

        state_2g, state_5g = await self._get_filter_states()

        if state_2g is None:
            self._logger.debug("Can not find actual 2.4GHz filter state")
            return False

        if state_5g is None:
            self._logger.debug("Can not find actual 5GHz filter state")
            return False

        current_value_2g = state_2g.get("MACAddressControlEnabled")
        current_value_2g = isinstance(current_value_2g, bool) and current_value_2g

        current_value_5g = state_5g.get("MACAddressControlEnabled")
        current_value_5g = isinstance(current_value_5g, bool) and current_value_5g

        current_state = current_value_2g and current_value_5g

        if current_state == value:
            return True

        command = {
            "config2g": {
                "MACAddressControlEnabled": value,
                "WMacFilters": state_2g.get("WMACAddresses"),
                "ID": state_2g.get("ID"),
                "MacFilterPolicy": state_2g.get("MacFilterPolicy"),
                "BMacFilters": state_2g.get("BMACAddresses"),
                "FrequencyBand": state_2g.get("FrequencyBand"),
            },
            "config5g": {
                "MACAddressControlEnabled": value,
                "WMacFilters": state_5g.get("WMACAddresses"),
                "ID": state_5g.get("ID"),
                "MacFilterPolicy": state_5g.get("MacFilterPolicy"),
                "BMacFilters": state_5g.get("BMACAddresses"),
                "FrequencyBand": state_5g.get("FrequencyBand"),
            },
        }

        await self._core_api.post(URL_WLAN_FILTER, command)
        return True

    async def set_wlan_filter_mode(self, value: FilterMode) -> bool:
        """Enable or disable wlan filtering."""

        state_2g, state_5g = await self._get_filter_states()

        if state_2g is None:
            self._logger.debug("Can not find actual 2.4GHz filter state")
            return False

        if state_5g is None:
            self._logger.debug("Can not find actual 5GHz filter state")
            return False

        current_state = state_5g.get("MacFilterPolicy")

        if current_state == value.value:
            return True

        command = {
            "config2g": {
                "MACAddressControlEnabled": state_2g.get("MACAddressControlEnabled"),
                "WMacFilters": state_2g.get("WMACAddresses"),
                "ID": state_2g.get("ID"),
                "MacFilterPolicy": value.value,
                "BMacFilters": state_2g.get("BMACAddresses"),
                "FrequencyBand": state_2g.get("FrequencyBand"),
            },
            "config5g": {
                "MACAddressControlEnabled": state_5g.get("MACAddressControlEnabled"),
                "WMacFilters": state_5g.get("WMACAddresses"),
                "ID": state_5g.get("ID"),
                "MacFilterPolicy": value.value,
                "BMacFilters": state_5g.get("BMACAddresses"),
                "FrequencyBand": state_5g.get("FrequencyBand"),
            },
        }

        await self._core_api.post(URL_WLAN_FILTER, command)
        return True

    async def get_wlan_filter_info(self) -> Tuple[HuaweiFilterInfo, HuaweiFilterInfo]:
        state_2g, state_5g = await self._get_filter_states()
        info_2g = HuaweiFilterInfo.parse(state_2g)
        info_5g = HuaweiFilterInfo.parse(state_5g)
        return info_2g, info_5g

    async def _get_filter_states(self):
        actual_states = await self._core_api.get(URL_WLAN_FILTER)
        state_2g = None
        state_5g = None
        for state in actual_states:
            frequency = state.get("FrequencyBand")
            if frequency == Frequency.WIFI_2_4_GHZ:
                state_2g = state
            elif frequency == Frequency.WIFI_5_GHZ:
                state_5g = state
        return state_2g, state_5g

    async def apply_url_filter_info(self, url_filter_info: HuaweiUrlFilterInfo) -> None:
        actual = await self.get_url_filter_info()
        existing_item = next(
            (item for item in actual if item.filter_id == url_filter_info.filter_id)
        )

        action: str = "update" if existing_item else "create"

        data: dict[str, Any] = {
            "Devices": [
                {"MACAddress": device.mac_address} for device in url_filter_info.devices
            ],
            "DeviceNames": [
                {"HostName": device.name} for device in url_filter_info.devices
            ],
            "DevManual": url_filter_info.dev_manual,
            "URL": url_filter_info.url,
            "Status": 2 if url_filter_info.enabled else 0,
            "ID": url_filter_info.filter_id,
        }

        await self._core_api.post(URL_URL_FILTER, data, extra_data={"action": action})

    async def _process_access_lists(
        self,
        state: dict[str, Any],
        filter_mode: FilterMode,
        filter_action: FilterAction,
        device_mac: MAC_ADDR,
        device_name: str | None,
    ) -> Tuple[bool | None, dict[str, Any] | None, dict[str, Any] | None]:
        """Return (need_action, whitelist, blacklist)"""
        whitelist = state.get("WMACAddresses")
        blacklist = state.get("BMACAddresses")

        if whitelist is None:
            self._logger.debug("Can not find whitelist")
            return None, None, None

        if blacklist is None:
            self._logger.debug("Can not find blacklist")
            return None, None, None

        async def get_access_list_item() -> dict[str, Any]:
            if device_name:
                return {"MACAddress": device_mac, "HostName": device_name}
            # search for HostName if no item popped and no name provided
            known_devices = await self.get_known_devices()
            for device in known_devices:
                if device.mac_address == device_mac:
                    return {"MACAddress": device_mac, "HostName": device.actual_name}
            self._logger.debug("Can not find known device '%s'", device_mac)
            return {
                "MACAddress": device_mac,
                "HostName": f"Unknown device {device_mac}",
            }

        # | FilterAction | FilterMode |    WL    |   BL   |
        # |--------------|------------|----------|--------|
        # | ADD          | WHITELIST  |   Add    | Remove |
        # | ADD          | BLACKLIST  |  Remove  |  Add   |
        # | REMOVE       | WHITELIST  |  Remove  |  None  |
        # | REMOVE       | BLACKLIST  |   None   | Remove |

        whitelist_index: int | None = None
        blacklist_index: int | None = None

        for index in range(len(whitelist)):
            if device_mac == whitelist[index].get("MACAddress"):
                whitelist_index = index
                self._logger.debug(
                    "Device '%s' found at %s whitelist",
                    device_mac,
                    state.get("FrequencyBand"),
                )
                break

        for index in range(len(blacklist)):
            if device_mac == blacklist[index].get("MACAddress"):
                blacklist_index = index
                self._logger.debug(
                    "Device '%s' found at %s blacklist",
                    device_mac,
                    state.get("FrequencyBand"),
                )
                break

        if filter_action == FilterAction.REMOVE:
            if filter_mode == FilterMode.BLACKLIST:
                if blacklist_index is None:
                    self._logger.debug(
                        "Can not find device '%s' to remove from blacklist", device_mac
                    )
                    return False, whitelist, blacklist
                del blacklist[blacklist_index]
                return True, whitelist, blacklist
            elif filter_mode == FilterMode.WHITELIST:
                if whitelist_index is None:
                    self._logger.debug(
                        "Can not find device '%s' to remove from whitelist", device_mac
                    )
                    return False, whitelist, blacklist
                del whitelist[whitelist_index]
                return True, whitelist, blacklist
            else:
                raise InvalidActionError(f"Unknown FilterMode: {filter_mode}")

        elif filter_action == FilterAction.ADD:
            item_to_add = None

            if filter_mode == FilterMode.BLACKLIST:
                if whitelist_index is not None:
                    item_to_add = whitelist.pop(whitelist_index)
                if blacklist_index is not None:
                    self._logger.debug(
                        "Device '%s' already in the %s blacklist",
                        device_mac,
                        state.get("FrequencyBand"),
                    )
                    return False, whitelist, blacklist
                else:
                    blacklist.append(item_to_add or await get_access_list_item())
                    return True, whitelist, blacklist

            if filter_mode == FilterMode.WHITELIST:
                if blacklist_index is not None:
                    item_to_add = blacklist.pop(blacklist_index)
                if whitelist_index is not None:
                    self._logger.debug(
                        "Device '%s' already in the %s whitelist",
                        device_mac,
                        state.get("FrequencyBand"),
                    )
                    return False, whitelist, blacklist
                else:
                    whitelist.append(item_to_add or await get_access_list_item())
                    return True, whitelist, blacklist
            else:
                raise InvalidActionError(f"Unknown FilterMode: {filter_mode}")

        else:
            raise InvalidActionError(f"Unknown FilterAction: {filter_action}")

    async def get_is_repeater(self) -> bool:
        data = await self._core_api.get(URL_REPEATER_INFO)

        if data is None:
            return False

        repeater_enable = data.get("RepeaterEnable", False)

        return isinstance(repeater_enable, bool) and repeater_enable

    @staticmethod
    def _to_url_filter_info(data: dict[str, Any]) -> HuaweiUrlFilterInfo:
        result = HuaweiUrlFilterInfo(
            filter_id=data["ID"],
            url=data["URL"],
            enabled=data.get("Status", -1) == 2,
            dev_manual=data.get("DevManual") is True,
            devices=[
                HuaweiFilterItem(item[0].get("MACAddress"), item[1].get("HostName"))
                for item in zip(data["Devices"], data["DeviceNames"])
            ],
        )

        return result

    async def get_url_filter_info(self) -> Iterable[HuaweiUrlFilterInfo]:
        data = await self._core_api.get(URL_URL_FILTER)
        return [self._to_url_filter_info(item) for item in data]

    @staticmethod
    def _to_huawei_guest_network_item(source: dict[str, Any]):
        return HuaweiGuestNetworkItem(
            item_id=source["ID"],
            enabled=source["EnableFrequency"] is True,
            sec_opt=source["SecOpt"],
            can_enable=source["CanEnableFrequency"] is True,
            pwd_score=source["PwdScore"],
            valid_time=HuaweiGuestNetworkDuration(source["ValidTime"]),
            ssid=source["WifiSsid"],
            key=source["WpaPreSharedKey"],
            frequency=source["FrequencyBand"],
            rest_rime=source["RestTime"],
        )

    async def get_guest_network_info(
        self,
    ) -> Tuple[HuaweiGuestNetworkItem, HuaweiGuestNetworkItem]:
        data = await self._core_api.get(URL_GUEST_NETWORK)
        item_2g = None
        item_5g = None

        for item in data:
            if item.get("FrequencyBand") == Frequency.WIFI_2_4_GHZ:
                item_2g = item
            elif item.get("FrequencyBand") == Frequency.WIFI_5_GHZ:
                item_5g = item

        result_2g = None if not item_2g else self._to_huawei_guest_network_item(item_2g)
        result_5g = None if not item_5g else self._to_huawei_guest_network_item(item_5g)
        return result_2g, result_5g

    @staticmethod
    def _to_guest_wifi_config(
        current_item: HuaweiGuestNetworkItem,
        rsa_key: HuaweiRsaPublicKey,
        enabled: bool,
        ssid: str,
        duration: HuaweiGuestNetworkDuration,
        secure: bool,
        password: str | None,
    ) -> dict[str, Any]:
        if secure and not password:
            raise InvalidActionError("Password must be specified")

        return {
            "ID": current_item.item_id,
            "Enable": enabled and current_item.can_enable,
            "WifiSsid": ssid,
            "ValidTime": duration.value,
            "SecOpt": WIFI_SECURITY_OPEN if not secure else WIFI_SECURITY_ENCRYPTED,
            "WpaPreSharedKey": rsa_encode(password, rsa_key),
        }

    async def set_guest_network_state(
        self,
        enabled: bool,
        ssid: str,
        duration: HuaweiGuestNetworkDuration,
        secure: bool,
        password: str | None,
    ) -> None:
        rsa_key = self._core_api.rsa_key
        if not rsa_key:
            raise InvalidActionError("Can not obtain RSA public key")

        actual_2g, actual_5g = await self.get_guest_network_info()

        config2g = self._to_guest_wifi_config(
            actual_2g, rsa_key, enabled, ssid, duration, secure, password
        )
        config5g = self._to_guest_wifi_config(
            actual_5g, rsa_key, enabled, ssid, duration, secure, password
        )

        data = {"config5g": config5g, "config2g": config2g}

        await self._core_api.post(
            URL_GUEST_NETWORK,
            data,
            headers={"Content-Type": "application/json;charset=UTF-8;enp"},
        )

    async def _set_guest_network_enabled(self, enabled: bool) -> None:
        actual_2g, actual_5g = await self.get_guest_network_info()

        actual_enabled = (actual_2g is not None and actual_2g.enabled) or (
            actual_5g is not None and actual_5g.enabled
        )

        if actual_enabled == enabled:
            return

        primary_item = None

        for item in await self.get_guest_network_info():
            if item.can_enable:
                primary_item = item
                break

        if not primary_item:
            raise InvalidActionError("No one frequency can be enabled")

        await self.set_guest_network_state(
            enabled=enabled,
            ssid=primary_item.ssid,
            duration=primary_item.valid_time,
            secure=primary_item.sec_opt != WIFI_SECURITY_OPEN,
            password=primary_item.key,
        )
