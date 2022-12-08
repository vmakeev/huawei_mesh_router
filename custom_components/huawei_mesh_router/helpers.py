"""Helpful common functions."""

from datetime import datetime, timedelta

from homeassistant.helpers.entity import generate_entity_id as hass_generate_id
import homeassistant.util.dt as dt

from .client.classes import MAC_ADDR
from .update_coordinator import HuaweiControllerDataUpdateCoordinator


# ---------------------------
#   get_past_moment
# ---------------------------
def get_past_moment(offset_seconds: int) -> datetime:
    return dt.now().replace(microsecond=0) - timedelta(seconds=offset_seconds)


# ---------------------------
#   generate_entity_name
# ---------------------------
def generate_entity_name(
        function_displayed_name: str,
        device_name: str
) -> str:
    return f"{device_name} {function_displayed_name}"


# ---------------------------
#   generate_entity_id
# ---------------------------
def generate_entity_id(
        coordinator: HuaweiControllerDataUpdateCoordinator,
        entity_domain: str,
        function_displayed_name: str,
        device_name: str
) -> str:
    preferred_id = f"{coordinator.name} {function_displayed_name} {device_name}"
    return hass_generate_id(entity_domain + ".{}", preferred_id, hass=coordinator.hass)


# ---------------------------
#   generate_entity_unique_id
# ---------------------------
def generate_entity_unique_id(
        coordinator: HuaweiControllerDataUpdateCoordinator,
        function_uid: str,
        device_mac: MAC_ADDR | None = None
) -> str:
    prefix = coordinator.unique_id
    suffix = coordinator.get_router_info().serial_number if not device_mac else device_mac
    return f"{prefix}_{function_uid}_{suffix.lower()}"
