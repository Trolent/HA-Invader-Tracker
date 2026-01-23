"""Data processor for Invader Tracker integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .models import (
    ChangeSet,
    City,
    CityStats,
    FlashedInvader,
    Invader,
    InvaderStatus,
    StateSnapshot,
)

if TYPE_CHECKING:
    from .coordinator import FlashInvaderCoordinator, InvaderSpotterCoordinator
    from .store import StateStore

_LOGGER = logging.getLogger(__name__)


class DataProcessor:
    """Process and cross-reference invader data."""

    def __init__(
        self,
        spotter_coordinator: InvaderSpotterCoordinator,
        flash_coordinator: FlashInvaderCoordinator,
        store: StateStore,
    ) -> None:
        """Initialize the processor.

        Args:
            spotter_coordinator: Coordinator for invader-spotter data
            flash_coordinator: Coordinator for Flash Invader API data
            store: State storage for snapshots

        """
        self._spotter = spotter_coordinator
        self._flash = flash_coordinator
        self._store = store
        self._previous_snapshot: StateSnapshot | None = None
        self._city_names: dict[str, str] = {}

    async def async_initialize(self) -> None:
        """Load previous snapshot from storage."""
        self._previous_snapshot = await self._store.async_load_snapshot()
        if self._previous_snapshot:
            _LOGGER.info(
                "Loaded previous snapshot from %s",
                self._previous_snapshot.timestamp.isoformat(),
            )

    def set_city_names(self, city_names: dict[str, str]) -> None:
        """Set city code to name mapping.

        Args:
            city_names: Dict mapping city codes to names

        """
        self._city_names = city_names

    def compute_city_stats(self, city_code: str) -> CityStats:
        """Compute full statistics for a city.

        Args:
            city_code: City code to compute stats for

        Returns:
            CityStats with all computed values

        """
        # Get all invaders from spotter coordinator
        all_invaders = self._get_invaders_for_city(city_code)

        # Get flashed invaders from flash coordinator
        flashed = self._flash.get_flashed_for_city(city_code)

        # Get changes
        changes = self.detect_changes(city_code)

        # Build city object
        city = City(
            code=city_code,
            name=self._city_names.get(city_code, city_code),
            total_invaders=len(all_invaders),
        )

        return CityStats(
            city=city,
            all_invaders=all_invaders,
            flashed_invaders=flashed,
            new_invaders=changes.new_invaders,
            reactivated_invaders=changes.reactivated_invaders,
        )

    def _get_invaders_for_city(self, city_code: str) -> list[Invader]:
        """Get invaders for a city from spotter coordinator."""
        if self._spotter.data is None:
            return []
        return self._spotter.data.get(city_code, [])

    def detect_changes(self, city_code: str) -> ChangeSet:
        """Detect new/reactivated invaders since last snapshot.

        Args:
            city_code: City code to check

        Returns:
            ChangeSet with detected changes

        """
        if not self._previous_snapshot:
            return ChangeSet()

        current_invaders = self._get_invaders_for_city(city_code)
        if not current_invaders:
            return ChangeSet()

        current_ids = {inv.id for inv in current_invaders}

        # Find new invaders (not in previous snapshot)
        new_ids = self._previous_snapshot.get_new_invaders(city_code, current_ids)
        new_invaders = [inv for inv in current_invaders if inv.id in new_ids]

        # Find reactivated invaders (status changed from destroyed to OK)
        reactivated = self._previous_snapshot.get_reactivated(current_invaders)

        if new_invaders or reactivated:
            _LOGGER.info(
                "Changes detected for %s: %d new, %d reactivated",
                city_code,
                len(new_invaders),
                len(reactivated),
            )

        return ChangeSet(
            new_invaders=new_invaders,
            reactivated_invaders=reactivated,
        )

    async def async_save_snapshot(self) -> None:
        """Save current state as snapshot for future comparison."""
        if self._spotter.data is None:
            _LOGGER.debug("No spotter data to save")
            return

        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            invader_ids_by_city={
                city: {inv.id for inv in invaders}
                for city, invaders in self._spotter.data.items()
            },
            status_by_invader={
                inv.id: inv.status
                for invaders in self._spotter.data.values()
                for inv in invaders
            },
        )

        await self._store.async_save_snapshot(snapshot)
        self._previous_snapshot = snapshot
        _LOGGER.debug("Saved new snapshot")

    def get_all_tracked_cities(self) -> list[str]:
        """Get list of all tracked city codes."""
        if self._spotter.data is None:
            return []
        return list(self._spotter.data.keys())

    def get_total_stats(self) -> dict[str, int]:
        """Get aggregate stats across all cities.

        Returns:
            Dict with total counts

        """
        total_invaders = 0
        total_flashed = 0
        total_unflashed = 0
        total_gone = 0

        for city_code in self.get_all_tracked_cities():
            stats = self.compute_city_stats(city_code)
            total_invaders += stats.total_count
            total_flashed += stats.flashed_count
            total_unflashed += stats.unflashed_count
            total_gone += stats.unflashed_gone_count

        return {
            "total": total_invaders,
            "flashed": total_flashed,
            "unflashed": total_unflashed,
            "gone": total_gone,
        }
