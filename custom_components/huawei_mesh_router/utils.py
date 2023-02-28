from abc import ABC, abstractmethod
import logging
from typing import Callable, Generic, Iterable, Tuple, TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.storage import Store

from .classes import DEVICE_TAG
from .client.classes import MAC_ADDR

_TKey = TypeVar("_TKey")
_TItem = TypeVar("_TItem")


# ---------------------------
#   HuaweiChangesWatcher
# ---------------------------
class HuaweiChangesWatcher(Generic[_TKey, _TItem], ABC):
    def __init__(self, predicate: Callable[[_TItem], bool]) -> None:
        """Initialize."""
        self._known_items: dict[_TKey, _TItem] = {}
        self._predicate = predicate

    @abstractmethod
    def _get_key(self, item: _TItem) -> _TKey:
        raise NotImplementedError()

    @abstractmethod
    def _get_actual_items(self) -> Iterable[_TItem]:
        raise NotImplementedError()

    def _get_difference(
        self, hass: HomeAssistant
    ) -> Tuple[
        Iterable[Tuple[_TKey, _TItem]],
        Iterable[Tuple[EntityRegistry, _TKey, _TItem]],
    ]:
        """Return the difference between previously known and current lists of items."""
        actual_items: dict[_TKey, _TItem] = {}

        for item in self._get_actual_items():
            if self._predicate(item):
                actual_items[self._get_key(item)] = item

        added: list[Tuple[_TKey, _TItem]] = []
        removed: list[Tuple[EntityRegistry, _TKey, _TItem]] = []

        for key, item in actual_items.items():
            if key in self._known_items:
                continue
            self._known_items[key] = item
            added.append((key, item))

        missing_items = {}
        for key, item in self._known_items.items():
            if key not in actual_items:
                missing_items[key] = item

        if missing_items:
            er = entity_registry.async_get(hass)
            for key, missing_item in missing_items.items():
                self._known_items.pop(key, None)
                removed.append((er, key, missing_item))

        return added, removed


# ---------------------------
#   TagsMap
# ---------------------------
class TagsMap:
    def __init__(self, tags_map_storage: Store, logger: logging.Logger):
        """Initialize."""
        self._logger = logger
        self._storage: Store = tags_map_storage
        self._mac_to_tags: dict[MAC_ADDR, list[DEVICE_TAG]] = {}
        self._tag_to_macs: dict[DEVICE_TAG, list[MAC_ADDR]] = {}
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Return true when tags are loaded."""
        return self._is_loaded

    async def load(self):
        """Load the tags from the storage."""
        self._logger.debug("Stored tags loading started")

        self._mac_to_tags.clear()
        self._tag_to_macs.clear()

        self._tag_to_macs = await self._storage.async_load()
        if not self._tag_to_macs:
            self._logger.debug("No stored tags found, creating sample")
            default_tags = {
                "homeowners": ["place_mac_addresses_here"],
                "visitors": ["place_mac_addresses_here"],
            }
            await self._storage.async_save(default_tags)
            self._tag_to_macs = default_tags

        for tag, devices_macs in self._tag_to_macs.items():
            for device_mac in devices_macs:
                if device_mac not in self._mac_to_tags:
                    self._mac_to_tags[device_mac] = []
                self._mac_to_tags[device_mac].append(tag)

        self._is_loaded = True

        self._logger.debug("Stored tags loading finished")

    def get_tags(self, mac_address: MAC_ADDR) -> list[DEVICE_TAG]:
        """Return the tags of the device"""
        return self._mac_to_tags.get(mac_address, [])

    def get_all_tags(self) -> Iterable[DEVICE_TAG]:
        """Return all known tags."""
        return self._tag_to_macs.keys()

    def get_devices(self, tag: DEVICE_TAG) -> list[MAC_ADDR]:
        """Return the devices having specified tag."""
        return self._tag_to_macs.get(tag, [])


# ---------------------------
#   ZonesMap
# ---------------------------
class ZonesMap:
    def __init__(self, zones_map_storage: Store, logger: logging.Logger):
        """Initialize."""
        self._logger = logger
        self._storage: Store = zones_map_storage
        self._devices_to_zones: dict[str, str] = {}
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Return true when zones are loaded."""
        return self._is_loaded

    async def load(self):
        """Load the zones from the storage."""
        self._logger.debug("Stored zones loading started")
        self._devices_to_zones.clear()
        self._devices_to_zones = await self._storage.async_load() or {}
        self._is_loaded = True
        self._logger.debug("Stored zones loading finished")

    def get_zone_id(self, device_id: str) -> str | None:
        """Return the zone id of the device"""
        return self._devices_to_zones.get(device_id)

    async def set_zone_id(self, device_id: str, zone_id: str | None) -> None:
        """Set the zone id to the device"""
        if not self.is_loaded:
            await self.load()

        self._devices_to_zones[device_id] = zone_id
        await self._storage.async_save(self._devices_to_zones)
