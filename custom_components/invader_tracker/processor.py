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

    def detect_changes(self, city_code: str, recently_added_days: int = 30) -> ChangeSet:
        """Detect new/reactivated invaders since last snapshot.

        Args:
            city_code: City code to check
            recently_added_days: Consider invaders "new" if first seen within N days

        Returns:
            ChangeSet with detected changes

        """
        if not self._previous_snapshot:
            return ChangeSet()

        current_invaders = self._get_invaders_for_city(city_code)
        if not current_invaders:
            return ChangeSet()

        # Get recently added invaders (first seen within N days)
        new_invaders = self._previous_snapshot.get_recently_added(
            current_invaders, days=recently_added_days
        )

        # Get reactivated invaders (status changed from non-flashable to flashable)
        reactivated = self._previous_snapshot.get_reactivated(current_invaders)

        if new_invaders or reactivated:
            _LOGGER.info(
                "Changes for %s: %d recently added (<%d days), %d reactivated",
                city_code,
                len(new_invaders),
                recently_added_days,
                len(reactivated),
            )

        return ChangeSet(
            new_invaders=new_invaders,
            reactivated_invaders=reactivated,
        )

    async def async_save_snapshot(self) -> None:
        """Save current state as snapshot for future comparison.
        
        This preserves first_seen dates and tracks status changes.
        """
        if self._spotter.data is None:
            _LOGGER.debug("No spotter data to save")
            return

        now = datetime.now()
        
        # Build current IDs and statuses
        current_ids_by_city = {
            city: {inv.id for inv in invaders}
            for city, invaders in self._spotter.data.items()
        }
        current_status = {
            inv.id: inv.status
            for invaders in self._spotter.data.values()
            for inv in invaders
        }
        
        # Preserve first_seen dates from previous snapshot, add new ones
        first_seen = {}
        if self._previous_snapshot:
            first_seen = dict(self._previous_snapshot.first_seen_date)
        
        # Add first_seen for newly discovered invaders
        for invaders in self._spotter.data.values():
            for inv in invaders:
                if inv.id not in first_seen:
                    first_seen[inv.id] = now
                    _LOGGER.debug("New invader discovered: %s", inv.id)
        
        # Track previous status (current status becomes previous for next comparison)
        # Only update if status changed (to preserve history)
        previous_status = {}
        if self._previous_snapshot:
            previous_status = dict(self._previous_snapshot.previous_status)
        
        for inv_id, status in current_status.items():
            old_status = self._previous_snapshot.status_by_invader.get(inv_id) if self._previous_snapshot else None
            if old_status and old_status != status:
                # Status changed - record the old status for reactivation detection
                previous_status[inv_id] = old_status
                _LOGGER.info(
                    "Status change detected: %s went from %s to %s",
                    inv_id, old_status.value, status.value
                )

        snapshot = StateSnapshot(
            timestamp=now,
            invader_ids_by_city=current_ids_by_city,
            status_by_invader=current_status,
            first_seen_date=first_seen,
            previous_status=previous_status,
        )

        await self._store.async_save_snapshot(snapshot)
        self._previous_snapshot = snapshot
        _LOGGER.debug("Saved snapshot with %d invaders tracked", len(current_status))

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
