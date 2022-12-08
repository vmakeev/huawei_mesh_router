"""Support for services."""

from dataclasses import dataclass
import logging
from typing import Final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import verify_domain_control

from .client.classes import MAC_ADDR, FilterAction, FilterMode
from .const import DATA_KEY_COORDINATOR, DATA_KEY_SERVICES, DOMAIN
from .update_coordinator import HuaweiControllerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_FIELD_MAC_ADDRESS: Final = "mac_address"

_CV_MAC_ADDR: Final = cv.matches_regex("^([A-Fa-f0-9]{2}\\:){5}[A-Fa-f0-9]{2}$")


# ---------------------------
#   ServiceNames
# ---------------------------
class ServiceNames(StrEnum):
    ADD_TO_WHITELIST = "whitelist_add"
    ADD_TO_BLACKLIST = "blacklist_add"
    REMOVE_FROM_WHITELIST = "whitelist_remove"
    REMOVE_FROM_BLACKLIST = "blacklist_remove"


@dataclass
class ServiceDescription:
    name: str
    schema: vol.Schema


SERVICES = [
    ServiceDescription(
        name=ServiceNames.ADD_TO_WHITELIST,
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
    ),
    ServiceDescription(
        name=ServiceNames.REMOVE_FROM_WHITELIST,
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
    ),
    ServiceDescription(
        name=ServiceNames.ADD_TO_BLACKLIST,
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
    ),
    ServiceDescription(
        name=ServiceNames.REMOVE_FROM_BLACKLIST,
        schema=vol.Schema({vol.Required(_FIELD_MAC_ADDRESS): _CV_MAC_ADDR}),
    ),
]


# ---------------------------
#   _find_coordinator
# ---------------------------
def _find_coordinator(
    hass: HomeAssistant, device_mac: MAC_ADDR
) -> HuaweiControllerDataUpdateCoordinator | None:
    _LOGGER.debug("Looking for coordinators with device '%s'", device_mac)
    for key, item in hass.data[DOMAIN].items():
        if key == DATA_KEY_SERVICES:
            continue
        coordinator = item.get(DATA_KEY_COORDINATOR)
        if not coordinator or not isinstance(
            coordinator, HuaweiControllerDataUpdateCoordinator
        ):
            continue
        for mac, connected_device in coordinator.connected_devices.items():
            if mac == device_mac:
                _LOGGER.debug(
                    "Found coordinator %s for '%s'", coordinator.name, device_mac
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
        _LOGGER.warning("Can not find coordinator for mac address '%s'", device_mac)
        return
    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )
    success = await coordinator.primary_router_api.apply_wlan_filter(
        FilterMode.WHITELIST, FilterAction.ADD, device_mac
    )
    if not success:
        _LOGGER.warning("Can not add item to whitelist")


# ---------------------------
#   _async_add_to_blacklist
# ---------------------------
async def _async_add_to_blacklist(hass: HomeAssistant, service: ServiceCall):
    """Service to add device to whitelist."""
    device_mac = service.data[_FIELD_MAC_ADDRESS].upper()
    coordinator = _find_coordinator(hass, device_mac)
    if not coordinator:
        _LOGGER.warning("Can not find coordinator for mac address '%s'", device_mac)
        return
    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )
    success = await coordinator.primary_router_api.apply_wlan_filter(
        FilterMode.BLACKLIST, FilterAction.ADD, device_mac
    )
    if not success:
        _LOGGER.warning("Can not add item to blacklist")


# ---------------------------
#   _async_remove_from_whitelist
# ---------------------------
async def _async_remove_from_whitelist(hass: HomeAssistant, service: ServiceCall):
    """Service to remove device from whitelist."""
    device_mac = service.data[_FIELD_MAC_ADDRESS].upper()
    coordinator = _find_coordinator(hass, device_mac)
    if not coordinator:
        _LOGGER.warning("Can not find coordinator for mac address '%s'", device_mac)
        return
    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )
    success = await coordinator.primary_router_api.apply_wlan_filter(
        FilterMode.WHITELIST, FilterAction.REMOVE, device_mac
    )
    if not success:
        _LOGGER.warning("Can not remove item from to whitelist")


# ---------------------------
#   _async_remove_from_blacklist
# ---------------------------
async def _async_remove_from_blacklist(hass: HomeAssistant, service: ServiceCall):
    """Service to remove device from whitelist."""
    device_mac = service.data[_FIELD_MAC_ADDRESS].upper()
    coordinator = _find_coordinator(hass, device_mac)
    if not coordinator:
        _LOGGER.warning("Can not find coordinator for mac address '%s'", device_mac)
        return
    _LOGGER.debug(
        "Service '%s' called for device mac '%s' with %s",
        service.service,
        device_mac,
        coordinator.name,
    )
    success = await coordinator.primary_router_api.apply_wlan_filter(
        FilterMode.BLACKLIST, FilterAction.REMOVE, device_mac
    )
    if not success:
        _LOGGER.warning("Can not remove item from to blacklist")


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

        if service_name == ServiceNames.ADD_TO_WHITELIST:
            await _async_add_to_whitelist(hass, service)

        elif service_name == ServiceNames.ADD_TO_BLACKLIST:
            await _async_add_to_blacklist(hass, service)

        elif service_name == ServiceNames.REMOVE_FROM_WHITELIST:
            await _async_remove_from_whitelist(hass, service)

        elif service_name == ServiceNames.REMOVE_FROM_BLACKLIST:
            await _async_remove_from_blacklist(hass, service)

        else:
            _LOGGER.warning("Unknown service: %s", service_name)

    _LOGGER.debug("Registering services")
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

    _LOGGER.debug("Unloading services")
    hass.data[DOMAIN].pop(DATA_KEY_SERVICES)
    for service in SERVICES:
        hass.services.async_remove(domain=DOMAIN, service=service.name)
