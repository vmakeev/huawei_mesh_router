"""Huawei router switches."""
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import (
    DOMAIN,
    SWITCHES_NFC,
    SWITCHES_WIFI_80211R,
    SWITCHES_WIFI_TWT,
)
from .connected_device import ConnectedDevice
from .update_coordinator import HuaweiControllerDataUpdateCoordinator, RoutersWatcher
from homeassistant.core import callback, HomeAssistant

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    """Set up switches for Huawei Router component."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    switches = [
        HuaweiNfcSwitch(coordinator, config_entry, None),
        HuaweiWifi80211RSwitch(coordinator, config_entry),
        HuaweiWifiTWTSwitch(coordinator, config_entry),
    ]
    async_add_entities(switches)

    watcher: RoutersWatcher = RoutersWatcher()

    @callback
    def on_router_added(_, router: ConnectedDevice) -> None:
        """When a new mesh router is detected."""
        entity = HuaweiNfcSwitch(coordinator, config_entry, router)
        async_add_entities([entity])

    @callback
    def on_router_removed(er: EntityRegistry, mac: str, _) -> None:
        """When a known mesh router becomes unavailable."""
        unique_id = f"nfc_{mac}_{coordinator.router_info.serial_number}"
        entity_id = er.async_get_entity_id(Platform.SWITCH, DOMAIN, unique_id)
        if entity_id:
            er.async_remove(entity_id)
        else:
            _LOGGER.warning("Can not remove unavailable switch '%s': entity id not found.", unique_id)

    @callback
    def coordinator_updated() -> None:
        """Update the status of the device."""
        watcher.watch_for_changes(coordinator, on_router_added, on_router_removed)

    config_entry.async_on_unload(coordinator.async_add_listener(coordinator_updated))
    coordinator_updated()


# ---------------------------
#   HuaweiSwitch
# ---------------------------
class HuaweiSwitch(CoordinatorEntity[HuaweiControllerDataUpdateCoordinator], SwitchEntity, ABC):
    _update_url: str

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            config_entry: ConfigEntry,
            switch_name: str,
            device_mac: str | None
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._switch_name: str = switch_name if not device_mac else f"{switch_name}_{device_mac}"
        self._device_mac: str = device_mac
        self._config_entry = config_entry
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        _LOGGER.debug("%s added to hass", self._switch_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool:
        """Return current status."""
        return self.coordinator.switches.get(self._switch_name, False)

    @abstractmethod
    def _get_payload(self, value: bool) -> Dict:
        """Get API request payload."""
        raise NotImplementedError()

    def _get_extra_data(self, value: bool) -> Dict | None:
        """Get API request additional data."""
        return None

    async def __go_to_state(self, state: bool):
        """Perform transition to the specified state."""
        await self.coordinator.async_set_value(path=self._update_url,
                                               value=self._get_payload(state),
                                               extra_data=self._get_extra_data(state),
                                               device_mac=self._device_mac)
        self.coordinator.switches[self._switch_name] = state
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """async_turn_off."""
        await self.__go_to_state(False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """async_turn_on."""
        await self.__go_to_state(True)

    def turn_on(self, **kwargs: Any) -> None:
        """turn_on."""
        return asyncio.run_coroutine_threadsafe(
            self.async_turn_on(**kwargs), self.hass.loop
        ).result()

    def turn_off(self, **kwargs: Any) -> None:
        """turn_off."""
        return asyncio.run_coroutine_threadsafe(
            self.async_turn_off(**kwargs), self.hass.loop
        ).result()


# ---------------------------
#   HuaweiNfcSwitch
# ---------------------------
class HuaweiNfcSwitch(HuaweiSwitch):

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            config_entry: ConfigEntry,
            device: ConnectedDevice | None
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, config_entry, SWITCHES_NFC, device.mac if device else None)

        self._attr_name = f"{self.coordinator.name} Nfc ({device.name if device else 'primary router'})"
        self._attr_unique_id = f"nfc_{'' if not device else device.mac + '_'}{self.coordinator.router_info.serial_number}"
        self._attr_icon = "mdi:nfc"
        self._update_url = "api/bsp/nfc_switch"

    def _get_payload(self, value: bool) -> Dict:
        """Get API request payload."""
        return {"nfcSwitch": 1 if value else 0}


# ---------------------------
#   HuaweiWifi80211RSwitch
# ---------------------------
class HuaweiWifi80211RSwitch(HuaweiSwitch):

    def __init__(
            self,
            coordinator: HuaweiControllerDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, config_entry, SWITCHES_WIFI_80211R, None)
        self._attr_name = f"{self.coordinator.name} WiFi 802.11r"
        self._attr_unique_id = f"wifi_802_11_r_{self.coordinator.router_info.serial_number}"
        self._attr_icon = "mdi:wifi-settings"
        self._update_url = "api/ntwk/WlanGuideBasic?type=notshowpassall"

    def _get_payload(self, value: bool) -> Dict:
        """Get API request payload."""
        return {"Dot11REnable": value}

    def _get_extra_data(self, value: bool) -> Dict | None:
        """Get API request additional data."""
        return {"action": "11rSetting"}


# ---------------------------
#   HuaweiWifiTWTSwitch
# ---------------------------
class HuaweiWifiTWTSwitch(HuaweiSwitch):

    def __init__(self, coordinator: HuaweiControllerDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, config_entry, SWITCHES_WIFI_TWT, None)

        self._attr_name = f"{self.coordinator.name} WiFi 6 TWT"
        self._attr_unique_id = f"wifi_twt_{self.coordinator.router_info.serial_number}"
        self._attr_icon = "mdi:wifi-settings"
        self._update_url = "api/ntwk/WlanGuideBasic?type=notshowpassall"

    def _get_payload(self, value: bool) -> Dict:
        """Get API request payload."""
        return {"TWTEnable": value}

    def _get_extra_data(self, value: bool) -> Dict | None:
        """Get API request additional data."""
        return {"action": "TWTSetting"}
