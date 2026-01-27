"""Tests for sensor entities."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.invader_tracker.const import (
    DOMAIN,
    SENSOR_FLASHED,
    SENSOR_NEW,
    SENSOR_TO_FLASH,
    SENSOR_TOTAL,
    SENSOR_UNFLASHED,
    SENSOR_UNFLASHED_GONE,
)
from custom_components.invader_tracker.models import (
    City,
    CityStats,
    FlashedInvader,
    Invader,
    InvaderStatus,
)
from custom_components.invader_tracker.sensor import (
    InvaderFlashedSensor,
    InvaderNewSensor,
    InvaderToFlashSensor,
    InvaderTotalSensor,
    InvaderUnflashedGoneSensor,
    InvaderUnflashedSensor,
)


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"PA": []}
    return coordinator


@pytest.fixture
def mock_processor() -> MagicMock:
    """Create a mock processor."""
    processor = MagicMock()
    invaders = [
        Invader(id="PA_001", city_code="PA", city_name="Paris", points=10, status=InvaderStatus.OK),
        Invader(id="PA_002", city_code="PA", city_name="Paris", points=20, status=InvaderStatus.OK),
        Invader(id="PA_003", city_code="PA", city_name="Paris", points=30, status=InvaderStatus.DESTROYED),
    ]
    flashed = [
        FlashedInvader(
            id="PA_001", name="PA_001", city_id=1, points=10,
            image_url="", install_date=date(2000, 1, 1),
            flash_date=datetime(2024, 1, 15, 10, 30, 0),
        ),
    ]
    city = City(code="PA", name="Paris", total_invaders=3)
    stats = CityStats(
        city=city,
        all_invaders=invaders,
        flashed_invaders=flashed,
        new_invaders=[invaders[1]],  # PA_002 is new
        reactivated_invaders=[],
    )
    processor.compute_city_stats = MagicMock(return_value=stats)
    return processor


@pytest.fixture
def mock_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    return entry


class TestInvaderTotalSensor:
    """Tests for InvaderTotalSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test total count."""
        sensor = InvaderTotalSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        assert sensor.native_value == 3

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include invader IDs and flashable count."""
        sensor = InvaderTotalSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        attrs = sensor.extra_state_attributes

        assert "invader_ids" in attrs
        assert len(attrs["invader_ids"]) == 3
        assert attrs["flashable_count"] == 2  # PA_001 and PA_002

    def test_unavailable(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test sensor returns None when unavailable."""
        mock_coordinator.data = None
        sensor = InvaderTotalSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    def test_unique_id(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test unique ID format."""
        sensor = InvaderTotalSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        assert sensor.unique_id == f"test_entry_PA_{SENSOR_TOTAL}"

    def test_device_info(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test device info."""
        sensor = InvaderTotalSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        info = sensor.device_info
        assert (DOMAIN, "test_entry_PA") in info["identifiers"]
        assert "Paris" in info["name"]


class TestInvaderFlashedSensor:
    """Tests for InvaderFlashedSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test flashed count."""
        sensor = InvaderFlashedSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        assert sensor.native_value == 1

    def test_attributes_with_flash_date(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include flash_date as ISO string."""
        sensor = InvaderFlashedSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        attrs = sensor.extra_state_attributes

        assert len(attrs["invaders"]) == 1
        assert attrs["invaders"][0]["id"] == "PA_001"
        assert attrs["invaders"][0]["flash_date"] == "2024-01-15T10:30:00"
        assert attrs["total_points"] == 10

    def test_attributes_with_none_flash_date(
        self, mock_coordinator, mock_processor, mock_entry
    ) -> None:
        """Test attributes handle None flash_date without crashing."""
        # Override with a flashed invader that has None flash_date
        stats = mock_processor.compute_city_stats.return_value
        stats.flashed_invaders = [
            FlashedInvader(
                id="PA_001", name="PA_001", city_id=1, points=10,
                image_url="", install_date=None, flash_date=None,
            ),
        ]

        sensor = InvaderFlashedSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        attrs = sensor.extra_state_attributes

        # Should not crash - flash_date should be None
        assert attrs["invaders"][0]["flash_date"] is None


class TestInvaderUnflashedSensor:
    """Tests for InvaderUnflashedSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test unflashed count (only flashable, not flashed)."""
        sensor = InvaderUnflashedSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        # PA_002 is OK and not flashed
        assert sensor.native_value == 1

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include invader details."""
        sensor = InvaderUnflashedSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        attrs = sensor.extra_state_attributes

        assert len(attrs["invaders"]) == 1
        assert attrs["invaders"][0]["id"] == "PA_002"
        assert attrs["invaders"][0]["status"] == "ok"
        assert attrs["total_points"] == 20


class TestInvaderUnflashedGoneSensor:
    """Tests for InvaderUnflashedGoneSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test unflashed gone count."""
        sensor = InvaderUnflashedGoneSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        # PA_003 is DESTROYED and not flashed
        assert sensor.native_value == 1

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include missed invader details."""
        sensor = InvaderUnflashedGoneSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        attrs = sensor.extra_state_attributes

        assert len(attrs["invaders"]) == 1
        assert attrs["invaders"][0]["id"] == "PA_003"
        assert attrs["invaders"][0]["status"] == "destroyed"
        assert attrs["missed_points"] == 30


class TestInvaderNewSensor:
    """Tests for InvaderNewSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test new + reactivated count (unflashed only)."""
        sensor = InvaderNewSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        # PA_002 is new and not flashed
        assert sensor.native_value == 1

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include new/reactivated breakdown."""
        sensor = InvaderNewSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        attrs = sensor.extra_state_attributes

        assert attrs["new_count"] == 1
        assert attrs["reactivated_count"] == 0
        assert attrs["potential_points"] == 20


class TestInvaderToFlashSensor:
    """Tests for InvaderToFlashSensor."""

    def test_native_value_with_targets(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test CSV list of invader IDs."""
        sensor = InvaderToFlashSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        # PA_002 is new and not flashed
        assert sensor.native_value == "PA_002"

    def test_native_value_no_targets(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test 'Aucun' when no targets."""
        stats = mock_processor.compute_city_stats.return_value
        stats.new_invaders = []
        stats.reactivated_invaders = []

        sensor = InvaderToFlashSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        assert sensor.native_value == "Aucun"

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include breakdown."""
        sensor = InvaderToFlashSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        attrs = sensor.extra_state_attributes

        assert attrs["new_count"] == 1
        assert attrs["reactivated_count"] == 0
        assert attrs["total_count"] == 1
        assert attrs["potential_points"] == 20

    def test_unavailable(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test sensor returns None when unavailable."""
        mock_coordinator.last_update_success = False
        sensor = InvaderToFlashSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    def test_unique_id(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test unique ID format."""
        sensor = InvaderToFlashSensor(
            mock_coordinator, mock_processor, mock_entry, "PA", "Paris"
        )
        assert sensor.unique_id == f"test_entry_PA_{SENSOR_TO_FLASH}"
