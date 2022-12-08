"""Huawei Router integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation
from homeassistant.helpers.storage import Store

from .client.huaweiapi import HuaweiApi
from .const import DATA_KEY_COORDINATOR, DOMAIN, PLATFORMS, STORAGE_VERSION
from .services import async_setup_services, async_unload_services
from .update_coordinator import HuaweiControllerDataUpdateCoordinator

CONFIG_SCHEMA = config_validation.removed(DOMAIN, raise_if_present=False)


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
    store: Store = Store(
        hass, STORAGE_VERSION, f"huawei_mesh_{config_entry.entry_id}_tags"
    )
    coordinator = HuaweiControllerDataUpdateCoordinator(hass, config_entry, store)
    await coordinator.async_config_entry_first_refresh()

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    config_entry.async_on_unload(coordinator.unload)

    hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})[
        DATA_KEY_COORDINATOR
    ] = coordinator
    hass.data[DOMAIN][config_entry.entry_id][DATA_KEY_COORDINATOR] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

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
        config_entry, PLATFORMS
    )
    if unload_ok:
        coordinator = (
            hass.data[DOMAIN].get(config_entry.entry_id, {}).pop(DATA_KEY_COORDINATOR)
        )
        if coordinator and isinstance(
            coordinator, HuaweiControllerDataUpdateCoordinator
        ):
            coordinator.unload()
    await async_unload_services(hass, config_entry)
    return unload_ok
