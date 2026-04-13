"""Config flow for Invader Tracker integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api.flash_invader import FlashInvaderAPI
from .api.invader_spotter import InvaderSpotterScraper
from .const import (
    CONF_API_INTERVAL,
    CONF_CITIES,
    CONF_NEWS_DAYS,
    CONF_SCRAPE_INTERVAL,
    CONF_TRACK_FOLLOWED,
    CONF_UID,
    DEFAULT_API_INTERVAL_HOURS,
    DEFAULT_NEWS_DAYS,
    DEFAULT_SCRAPE_INTERVAL_HOURS,
    DEFAULT_TRACK_FOLLOWED,
    DOMAIN,
)
from .exceptions import AuthenticationError, InvaderTrackerConnectionError

_LOGGER = logging.getLogger(__name__)

# UID validation pattern (UUID v4 format)
UID_PATTERN = re.compile(
    r"^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$",
    re.IGNORECASE,
)

INTERVAL_OPTIONS = {
    1: "Every hour",
    6: "Every 6 hours",
    12: "Every 12 hours",
    24: "Daily",
    168: "Weekly",
    720: "Monthly",
}

API_INTERVAL_OPTIONS = {
    1: "Every hour",
    6: "Every 6 hours",
    12: "Every 12 hours",
    24: "Daily",
}

NEWS_DAYS_OPTIONS = {
    7: "7 days",
    14: "14 days",
    30: "30 days",
    60: "60 days",
    90: "90 days",
    180: "6 months",
    365: "1 year",
}


def _validate_uid(uid: str) -> bool:
    """Validate UID format."""
    if not uid:
        return False
    return bool(UID_PATTERN.match(uid.strip()))


class InvaderTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Invader Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._uid: str = ""
        self._cities: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> InvaderTrackerOptionsFlow:
        """Get the options flow for this handler."""
        return InvaderTrackerOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - UID entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uid = user_input[CONF_UID].strip()

            # Format validation first (cheap)
            if not _validate_uid(uid):
                errors["base"] = "invalid_uid_format"
            else:
                # API validation (expensive)
                session = async_get_clientsession(self.hass)
                api = FlashInvaderAPI(session, uid)

                try:
                    await api.get_flashed_invaders()
                except AuthenticationError:
                    errors["base"] = "invalid_uid"
                except InvaderTrackerConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error validating UID")
                    errors["base"] = "unknown"

                if not errors:
                    # UID is valid, proceed to city selection
                    self._uid = uid
                    return await self.async_step_cities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UID): str,
                }
            ),
            errors=errors,
        )

    async def async_step_cities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle city selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_cities = user_input.get(CONF_CITIES, [])

            if not selected_cities:
                errors["base"] = "no_cities_selected"
            else:
                # Build cities dict from selection
                cities = {
                    code: self._cities.get(code, code) for code in selected_cities
                }

                # Check for existing entry with same UID
                await self.async_set_unique_id(self._uid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Invader Tracker",
                    data={
                        CONF_UID: self._uid,
                        CONF_CITIES: cities,
                        CONF_SCRAPE_INTERVAL: user_input.get(
                            CONF_SCRAPE_INTERVAL, DEFAULT_SCRAPE_INTERVAL_HOURS
                        ),
                        CONF_API_INTERVAL: user_input.get(
                            CONF_API_INTERVAL, DEFAULT_API_INTERVAL_HOURS
                        ),
                    },
                )

        # Fetch available cities
        session = async_get_clientsession(self.hass)
        scraper = InvaderSpotterScraper(session)

        try:
            cities_list = await scraper.get_cities()
            self._cities = {c.code: c.name for c in cities_list}
        except InvaderTrackerConnectionError:
            errors["base"] = "cannot_connect_spotter"
            self._cities = {}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error fetching cities")
            errors["base"] = "unknown"
            self._cities = {}

        if not self._cities and not errors:
            errors["base"] = "no_cities_found"

        # Sort cities by name for display
        city_options = dict(
            sorted(self._cities.items(), key=lambda x: x[1])
        )

        return self.async_show_form(
            step_id="cities",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CITIES): cv.multi_select(city_options),
                    vol.Optional(
                        CONF_SCRAPE_INTERVAL, default=DEFAULT_SCRAPE_INTERVAL_HOURS
                    ): vol.In(INTERVAL_OPTIONS),
                    vol.Optional(
                        CONF_API_INTERVAL, default=DEFAULT_API_INTERVAL_HOURS
                    ): vol.In(API_INTERVAL_OPTIONS),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uid = user_input[CONF_UID].strip()

            if not _validate_uid(uid):
                errors["base"] = "invalid_uid_format"
            else:
                session = async_get_clientsession(self.hass)
                api = FlashInvaderAPI(session, uid)

                try:
                    await api.get_flashed_invaders()
                except AuthenticationError:
                    errors["base"] = "invalid_uid"
                except InvaderTrackerConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    errors["base"] = "unknown"

                if not errors:
                    # Update the config entry with new UID
                    existing_entry = await self.async_set_unique_id(uid)
                    if existing_entry:
                        self.hass.config_entries.async_update_entry(
                            existing_entry,
                            data={**existing_entry.data, CONF_UID: uid},
                        )
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UID): str,
                }
            ),
            errors=errors,
        )


class InvaderTrackerOptionsFlow(OptionsFlow):
    """Handle options flow for Invader Tracker."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._cities: dict[str, str] = {}

    def _get_current_cities(self) -> dict[str, str]:
        """Get currently configured cities (options override data)."""
        return (
            self._config_entry.options.get(CONF_CITIES)
            or self._config_entry.data.get(CONF_CITIES, {})
        )

    def _get_current_value(self, key: str, default: Any) -> Any:
        """Get current config value (options override data)."""
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_cities = user_input.get(CONF_CITIES, [])

            if not selected_cities:
                errors["base"] = "no_cities_selected"
            else:
                # Build cities dict from selection
                cities = {
                    code: self._cities.get(code, code) for code in selected_cities
                }

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_CITIES: cities,
                        CONF_SCRAPE_INTERVAL: user_input.get(
                            CONF_SCRAPE_INTERVAL,
                            self._get_current_value(
                                CONF_SCRAPE_INTERVAL, DEFAULT_SCRAPE_INTERVAL_HOURS
                            ),
                        ),
                        CONF_API_INTERVAL: user_input.get(
                            CONF_API_INTERVAL,
                            self._get_current_value(
                                CONF_API_INTERVAL, DEFAULT_API_INTERVAL_HOURS
                            ),
                        ),
                        CONF_NEWS_DAYS: user_input.get(
                            CONF_NEWS_DAYS,
                            self._get_current_value(
                                CONF_NEWS_DAYS, DEFAULT_NEWS_DAYS
                            ),
                        ),
                        CONF_TRACK_FOLLOWED: user_input.get(
                            CONF_TRACK_FOLLOWED,
                            self._get_current_value(
                                CONF_TRACK_FOLLOWED, DEFAULT_TRACK_FOLLOWED
                            ),
                        ),
                    },
                )

        # Fetch available cities
        session = async_get_clientsession(self.hass)
        scraper = InvaderSpotterScraper(session)

        try:
            cities_list = await scraper.get_cities()
            self._cities = {c.code: c.name for c in cities_list}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error fetching cities for options")
            # Use previously configured cities as fallback
            self._cities = self._get_current_cities()

        # Get currently selected cities (from options first, then data)
        current_cities = list(self._get_current_cities().keys())

        # Sort cities by name for display
        city_options = dict(sorted(self._cities.items(), key=lambda x: x[1]))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CITIES, default=current_cities
                    ): cv.multi_select(city_options),
                    vol.Optional(
                        CONF_SCRAPE_INTERVAL,
                        default=self._get_current_value(
                            CONF_SCRAPE_INTERVAL, DEFAULT_SCRAPE_INTERVAL_HOURS
                        ),
                    ): vol.In(INTERVAL_OPTIONS),
                    vol.Optional(
                        CONF_API_INTERVAL,
                        default=self._get_current_value(
                            CONF_API_INTERVAL, DEFAULT_API_INTERVAL_HOURS
                        ),
                    ): vol.In(API_INTERVAL_OPTIONS),
                    vol.Optional(
                        CONF_NEWS_DAYS,
                        default=self._get_current_value(
                            CONF_NEWS_DAYS, DEFAULT_NEWS_DAYS
                        ),
                    ): vol.In(NEWS_DAYS_OPTIONS),
                    vol.Optional(
                        CONF_TRACK_FOLLOWED,
                        default=self._get_current_value(
                            CONF_TRACK_FOLLOWED, DEFAULT_TRACK_FOLLOWED
                        ),
                    ): bool,
                }
            ),
            errors=errors,
        )
