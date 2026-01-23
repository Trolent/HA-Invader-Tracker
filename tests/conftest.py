"""Pytest fixtures for Invader Tracker tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.invader_tracker.const import DOMAIN
from custom_components.invader_tracker.models import (
    FlashedInvader,
    Invader,
    InvaderStatus,
)

from datetime import datetime, date


@pytest.fixture
def mock_config_entry_data() -> dict:
    """Create mock config entry data."""
    return {
        "uid": "TEST-UID-1234-5678-9ABC-DEF012345678",
        "cities": {"PA": "Paris", "LYN": "Lyon"},
        "scrape_interval": 24,
        "api_interval": 1,
    }


@pytest.fixture
def mock_flash_invader_response() -> dict:
    """Create mock Flash Invader API response."""
    return {
        "invaders": {
            "PA_001": {
                "name": "PA_001",
                "point": 10,
                "city_id": 1,
                "image_url": "https://example.com/pa001.jpg",
                "date_pos": "2000-01-01",
                "date_flash": "2024-01-15 10:30:00",
            },
            "PA_002": {
                "name": "PA_002",
                "point": 20,
                "city_id": 1,
                "image_url": "https://example.com/pa002.jpg",
                "date_pos": "2000-01-02",
                "date_flash": "2024-02-20 14:45:00",
            },
            "LYN_001": {
                "name": "LYN_001",
                "point": 30,
                "city_id": 2,
                "image_url": "https://example.com/lyn001.jpg",
                "date_pos": "2005-03-15",
                "date_flash": "2024-03-10 09:00:00",
            },
        }
    }


@pytest.fixture
def mock_flashed_invaders() -> list[FlashedInvader]:
    """Create mock FlashedInvader objects."""
    return [
        FlashedInvader(
            id="PA_001",
            name="PA_001",
            city_id=1,
            points=10,
            image_url="https://example.com/pa001.jpg",
            install_date=date(2000, 1, 1),
            flash_date=datetime(2024, 1, 15, 10, 30, 0),
        ),
        FlashedInvader(
            id="PA_002",
            name="PA_002",
            city_id=1,
            points=20,
            image_url="https://example.com/pa002.jpg",
            install_date=date(2000, 1, 2),
            flash_date=datetime(2024, 2, 20, 14, 45, 0),
        ),
    ]


@pytest.fixture
def mock_invaders_paris() -> list[Invader]:
    """Create mock Invader objects for Paris."""
    return [
        Invader(
            id="PA_001",
            city_code="PA",
            city_name="Paris",
            points=10,
            status=InvaderStatus.OK,
            install_date=date(2000, 1, 1),
        ),
        Invader(
            id="PA_002",
            city_code="PA",
            city_name="Paris",
            points=20,
            status=InvaderStatus.OK,
            install_date=date(2000, 1, 2),
        ),
        Invader(
            id="PA_003",
            city_code="PA",
            city_name="Paris",
            points=30,
            status=InvaderStatus.OK,
            install_date=date(2000, 1, 3),
        ),
        Invader(
            id="PA_004",
            city_code="PA",
            city_name="Paris",
            points=40,
            status=InvaderStatus.DESTROYED,
            install_date=date(2000, 1, 4),
        ),
    ]


@pytest.fixture
def mock_invader_spotter_cities_html() -> str:
    """Create mock HTML for cities page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Villes</title></head>
    <body>
    <h1>Liste des villes</h1>
    <ul>
        <li><a href="ville.php?ville=PA">Paris</a></li>
        <li><a href="ville.php?ville=LYN">Lyon</a></li>
        <li><a href="ville.php?ville=MRS">Marseille</a></li>
    </ul>
    </body>
    </html>
    """


@pytest.fixture
def mock_invader_spotter_paris_html() -> str:
    """Create mock HTML for Paris invaders page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Paris</title></head>
    <body>
    <h1>Invaders à Paris</h1>
    <div class="invader">
        <a href="invader.php?id=PA_001">PA_001</a> [10 pts]<br>
        Date de pose : 01/01/2000<br>
        Dernier état connu : OK<br>
        Date et source : janvier 2024 (spott)
    </div>
    <div class="invader">
        <a href="invader.php?id=PA_002">PA_002</a> [20 pts]<br>
        Date de pose : 02/01/2000<br>
        Dernier état connu : OK<br>
        Date et source : février 2024 (user)
    </div>
    <div class="invader">
        <a href="invader.php?id=PA_003">PA_003</a> [30 pts]<br>
        Date de pose : 03/01/2000<br>
        Dernier état connu : OK<br>
        Date et source : mars 2024 (spott)
    </div>
    <div class="invader">
        <a href="invader.php?id=PA_004">PA_004</a> [40 pts]<br>
        Date de pose : 04/01/2000<br>
        Dernier état connu : Détruit<br>
        Date et source : avril 2024 (spott)
    </div>
    </body>
    </html>
    """
