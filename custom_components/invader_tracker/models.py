"""Data models for Invader Tracker integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class InvaderStatus(Enum):
    """Status from invader-spotter community data."""

    OK = "ok"  # Intact, flashable
    DAMAGED = "damaged"  # Partially damaged, may be flashable
    DESTROYED = "destroyed"  # Gone, unflashable
    UNKNOWN = "unknown"  # No recent report


@dataclass
class Invader:
    """Represents an invader from invader-spotter.art."""

    id: str  # e.g., "PA_346", "LYN_042"
    city_code: str  # e.g., "PA", "LYN"
    city_name: str  # e.g., "Paris", "Lyon"
    points: int  # Point value (10-100)
    status: InvaderStatus  # Current known status
    install_date: date | None = None  # Date de pose
    status_date: date | None = None  # When status was last reported
    status_source: str | None = None  # Who reported (e.g., "spott", "user")

    @property
    def is_flashable(self) -> bool:
        """Can this invader still be flashed?"""
        return self.status in (InvaderStatus.OK, InvaderStatus.DAMAGED)


@dataclass
class FlashedInvader:
    """Represents an invader the user has flashed."""

    id: str  # e.g., "PA_346"
    name: str  # Same as ID typically
    city_id: int  # Numeric city ID from API
    points: int  # Points earned
    image_url: str  # URL to invader image
    install_date: date  # date_pos from API
    flash_date: datetime  # When user flashed it


@dataclass
class City:
    """Represents a city with invaders."""

    code: str  # e.g., "PA", "LYN"
    name: str  # e.g., "Paris", "Lyon"
    country: str = ""  # e.g., "France"
    total_invaders: int = 0  # Count from invader-spotter
    api_city_id: int | None = None  # Numeric ID from Flash Invader API


@dataclass
class CityStats:
    """Computed statistics for a tracked city."""

    city: City
    all_invaders: list[Invader] = field(default_factory=list)
    flashed_invaders: list[FlashedInvader] = field(default_factory=list)
    new_invaders: list[Invader] = field(default_factory=list)
    reactivated_invaders: list[Invader] = field(default_factory=list)

    @property
    def flashed_ids(self) -> set[str]:
        """Get set of flashed invader IDs."""
        return {inv.id for inv in self.flashed_invaders}

    @property
    def unflashed(self) -> list[Invader]:
        """Invaders not flashed AND still flashable."""
        return [
            inv
            for inv in self.all_invaders
            if inv.id not in self.flashed_ids and inv.is_flashable
        ]

    @property
    def unflashed_gone(self) -> list[Invader]:
        """Invaders not flashed AND no longer flashable (missed)."""
        return [
            inv
            for inv in self.all_invaders
            if inv.id not in self.flashed_ids and not inv.is_flashable
        ]

    @property
    def total_count(self) -> int:
        """Total invaders in city."""
        return len(self.all_invaders)

    @property
    def flashed_count(self) -> int:
        """Number of flashed invaders."""
        return len(self.flashed_invaders)

    @property
    def unflashed_count(self) -> int:
        """Number of unflashed but flashable invaders."""
        return len(self.unflashed)

    @property
    def unflashed_gone_count(self) -> int:
        """Number of unflashed and no longer flashable invaders."""
        return len(self.unflashed_gone)

    @property
    def new_count(self) -> int:
        """Number of new + reactivated invaders."""
        return len(self.new_invaders) + len(self.reactivated_invaders)


@dataclass
class StateSnapshot:
    """Snapshot of state for detecting changes."""

    timestamp: datetime
    invader_ids_by_city: dict[str, set[str]] = field(default_factory=dict)
    status_by_invader: dict[str, InvaderStatus] = field(default_factory=dict)

    def get_new_invaders(self, city_code: str, current_ids: set[str]) -> set[str]:
        """Return IDs that are in current but not in snapshot."""
        previous = self.invader_ids_by_city.get(city_code, set())
        return current_ids - previous

    def get_reactivated(self, current_invaders: list[Invader]) -> list[Invader]:
        """Return invaders whose status changed from destroyed to OK."""
        reactivated = []
        for inv in current_invaders:
            prev_status = self.status_by_invader.get(inv.id)
            if prev_status == InvaderStatus.DESTROYED and inv.status == InvaderStatus.OK:
                reactivated.append(inv)
        return reactivated


@dataclass
class ChangeSet:
    """Changes detected since last snapshot."""

    new_invaders: list[Invader] = field(default_factory=list)
    reactivated_invaders: list[Invader] = field(default_factory=list)
    newly_destroyed: list[Invader] = field(default_factory=list)
