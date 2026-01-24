"""Data update coordinators for Invader Tracker integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CITY_REQUEST_DELAY, COORDINATOR_FLASH, COORDINATOR_SPOTTER
from .exceptions import (
    AuthenticationError,
    InvaderSpotterConnectionError,
    InvaderTrackerConnectionError,
    ParseError,
    RateLimitError,
)
from .models import FlashedInvader, Invader, NewsEvent

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api.flash_invader import FlashInvaderAPI
    from .api.invader_spotter import InvaderSpotterScraper

_LOGGER = logging.getLogger(__name__)


class InvaderSpotterCoordinator(DataUpdateCoordinator[dict[str, list[Invader]]]):
    """Coordinator for invader-spotter.art data with smart caching."""

    def __init__(
        self,
        hass: HomeAssistant,
        scraper: InvaderSpotterScraper,
        cities: dict[str, str],
        update_interval_hours: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            scraper: Invader Spotter scraper
            cities: Dict mapping city codes to names
            update_interval_hours: Hours between updates

        """
        super().__init__(
            hass,
            _LOGGER,
            name=COORDINATOR_SPOTTER,
            update_interval=timedelta(hours=update_interval_hours),
        )
        self._scraper = scraper
        self._cities = cities
        self._update_interval_hours = update_interval_hours
        # Cache: city_code -> (timestamp, list[Invader])
        self._city_cache: dict[str, tuple[datetime, list[Invader]]] = {}
        # News events cache: (timestamp, list[NewsEvent])
        self._news_cache: tuple[datetime, list[NewsEvent]] | None = None
        self._news_cache_hours: int = 6  # Cache news for 6 hours

    @property
    def cities(self) -> dict[str, str]:
        """Get tracked cities."""
        return self._cities

    def update_cities(self, cities: dict[str, str]) -> None:
        """Update the list of tracked cities.

        Args:
            cities: New dict mapping city codes to names

        """
        old_cities = set(self._cities.keys())
        new_cities = set(cities.keys())
        
        # Log changes
        added = new_cities - old_cities
        removed = old_cities - new_cities
        
        if added:
            _LOGGER.info("New cities added: %s", ", ".join(added))
        if removed:
            _LOGGER.info("Cities removed: %s", ", ".join(removed))
            # Clean up cache for removed cities
            for city_code in removed:
                self._city_cache.pop(city_code, None)
        
        self._cities = cities

    def _is_cache_valid(self, city_code: str) -> bool:
        """Check if cached data for a city is still valid.
        
        Args:
            city_code: City code to check
            
        Returns:
            True if cache is valid and not expired
        """
        if city_code not in self._city_cache:
            return False
        
        cached_time, _ = self._city_cache[city_code]
        age = datetime.now() - cached_time
        max_age = timedelta(hours=self._update_interval_hours)
        
        return age < max_age

    async def _async_update_data(self) -> dict[str, list[Invader]]:
        """Fetch data from invader-spotter, using cache for unchanged cities."""
        _LOGGER.debug("Starting invader-spotter update for %d cities", len(self._cities))

        result: dict[str, list[Invader]] = {}
        failures: list[str] = []
        cached_count = 0
        scraped_count = 0

        for i, (city_code, city_name) in enumerate(self._cities.items()):
            # Check if we can use cached data
            if self._is_cache_valid(city_code):
                _, cached_invaders = self._city_cache[city_code]
                result[city_code] = cached_invaders
                cached_count += 1
                _LOGGER.debug("Using cached data for %s (%d invaders)", city_code, len(cached_invaders))
                continue
            
            # Polite delay between requests (except first scrape)
            if scraped_count > 0:
                await asyncio.sleep(CITY_REQUEST_DELAY)

            try:
                invaders = await self._scraper.get_city_invaders(city_code, city_name)
                result[city_code] = invaders
                
                # Update cache
                self._city_cache[city_code] = (datetime.now(), invaders)
                scraped_count += 1
                
                _LOGGER.debug(
                    "Scraped %s: %d invaders (%d flashable)",
                    city_code,
                    len(invaders),
                    sum(1 for inv in invaders if inv.is_flashable),
                )

            except (InvaderSpotterConnectionError, ParseError) as err:
                _LOGGER.warning("Failed to scrape %s: %s", city_code, err)
                failures.append(city_code)

                # Use cached data if available (even if expired)
                if city_code in self._city_cache:
                    _, cached_invaders = self._city_cache[city_code]
                    result[city_code] = cached_invaders
                    _LOGGER.info("Using expired cache for %s", city_code)
                # Or use previous coordinator data
                elif self.data and city_code in self.data:
                    result[city_code] = self.data[city_code]
                    _LOGGER.info("Using previous data for %s", city_code)

        # If ALL cities failed and no cached data, raise UpdateFailed
        if len(failures) == len(self._cities) and not result:
            raise UpdateFailed(f"Failed to scrape any cities: {', '.join(failures)}")

        # Log summary
        total_invaders = sum(len(inv) for inv in result.values())
        if failures:
            _LOGGER.warning(
                "Partial update: %d scraped, %d cached, %d failed (%d total invaders)",
                scraped_count, cached_count, len(failures), total_invaders,
            )
        else:
            _LOGGER.info(
                "Update complete: %d scraped, %d cached (%d total invaders)",
                scraped_count, cached_count, total_invaders,
            )

        return result
    
    async def async_force_refresh_city(self, city_code: str) -> None:
        """Force refresh a specific city, bypassing cache.
        
        Args:
            city_code: City code to refresh
        """
        if city_code not in self._cities:
            _LOGGER.warning("Cannot refresh unknown city: %s", city_code)
            return
        
        # Invalidate cache for this city
        self._city_cache.pop(city_code, None)
        
        # Trigger a refresh
        await self.async_request_refresh()

    async def get_news_events(self, days: int = 30) -> list[NewsEvent]:
        """Get news events from invader-spotter.art/news.php.
        
        Uses caching to avoid hitting the site too frequently.
        
        Args:
            days: Number of days of news to fetch
            
        Returns:
            List of NewsEvent objects
        """
        # Check cache
        if self._news_cache is not None:
            cached_time, cached_events = self._news_cache
            age = datetime.now() - cached_time
            if age < timedelta(hours=self._news_cache_hours):
                _LOGGER.debug("Using cached news (%d events)", len(cached_events))
                return cached_events
        
        try:
            # Get news filtered by our tracked cities
            city_codes = set(self._cities.keys())
            events = await self._scraper.get_news(days=days, city_codes=city_codes)
            
            # Update cache
            self._news_cache = (datetime.now(), events)
            _LOGGER.info("Fetched %d news events for tracked cities", len(events))
            
            return events
            
        except Exception as err:
            _LOGGER.warning("Failed to fetch news: %s", err)
            # Return cached events if available
            if self._news_cache is not None:
                _, cached_events = self._news_cache
                return cached_events
            return []

    def get_news_for_city(self, city_code: str, events: list[NewsEvent]) -> list[NewsEvent]:
        """Filter news events for a specific city.
        
        Args:
            city_code: City code to filter by
            events: List of all news events
            
        Returns:
            List of NewsEvent for this city
        """
        return [e for e in events if e.city_code == city_code]


class FlashInvaderCoordinator(DataUpdateCoordinator[list[FlashedInvader]]):
    """Coordinator for Flash Invader API data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FlashInvaderAPI,
        update_interval_hours: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            api: Flash Invader API client
            update_interval_hours: Hours between updates

        """
        super().__init__(
            hass,
            _LOGGER,
            name=COORDINATOR_FLASH,
            update_interval=timedelta(hours=update_interval_hours),
        )
        self._api = api
        self._flashed_by_city: dict[str, list[FlashedInvader]] = {}

    def get_flashed_for_city(self, city_code: str) -> list[FlashedInvader]:
        """Get flashed invaders for a specific city.

        Args:
            city_code: City code to filter by

        Returns:
            List of FlashedInvader for the city

        """
        return self._flashed_by_city.get(city_code, [])

    async def _async_update_data(self) -> list[FlashedInvader]:
        """Fetch flashed invaders from API."""
        _LOGGER.debug("Fetching flashed invaders from Flash Invader API")

        try:
            invaders = await self._api.get_flashed_invaders()
            self._update_city_grouping(invaders)

            _LOGGER.info(
                "Fetched %d flashed invaders across %d cities",
                len(invaders),
                len(self._flashed_by_city),
            )
            return invaders

        except AuthenticationError as err:
            # Triggers HA reauth flow - user must reconfigure
            raise ConfigEntryAuthFailed(
                "Flash Invader authentication failed. Please reconfigure."
            ) from err

        except RateLimitError as err:
            _LOGGER.warning("Rate limited, will retry later")
            raise UpdateFailed("Rate limited by Flash Invader API") from err

        except InvaderTrackerConnectionError as err:
            _LOGGER.warning("Connection error: %s", err)
            raise UpdateFailed(f"Connection error: {err}") from err

        except ParseError as err:
            _LOGGER.error("Parse error: %s", err)
            raise UpdateFailed(f"Failed to parse response: {err}") from err

    def _update_city_grouping(self, invaders: list[FlashedInvader]) -> None:
        """Group invaders by city code extracted from ID.

        Args:
            invaders: List of flashed invaders to group

        """
        self._flashed_by_city.clear()

        for inv in invaders:
            # Extract city code from ID (e.g., "PA_346" -> "PA")
            parts = inv.id.rsplit("_", 1)
            if len(parts) == 2:
                city_code = parts[0]
            else:
                city_code = inv.id[:2]  # Fallback to first 2 chars

            self._flashed_by_city.setdefault(city_code, []).append(inv)
