"""Data update coordinators for Invader Tracker integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
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
from .models import FlashedInvader, Invader

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api.flash_invader import FlashInvaderAPI
    from .api.invader_spotter import InvaderSpotterScraper

_LOGGER = logging.getLogger(__name__)


class InvaderSpotterCoordinator(DataUpdateCoordinator[dict[str, list[Invader]]]):
    """Coordinator for invader-spotter.art data."""

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

    @property
    def cities(self) -> dict[str, str]:
        """Get tracked cities."""
        return self._cities

    def update_cities(self, cities: dict[str, str]) -> None:
        """Update the list of tracked cities.

        Args:
            cities: New dict mapping city codes to names

        """
        self._cities = cities

    async def _async_update_data(self) -> dict[str, list[Invader]]:
        """Fetch data from invader-spotter for all tracked cities."""
        _LOGGER.debug("Starting invader-spotter scrape for %d cities", len(self._cities))

        result: dict[str, list[Invader]] = {}
        failures: list[str] = []

        for i, (city_code, city_name) in enumerate(self._cities.items()):
            # Polite delay between requests (except first)
            if i > 0:
                await asyncio.sleep(CITY_REQUEST_DELAY)

            try:
                invaders = await self._scraper.get_city_invaders(city_code, city_name)
                result[city_code] = invaders
                _LOGGER.debug(
                    "Scraped %s: %d invaders (%d flashable)",
                    city_code,
                    len(invaders),
                    sum(1 for inv in invaders if inv.is_flashable),
                )

            except (InvaderSpotterConnectionError, ParseError) as err:
                _LOGGER.warning("Failed to scrape %s: %s", city_code, err)
                failures.append(city_code)

                # Keep previous data for this city if available
                if self.data and city_code in self.data:
                    result[city_code] = self.data[city_code]
                    _LOGGER.info("Using cached data for %s", city_code)

        # If ALL cities failed, raise UpdateFailed
        if len(failures) == len(self._cities):
            raise UpdateFailed(f"Failed to scrape any cities: {', '.join(failures)}")

        # Log summary
        if failures:
            _LOGGER.warning(
                "Partial scrape failure: %d/%d cities failed",
                len(failures),
                len(self._cities),
            )
        else:
            total_invaders = sum(len(inv) for inv in result.values())
            _LOGGER.info(
                "Scrape complete: %d cities, %d total invaders",
                len(result),
                total_invaders,
            )

        return result


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
