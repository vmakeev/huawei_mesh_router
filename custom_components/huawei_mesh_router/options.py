from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import (
    DEFAULT_DEVICE_TRACKER,
    DEFAULT_DEVICE_TRACKER_ZONES,
    DEFAULT_DEVICES_TAGS,
    DEFAULT_ROUTER_CLIENTS_SENSORS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WIFI_ACCESS_SWITCHES,
    OPT_DEVICE_TRACKER,
    OPT_DEVICE_TRACKER_ZONES,
    OPT_DEVICES_TAGS,
    OPT_ROUTER_CLIENTS_SENSORS,
    OPT_WIFI_ACCESS_SWITCHES,
)


# ---------------------------
#   get_option
# ---------------------------
def get_option(
    config_entry: ConfigEntry, name: str, default: Any | None = None
) -> Any | None:
    return config_entry.options.get(name, default)


# ---------------------------
#   HuaweiOptions
# ---------------------------
class HuaweiIntegrationOptions:
    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._config_entry = config_entry

    @property
    def update_interval(self) -> int:
        """Return option 'update interval' value"""
        return get_option(self._config_entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    @property
    def wifi_access_switches(self) -> bool:
        """Return option 'Wi-Fi access switches' value"""
        return get_option(
            self._config_entry, OPT_WIFI_ACCESS_SWITCHES, DEFAULT_WIFI_ACCESS_SWITCHES
        )

    @property
    def devices_tags(self) -> bool:
        """Return option 'devices tags' value"""
        return get_option(self._config_entry, OPT_DEVICES_TAGS, DEFAULT_DEVICES_TAGS)

    @property
    def device_tracker(self) -> bool:
        """Return option 'device tracker' value"""
        return get_option(
            self._config_entry, OPT_DEVICE_TRACKER, DEFAULT_DEVICE_TRACKER
        )

    @property
    def device_tracker_zones(self) -> bool:
        """Return option 'device tracker zones' value"""
        return get_option(
            self._config_entry, OPT_DEVICE_TRACKER_ZONES, DEFAULT_DEVICE_TRACKER_ZONES
        )

    @property
    def router_clients_sensors(self) -> bool:
        """Return option 'router clients sensors' value"""
        return get_option(
            self._config_entry,
            OPT_ROUTER_CLIENTS_SENSORS,
            DEFAULT_ROUTER_CLIENTS_SENSORS,
        )
