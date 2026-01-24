"""Constants for Invader Tracker integration."""
from typing import Final

DOMAIN: Final = "invader_tracker"

# Configuration keys
CONF_UID: Final = "uid"
CONF_CITIES: Final = "cities"
CONF_SCRAPE_INTERVAL: Final = "scrape_interval"
CONF_API_INTERVAL: Final = "api_interval"

# Defaults
DEFAULT_SCRAPE_INTERVAL_HOURS: Final = 24
DEFAULT_API_INTERVAL_HOURS: Final = 1
MIN_SCRAPE_INTERVAL_HOURS: Final = 1
MAX_SCRAPE_INTERVAL_HOURS: Final = 720  # 30 days
MIN_API_INTERVAL_HOURS: Final = 1
MAX_API_INTERVAL_HOURS: Final = 24

# API URLs
FLASH_INVADER_BASE_URL: Final = "https://api.space-invaders.com"
FLASH_INVADER_ENDPOINT: Final = "/flashinvaders_v3_pas_trop_predictif/api/gallery"
INVADER_SPOTTER_BASE_URL: Final = "https://www.invader-spotter.art"

# Storage
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}_state"

# Coordinator names
COORDINATOR_SPOTTER: Final = "invader_spotter"
COORDINATOR_FLASH: Final = "flash_invader"

# Entity naming
SENSOR_TOTAL: Final = "total"
SENSOR_FLASHED: Final = "flashed"
SENSOR_UNFLASHED: Final = "unflashed"
SENSOR_UNFLASHED_GONE: Final = "unflashed_gone"
SENSOR_NEW: Final = "new"
BINARY_SENSOR_HAS_NEW: Final = "has_new"

# Rate limiting
CITY_REQUEST_DELAY: Final = 2.0  # seconds between city requests
