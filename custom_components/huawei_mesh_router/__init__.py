"""Huawei Router integration."""

import logging
from typing import Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation
from homeassistant.helpers.storage import Store

from .client.huaweiapi import HuaweiApi
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPT_DEVICE_TRACKER,
    OPT_DEVICES_TAGS,
    OPT_ROUTER_CLIENTS_SENSORS,
    OPT_WIFI_ACCESS_SWITCHES,
    PLATFORMS,
    STORAGE_VERSION,
)
from .helpers import pop_coordinator, set_coordinator
from .options import HuaweiIntegrationOptions
from .services import async_setup_services, async_unload_services
from .update_coordinator import HuaweiControllerDataUpdateCoordinator

CONFIG_SCHEMA = config_validation.removed(DOMAIN, raise_if_present=False)

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   _get_platforms
# ---------------------------
def _get_platforms(integration_options: HuaweiIntegrationOptions) -> Iterable[str]:
    excluded_platforms = []

    if not integration_options.device_tracker:
        excluded_platforms.append(Platform.DEVICE_TRACKER)

    return filter(lambda item: item not in excluded_platforms, PLATFORMS)


# ---------------------------
#   async_setup
# ---------------------------
async def async_setup(hass, _config):
    """Set up configured Huawei Controller."""
    hass.data[DOMAIN] = {}
    return True


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Huawei Router as config entry."""
    integration_options = HuaweiIntegrationOptions(config_entry)

    if integration_options.devices_tags:
        store = Store(
            hass, STORAGE_VERSION, f"huawei_mesh_{config_entry.entry_id}_tags"
        )
    else:
        store = None

    coordinator = HuaweiControllerDataUpdateCoordinator(
        hass, config_entry, integration_options, store
    )
    await coordinator.async_config_entry_first_refresh()

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    set_coordinator(hass, config_entry, coordinator)

    hass.config_entries.async_setup_platforms(
        config_entry, _get_platforms(integration_options)
    )

    await async_setup_services(hass, config_entry)
    return True


# ---------------------------
#   update_listener
# ---------------------------
async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


# ---------------------------
#   async_update_entry
# ---------------------------
async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, _get_platforms(HuaweiIntegrationOptions(config_entry))
    )
    if unload_ok:
        coordinator = pop_coordinator(hass, config_entry)
        if coordinator and isinstance(
            coordinator, HuaweiControllerDataUpdateCoordinator
        ):
            coordinator.unload()
    await async_unload_services(hass, config_entry)
    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    updated_data = {**config_entry.data}
    updated_options = {**config_entry.options}

    if config_entry.version == 1:
        _LOGGER.debug("Migrating to version 2")
        scan_interval = (
            updated_data.pop(CONF_SCAN_INTERVAL)
            if CONF_SCAN_INTERVAL in updated_data
            else DEFAULT_SCAN_INTERVAL
        )

        # use True instead of default values so as not to change the behavior of existing integrations
        updated_options = {
            CONF_SCAN_INTERVAL: scan_interval,
            OPT_WIFI_ACCESS_SWITCHES: True,
            OPT_DEVICES_TAGS: True,
            OPT_ROUTER_CLIENTS_SENSORS: True,
            OPT_DEVICE_TRACKER: True,
        }
        config_entry.version = 2

    hass.config_entries.async_update_entry(
        config_entry, data=updated_data, options=updated_options
    )

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
