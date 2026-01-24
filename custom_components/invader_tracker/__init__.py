"""The Invader Tracker integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.flash_invader import FlashInvaderAPI
from .api.invader_spotter import InvaderSpotterScraper
from .const import (
    CONF_API_INTERVAL,
    CONF_CITIES,
    CONF_SCRAPE_INTERVAL,
    CONF_UID,
    DEFAULT_API_INTERVAL_HOURS,
    DEFAULT_SCRAPE_INTERVAL_HOURS,
    DOMAIN,
)
from .coordinator import FlashInvaderCoordinator, InvaderSpotterCoordinator
from .processor import DataProcessor
from .store import StateStore

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Invader Tracker from a config entry."""
    _LOGGER.info("Setting up Invader Tracker integration")

    # Initialize domain data
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)

    # Get configuration
    uid = entry.data[CONF_UID]
    cities = entry.data.get(CONF_CITIES, {})
    scrape_interval = entry.data.get(CONF_SCRAPE_INTERVAL, DEFAULT_SCRAPE_INTERVAL_HOURS)
    api_interval = entry.data.get(CONF_API_INTERVAL, DEFAULT_API_INTERVAL_HOURS)

    # Create API clients
    flash_api = FlashInvaderAPI(session, uid)
    spotter_scraper = InvaderSpotterScraper(session)

    # Create coordinators
    spotter_coordinator = InvaderSpotterCoordinator(
        hass,
        spotter_scraper,
        cities,
        scrape_interval,
    )
    flash_coordinator = FlashInvaderCoordinator(
        hass,
        flash_api,
        api_interval,
    )

    # Create processor and store
    store = StateStore(hass, entry.entry_id)
    processor = DataProcessor(spotter_coordinator, flash_coordinator, store)
    processor.set_city_names(cities)

    # Initialize processor (load previous snapshot)
    await processor.async_initialize()

    # Initial data fetch
    _LOGGER.debug("Performing initial data fetch")
    await spotter_coordinator.async_config_entry_first_refresh()
    await flash_coordinator.async_config_entry_first_refresh()

    # Save initial snapshot
    await processor.async_save_snapshot()

    # Set up listener to save snapshot after each spotter update
    async def _on_spotter_update() -> None:
        """Save snapshot when spotter data updates."""
        await processor.async_save_snapshot()

    spotter_coordinator.async_add_listener(_on_spotter_update)

    # Store runtime data
    hass.data[DOMAIN][entry.entry_id] = {
        "spotter_coordinator": spotter_coordinator,
        "flash_coordinator": flash_coordinator,
        "processor": processor,
        "store": store,
    }

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "Invader Tracker setup complete: tracking %d cities", len(cities)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Invader Tracker integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("Options updated, reloading Invader Tracker")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of config entry."""
    _LOGGER.info("Removing Invader Tracker integration")

    # Clean up stored data
    store = StateStore(hass, entry.entry_id)
    await store.async_remove()
