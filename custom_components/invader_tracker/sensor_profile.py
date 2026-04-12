"""Profile sensor entities for Invader Tracker integration."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import FlashInvaderProfileCoordinator
    from .models import FollowedPlayer

_LOGGER = logging.getLogger(__name__)


async def async_setup_profile_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up profile and followed player sensor entities."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: FlashInvaderProfileCoordinator = runtime_data["profile_coordinator"]

    entities: list[SensorEntity] = [
        PlayerScoreSensor(coordinator, entry),
        PlayerRankSensor(coordinator, entry),
        PlayerInvadersFoundSensor(coordinator, entry),
        PlayerCitiesFoundSensor(coordinator, entry),
    ]

    # Add one sensor per followed player (based on current data)
    if coordinator.data:
        for player in coordinator.followed_players:
            entities.append(FollowedPlayerSensor(coordinator, entry, player.name))

    async_add_entities(entities)


def _profile_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return device info for the profile device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_profile")},
        name="Invader Tracker - Profil",
        manufacturer="Space Invader",
        model="Player Profile",
    )


def _slugify(name: str) -> str:
    """Convert a player name to a safe entity id suffix."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")


class ProfileBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for profile sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FlashInvaderProfileCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_profile_{sensor_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return _profile_device_info(self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


class PlayerScoreSensor(ProfileBaseSensor):
    """Sensor for the player's total score."""

    _attr_icon = "mdi:trophy"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "score")
        self._attr_name = "Score"

    @property
    def native_value(self) -> int | None:
        """Return the score."""
        if not self.available:
            return None
        return self.coordinator.profile.score

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rank as attribute."""
        if not self.available:
            return {}
        profile = self.coordinator.profile
        return {
            "rank": profile.rank,
            "rank_str": profile.rank_str,
        }


class PlayerRankSensor(ProfileBaseSensor):
    """Sensor for the player's global rank."""

    _attr_icon = "mdi:podium"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "rank")
        self._attr_name = "Rank"

    @property
    def native_value(self) -> int | None:
        """Return the rank."""
        if not self.available:
            return None
        return self.coordinator.profile.rank


class PlayerInvadersFoundSensor(ProfileBaseSensor):
    """Sensor for total invaders found by the player."""

    _attr_icon = "mdi:space-invaders"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "invaders_found")
        self._attr_name = "Invaders Found"

    @property
    def native_value(self) -> int | None:
        """Return the total invaders found."""
        if not self.available:
            return None
        return self.coordinator.profile.si_found


class PlayerCitiesFoundSensor(ProfileBaseSensor):
    """Sensor for total cities where the player has flashed at least one invader."""

    _attr_icon = "mdi:city"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "cities_found")
        self._attr_name = "Cities Found"

    @property
    def native_value(self) -> int | None:
        """Return the number of cities."""
        if not self.available:
            return None
        return self.coordinator.profile.city_found


class FollowedPlayerSensor(CoordinatorEntity, SensorEntity):
    """Sensor tracking a followed player's score."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:account-star"

    def __init__(
        self,
        coordinator: FlashInvaderProfileCoordinator,
        entry: ConfigEntry,
        player_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._player_name = player_name
        self._attr_unique_id = f"{entry.entry_id}_followed_{_slugify(player_name)}"
        self._attr_name = player_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return _profile_device_info(self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    def _get_player(self) -> FollowedPlayer | None:
        """Find this player in coordinator data."""
        for p in self.coordinator.followed_players:
            if p.name == self._player_name:
                return p
        return None

    @property
    def native_value(self) -> int | None:
        """Return the player's score."""
        if not self.available:
            return None
        player = self._get_player()
        return player.score if player else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rank and invaders count."""
        if not self.available:
            return {}
        player = self._get_player()
        if not player:
            return {}
        return {
            "rank": player.rank,
            "rank_str": player.rank_str,
            "invaders_count": player.invaders_count,
        }
