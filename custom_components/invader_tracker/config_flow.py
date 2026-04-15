"""Config flow for Invader Tracker integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api.awazleon import AwazleonClient
from .api.flash_invader import FlashInvaderAPI
from .const import (
    CONF_API_INTERVAL,
    CONF_CITIES,
    CONF_NEW_CITY_DAYS,
    CONF_NEWS_DAYS,
    CONF_SCRAPE_INTERVAL,
    CONF_TRACK_FOLLOWED,
    CONF_UPDATE_INTERVAL,
    CONF_UID,
    DEFAULT_NEW_CITY_DAYS,
    DEFAULT_NEWS_DAYS,
    DEFAULT_TRACK_FOLLOWED,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from .exceptions import AuthenticationError, InvaderTrackerConnectionError

_LOGGER = logging.getLogger(__name__)

# UID validation pattern (UUID v4 format)
UID_PATTERN = re.compile(
    r"^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$",
    re.IGNORECASE,
)

# Predefined interval options: display label -> minutes
INTERVAL_OPTIONS: dict[int, str] = {
    15: "Every 15 minutes",
    30: "Every 30 minutes",
    60: "Every hour",
    120: "Every 2 hours",
    360: "Every 6 hours",
    720: "Every 12 hours",
    1440: "Daily",
    10080: "Weekly",
    43200: "Monthly",
}

# Sentinel value shown in the selector to trigger the custom-value step
_CUSTOM_SENTINEL = 0

NEWS_DAYS_OPTIONS = {
    7: "7 days",
    14: "14 days",
    30: "30 days",
    60: "60 days",
    90: "90 days",
    180: "6 months",
    365: "1 year",
}

NEW_CITY_DAYS_OPTIONS = {
    3: "3 days",
    7: "1 week",
    14: "2 weeks",
    30: "1 month",
}

# Selector options: predefined values + "Custom…" entry
_INTERVAL_SELECTOR_OPTIONS: dict[int, str] = {
    **INTERVAL_OPTIONS,
    _CUSTOM_SENTINEL: "Custom…",
}


def _validate_uid(uid: str) -> bool:
    """Validate UID format."""
    if not uid:
        return False
    return bool(UID_PATTERN.match(uid.strip()))


def _interval_schema(current: int) -> vol.Schema:
    """Build the interval selector schema.

    If the current value is not in the predefined list, we show the
    predefined list + Custom…, defaulting to Custom… so the user can
    edit their existing custom value.
    """
    default = current if current in INTERVAL_OPTIONS else _CUSTOM_SENTINEL
    return vol.Schema({
        vol.Required(CONF_UPDATE_INTERVAL, default=default): vol.In(
            _INTERVAL_SELECTOR_OPTIONS
        ),
    })


def _custom_interval_schema(current: int) -> vol.Schema:
    """Build the custom interval input schema."""
    return vol.Schema({
        vol.Required(CONF_UPDATE_INTERVAL, default=current): vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES),
        ),
    })


class InvaderTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Invader Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._uid: str = ""
        self._cities: dict[str, str] = {}
        self._pending_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> InvaderTrackerOptionsFlow:
        """Get the options flow for this handler."""
        return InvaderTrackerOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - UID entry."""
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
                    _LOGGER.exception("Unexpected error validating UID")
                    errors["base"] = "unknown"

                if not errors:
                    self._uid = uid
                    return await self.async_step_cities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_UID): str}),
            errors=errors,
        )

    async def async_step_cities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle city selection + interval choice step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_cities = user_input.get(CONF_CITIES, [])

            if not selected_cities:
                errors["base"] = "no_cities_selected"
            else:
                cities = {
                    code: self._cities.get(code, code) for code in selected_cities
                }
                chosen_interval = user_input.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
                )

                self._pending_data = {
                    CONF_UID: self._uid,
                    CONF_CITIES: cities,
                }

                if chosen_interval == _CUSTOM_SENTINEL:
                    # Proceed to the custom-value step
                    return await self.async_step_custom_interval()

                self._pending_data[CONF_UPDATE_INTERVAL] = chosen_interval

                await self.async_set_unique_id(self._uid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Invader Tracker",
                    data=self._pending_data,
                )

        # Fetch available cities from awazleon
        session = async_get_clientsession(self.hass)
        awazleon = AwazleonClient(session)

        try:
            cities_list = await awazleon.get_cities()
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

        city_options = dict(sorted(self._cities.items(), key=lambda x: x[1]))

        return self.async_show_form(
            step_id="cities",
            data_schema=vol.Schema({
                vol.Required(CONF_CITIES): cv.multi_select(city_options),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=DEFAULT_UPDATE_INTERVAL_MINUTES,
                ): vol.In(_INTERVAL_SELECTOR_OPTIONS),
            }),
            errors=errors,
        )

    async def async_step_custom_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle custom interval entry (config flow)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            minutes = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES)
            self._pending_data[CONF_UPDATE_INTERVAL] = int(minutes)

            await self.async_set_unique_id(self._uid)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Invader Tracker",
                data=self._pending_data,
            )

        return self.async_show_form(
            step_id="custom_interval",
            data_schema=_custom_interval_schema(DEFAULT_UPDATE_INTERVAL_MINUTES),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            data_schema=vol.Schema({vol.Required(CONF_UID): str}),
            errors=errors,
        )


class InvaderTrackerOptionsFlow(OptionsFlow):
    """Handle options flow for Invader Tracker."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._cities: dict[str, str] = {}
        self._pending_options: dict[str, Any] = {}

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

    def _get_current_interval(self) -> int:
        """Return current update interval in minutes, migrating legacy values."""
        # New key takes precedence
        if CONF_UPDATE_INTERVAL in self._config_entry.options:
            return int(self._config_entry.options[CONF_UPDATE_INTERVAL])
        if CONF_UPDATE_INTERVAL in self._config_entry.data:
            return int(self._config_entry.data[CONF_UPDATE_INTERVAL])
        # Migrate from legacy scrape_interval (hours) — take the smaller of the two
        scrape_h = self._config_entry.options.get(
            CONF_SCRAPE_INTERVAL,
            self._config_entry.data.get(CONF_SCRAPE_INTERVAL, 24),
        )
        api_h = self._config_entry.options.get(
            CONF_API_INTERVAL,
            self._config_entry.data.get(CONF_API_INTERVAL, 1),
        )
        return min(int(scrape_h), int(api_h)) * 60

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow - city selection and interval."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_cities = user_input.get(CONF_CITIES, [])

            if not selected_cities:
                errors["base"] = "no_cities_selected"
            else:
                cities = {
                    code: self._cities.get(code, code) for code in selected_cities
                }
                chosen_interval = user_input.get(CONF_UPDATE_INTERVAL, self._get_current_interval())

                self._pending_options = {
                    CONF_CITIES: cities,
                    CONF_NEWS_DAYS: user_input.get(
                        CONF_NEWS_DAYS,
                        self._get_current_value(CONF_NEWS_DAYS, DEFAULT_NEWS_DAYS),
                    ),
                    CONF_NEW_CITY_DAYS: user_input.get(
                        CONF_NEW_CITY_DAYS,
                        self._get_current_value(CONF_NEW_CITY_DAYS, DEFAULT_NEW_CITY_DAYS),
                    ),
                    CONF_TRACK_FOLLOWED: user_input.get(
                        CONF_TRACK_FOLLOWED,
                        self._get_current_value(CONF_TRACK_FOLLOWED, DEFAULT_TRACK_FOLLOWED),
                    ),
                }

                if chosen_interval == _CUSTOM_SENTINEL:
                    return await self.async_step_custom_interval()

                self._pending_options[CONF_UPDATE_INTERVAL] = chosen_interval
                return self.async_create_entry(title="", data=self._pending_options)

        # Fetch available cities from awazleon
        session = async_get_clientsession(self.hass)
        awazleon = AwazleonClient(session)

        try:
            cities_list = await awazleon.get_cities()
            self._cities = {c.code: c.name for c in cities_list}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error fetching cities for options")
            self._cities = self._get_current_cities()

        current_cities = list(self._get_current_cities().keys())
        current_interval = self._get_current_interval()
        city_options = dict(sorted(self._cities.items(), key=lambda x: x[1]))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_CITIES, default=current_cities
                ): cv.multi_select(city_options),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=current_interval if current_interval in INTERVAL_OPTIONS else _CUSTOM_SENTINEL,
                ): vol.In(_INTERVAL_SELECTOR_OPTIONS),
                vol.Optional(
                    CONF_NEWS_DAYS,
                    default=self._get_current_value(CONF_NEWS_DAYS, DEFAULT_NEWS_DAYS),
                ): vol.In(NEWS_DAYS_OPTIONS),
                vol.Optional(
                    CONF_NEW_CITY_DAYS,
                    default=self._get_current_value(CONF_NEW_CITY_DAYS, DEFAULT_NEW_CITY_DAYS),
                ): vol.In(NEW_CITY_DAYS_OPTIONS),
                vol.Optional(
                    CONF_TRACK_FOLLOWED,
                    default=self._get_current_value(CONF_TRACK_FOLLOWED, DEFAULT_TRACK_FOLLOWED),
                ): bool,
            }),
            errors=errors,
        )

    async def async_step_custom_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle custom interval entry (options flow)."""
        errors: dict[str, str] = {}
        current_interval = self._get_current_interval()

        if user_input is not None:
            minutes = user_input.get(CONF_UPDATE_INTERVAL, current_interval)
            self._pending_options[CONF_UPDATE_INTERVAL] = int(minutes)
            return self.async_create_entry(title="", data=self._pending_options)

        return self.async_show_form(
            step_id="custom_interval",
            data_schema=_custom_interval_schema(
                current_interval if current_interval >= MIN_UPDATE_INTERVAL_MINUTES
                else DEFAULT_UPDATE_INTERVAL_MINUTES
            ),
            errors=errors,
        )
