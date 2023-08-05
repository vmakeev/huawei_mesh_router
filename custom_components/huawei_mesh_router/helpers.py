"""Helpful common functions."""

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import generate_entity_id as hass_generate_id
import homeassistant.util.dt as dt

from .client.classes import MAC_ADDR
from .const import DATA_KEY_COORDINATOR, DATA_KEY_PLATFORMS, DOMAIN
from .update_coordinator import HuaweiDataUpdateCoordinator


class ConfigurationError(Exception):
    def __init__(self, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message

    def __str__(self, *args, **kwargs) -> str:
        """Return str(self)."""
        return self._message


# ---------------------------
#   get_coordinator
# ---------------------------
def get_coordinator(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> HuaweiDataUpdateCoordinator:
    result = (
        hass.data.get(DOMAIN, {})
        .get(config_entry.entry_id, {})
        .get(DATA_KEY_COORDINATOR)
    )
    if not result:
        raise ConfigurationError(f"Coordinator not found at {config_entry.entry_id}")
    return result


# ---------------------------
#   pop_coordinator
# ---------------------------
def pop_coordinator(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> HuaweiDataUpdateCoordinator | None:
    data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})
    if DATA_KEY_COORDINATOR in data:
        return data.pop(DATA_KEY_COORDINATOR)
    return None


# ---------------------------
#   set_coordinator
# ---------------------------
def set_coordinator(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    coordinator: HuaweiDataUpdateCoordinator,
) -> None:
    hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})[
        DATA_KEY_COORDINATOR
    ] = coordinator


# ---------------------------
#   set_loaded_platforms
# ---------------------------
def set_loaded_platforms(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    platforms: list[str],
) -> None:
    hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})[
        DATA_KEY_PLATFORMS
    ] = platforms


# ---------------------------
#   get_loaded_platforms
# ---------------------------
def get_loaded_platforms(hass: HomeAssistant, config_entry: ConfigEntry) -> list[str]:
    result = (
        hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get(DATA_KEY_PLATFORMS)
    )
    if not result:
        raise ConfigurationError(
            f"Loaded plaforms not found at {config_entry.entry_id}"
        )
    return result


# ---------------------------
#   get_past_moment
# ---------------------------
def get_past_moment(offset_seconds: int) -> datetime:
    return dt.now().replace(microsecond=0) - timedelta(seconds=offset_seconds)


# ---------------------------
#   generate_entity_name
# ---------------------------
def generate_entity_name(function_displayed_name: str, device_name: str | None = None) -> str:
    return f"{device_name} {function_displayed_name}" if device_name else function_displayed_name


# ---------------------------
#   generate_entity_id
# ---------------------------
def generate_entity_id(
    coordinator: HuaweiDataUpdateCoordinator,
    entity_domain: str,
    function_displayed_name: str,
    device_name: str | None = None,
) -> str:
    preferred_id = (
        f"{coordinator.name} {function_displayed_name} {device_name}"
        if device_name
        else f"{coordinator.name} {function_displayed_name}"
    )
    return hass_generate_id(entity_domain + ".{}", preferred_id, hass=coordinator.hass)


# ---------------------------
#   generate_entity_unique_id
# ---------------------------
def generate_entity_unique_id(
    coordinator: HuaweiDataUpdateCoordinator,
    function_uid: str,
    device_mac: MAC_ADDR | None = None,
) -> str:
    prefix = coordinator.unique_id
    suffix = (
        coordinator.get_router_info().serial_number if not device_mac else device_mac
    )
    return f"{prefix}_{function_uid}_{suffix.lower()}"
