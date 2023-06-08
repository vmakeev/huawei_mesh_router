"""Support for services."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import verify_domain_control

from .client.classes import (
    MAC_ADDR,
    FilterAction,
    FilterMode,
    HuaweiGuestNetworkDuration,
)
from .const import DATA_KEY_COORDINATOR, DATA_KEY_SERVICES, DOMAIN
from .update_coordinator import HuaweiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_FIELD_MAC_ADDRESS: Final = "mac_address"

_FIELD_SERIAL_NUMBER: Final = "serial_number"
_FIELD_ENABLED: Final = "enabled"
_FIELD_SSID: Final = "ssid"
_FIELD_DURATION: Final = "duration"
_FIELD_SECURITY: Final = "security"
_FIELD_PASSWORD: Final = "password"

_CV_MAC_ADDR: Final = cv.matches_regex("^([A-Fa-f0-9]{2}\\:){5}[A-Fa-f0-9]{2}$")

_CV_SSID: Final = cv.matches_regex("^([A-Fa-f0-9]{2}\\:){5}[A-Fa-f0-9]{2}$")

_WIFI_DURATION_MAP: dict[str, HuaweiGuestNetworkDuration] = {
    "4 hours": HuaweiGuestNetworkDuration.FOUR_HOURS,
    "1 day": HuaweiGuestNetworkDuration.ONE_DAY,
    "Unlimited": HuaweiGuestNetworkDuration.UNLIMITED,
}

_WIFI_SECURITY_MAP: dict[str, bool] = {
    "Encrypted": True,
    "Open": False,
}


# ---------------------------
# ---------------------------


# ---------------------------
#   ServiceName
# ---------------------------
class ServiceName(StrEnum):
    ADD_TO_WHITELIST = "whitelist_add"
    ADD_TO_BLACKLIST = "blacklist_add"
    REMOVE_FROM_WHITELIST = "whitelist_remove"
    REMOVE_FROM_BLACKLIST = "blacklist_remove"
    GUEST_NETWORK_SETUP = "guest_network_setup"


@dataclass
class ServiceDescription:
    name: str
    schema: vol.Schema


SERVICES = [
    ServiceDescription(
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
        name=ServiceName.ADD_TO_WHITELIST,
    ),
    ServiceDescription(
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
        name=ServiceName.REMOVE_FROM_WHITELIST,
    ),
    ServiceDescription(
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
        name=ServiceName.ADD_TO_BLACKLIST,
    ),
    ServiceDescription(
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
        name=ServiceName.REMOVE_FROM_BLACKLIST,
    ),
    ServiceDescription(
        name=ServiceName.GUEST_NETWORK_SETUP,
        schema=vol.Schema(
            {
                vol.Required(_FIELD_SERIAL_NUMBER): vol.Coerce(str),
                vol.Required(_FIELD_ENABLED): vol.Coerce(bool),
                vol.Required(_FIELD_SSID): vol.Coerce(str),
                vol.Required(_FIELD_DURATION): vol.In(list(_WIFI_DURATION_MAP.keys())),
                vol.Required(_FIELD_SECURITY): vol.In(list(_WIFI_SECURITY_MAP.keys())),
                vol.Required(_FIELD_PASSWORD): vol.All(
                    vol.Coerce(str), vol.Length(min=8)
                ),
            }
        ),
    ),
]


# ---------------------------
#   _find_coordinator
# ---------------------------
def _find_coordinator(
    hass: HomeAssistant, device_mac: MAC_ADDR
) -> HuaweiDataUpdateCoordinator | None:
    _LOGGER.debug("Looking for coordinators with device '%s'", device_mac)
    for key, item in hass.data[DOMAIN].items():
        if key == DATA_KEY_SERVICES:
            continue
        coordinator = item.get(DATA_KEY_COORDINATOR)
        if not coordinator or not isinstance(coordinator, HuaweiDataUpdateCoordinator):
            continue
        for mac, _ in coordinator.connected_devices.items():
            if mac == device_mac:
                _LOGGER.debug(
                    "Found coordinator %s for '%s'", coordinator.name, device_mac
                )
                return coordinator


# ---------------------------
#   _find_coordinator_serial
# ---------------------------
def _find_coordinator_serial(
    hass: HomeAssistant, serial_number: str
) -> HuaweiDataUpdateCoordinator | None:
    _LOGGER.debug("Looking for coordinators with serial number '%s'", str)
    for key, item in hass.data[DOMAIN].items():
        if key == DATA_KEY_SERVICES:
            continue
        coordinator = item.get(DATA_KEY_COORDINATOR)
        if not coordinator or not isinstance(coordinator, HuaweiDataUpdateCoordinator):
            continue
        if coordinator.get_router_info().serial_number.upper() == serial_number.upper():
            _LOGGER.debug(
                "Found coordinator %s with serial number '%s'",
                coordinator.name,
                serial_number,
            )
            return coordinator


# ---------------------------
#   _async_add_to_whitelist
# ---------------------------
async def _async_add_to_whitelist(hass: HomeAssistant, service: ServiceCall):
    """Service to add device to whitelist."""
    device_mac = service.data[_FIELD_MAC_ADDRESS].upper()
    coordinator = _find_coordinator(hass, device_mac)
    if not coordinator:
        raise HomeAssistantError(
            f"Can not find coordinator for mac address '{device_mac}'"
        )

    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )
    try:
        success = await coordinator.primary_router_api.apply_wlan_filter(
            FilterMode.WHITELIST, FilterAction.ADD, device_mac
        )
    except Exception as ex:
        raise HomeAssistantError(str(ex))

    if not success:
        raise HomeAssistantError("Can not add item to whitelist")


# ---------------------------
#   _async_add_to_blacklist
# ---------------------------
async def _async_add_to_blacklist(hass: HomeAssistant, service: ServiceCall):
    """Service to add device to whitelist."""
    device_mac = service.data[_FIELD_MAC_ADDRESS].upper()
    coordinator = _find_coordinator(hass, device_mac)
    if not coordinator:
        raise HomeAssistantError(
            f"Can not find coordinator for mac address '{device_mac}'"
        )

    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )
    try:
        success = await coordinator.primary_router_api.apply_wlan_filter(
            FilterMode.BLACKLIST, FilterAction.ADD, device_mac
        )
    except Exception as ex:
        raise HomeAssistantError(str(ex))

    if not success:
        raise HomeAssistantError("Can not add item to blacklist")


# ---------------------------
#   _async_remove_from_whitelist
# ---------------------------
async def _async_remove_from_whitelist(hass: HomeAssistant, service: ServiceCall):
    """Service to remove device from whitelist."""
    device_mac = service.data[_FIELD_MAC_ADDRESS].upper()
    coordinator = _find_coordinator(hass, device_mac)
    if not coordinator:
        raise HomeAssistantError(
            f"Can not find coordinator for mac address '{device_mac}'"
        )

    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )

    try:
        success = await coordinator.primary_router_api.apply_wlan_filter(
            FilterMode.WHITELIST, FilterAction.REMOVE, device_mac
        )
    except Exception as ex:
        raise HomeAssistantError(str(ex))

    if not success:
        raise HomeAssistantError("Can not remove item from whitelist")


# ---------------------------
#   _async_remove_from_blacklist
# ---------------------------
async def _async_remove_from_blacklist(hass: HomeAssistant, service: ServiceCall):
    """Service to remove device from whitelist."""
    device_mac = service.data[_FIELD_MAC_ADDRESS].upper()
    coordinator = _find_coordinator(hass, device_mac)
    if not coordinator:
        raise HomeAssistantError(
            f"Can not find coordinator for mac address '{device_mac}'"
        )

    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )
    try:
        success = await coordinator.primary_router_api.apply_wlan_filter(
            FilterMode.BLACKLIST, FilterAction.REMOVE, device_mac
        )
    except Exception as ex:
        raise HomeAssistantError(str(ex))

    if not success:
        raise HomeAssistantError("Can not remove item from blacklist")


# ---------------------------
#   _async_setup_guest_network
# ---------------------------
async def _async_setup_guest_network(hass: HomeAssistant, service: ServiceCall):
    """Service to set port poe settings."""
    serial_number = service.data[_FIELD_SERIAL_NUMBER]

    coordinator = _find_coordinator_serial(hass, serial_number)
    if not coordinator:
        raise HomeAssistantError(
            f"Can not find coordinator with serial number '{serial_number}'"
        )

    _LOGGER.debug(
        "Service '%s' called for serial number '%s' with name %s",
        service.service,
        serial_number,
        coordinator.name,
    )

    try:
        enabled: bool = service.data[_FIELD_ENABLED]
        ssid: str = service.data[_FIELD_SSID]
        duration: HuaweiGuestNetworkDuration = _WIFI_DURATION_MAP[
            service.data[_FIELD_DURATION]
        ]
        secured: bool = _WIFI_SECURITY_MAP[service.data[_FIELD_SECURITY]]
        password: str | None = service.data[_FIELD_PASSWORD]

        await coordinator.primary_router_api.set_guest_network_state(
            enabled, ssid, duration, secured, password
        )
    except Exception as ex:
        raise HomeAssistantError(str(ex))


# ---------------------------
#   _change_instances_count
# ---------------------------
def _change_instances_count(hass: HomeAssistant, delta: int) -> int:
    current_count = hass.data.setdefault(DOMAIN, {}).setdefault(DATA_KEY_SERVICES, 0)
    result = current_count + delta
    hass.data[DOMAIN][DATA_KEY_SERVICES] = result
    return result


async def async_setup_services(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Set up the Huawei Router services."""
    active_instances = _change_instances_count(hass, 1)
    if active_instances > 1:
        _LOGGER.debug(
            "%s active instances has already been registered, skipping",
            active_instances - 1,
        )
        return

    @verify_domain_control(hass, DOMAIN)
    async def async_call_service(service: ServiceCall) -> None:
        service_name = service.service

        if service_name == ServiceName.ADD_TO_WHITELIST:
            await _async_add_to_whitelist(hass, service)

        elif service_name == ServiceName.ADD_TO_BLACKLIST:
            await _async_add_to_blacklist(hass, service)

        elif service_name == ServiceName.REMOVE_FROM_WHITELIST:
            await _async_remove_from_whitelist(hass, service)

        elif service_name == ServiceName.REMOVE_FROM_BLACKLIST:
            await _async_remove_from_blacklist(hass, service)

        elif service_name == ServiceName.GUEST_NETWORK_SETUP:
            await _async_setup_guest_network(hass, service)

        else:
            raise ServiceNotFound(DOMAIN, service_name)

    for item in SERVICES:
        hass.services.async_register(
            domain=DOMAIN,
            service=item.name,
            service_func=async_call_service,
            schema=item.schema,
        )


async def async_unload_services(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload services."""
    active_instances = _change_instances_count(hass, -1)
    if active_instances > 0:
        _LOGGER.debug("%s active instances remaining, skipping", active_instances)
        return

    hass.data[DOMAIN].pop(DATA_KEY_SERVICES)
    for service in SERVICES:
        hass.services.async_remove(domain=DOMAIN, service=service.name)
