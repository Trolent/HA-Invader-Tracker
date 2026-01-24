"""Flash Invader API client."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import aiohttp

from ..const import FLASH_INVADER_BASE_URL, FLASH_INVADER_ENDPOINT
from ..exceptions import (
    AuthenticationError,
    FlashInvaderConnectionError,
    InvalidResponseError,
    ParseError,
    RateLimitError,
)
from ..models import FlashedInvader

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class FlashInvaderAPI:
    """Client for Flash Invader API."""

    def __init__(self, session: aiohttp.ClientSession, uid: str) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp client session
            uid: User's Flash Invader UID

        """
        self._session = session
        self._uid = uid

    @property
    def _headers(self) -> dict[str, str]:
        """Build request headers."""
        return {
            "Accept": "*/*",
            "Origin": "https://pnote.eu",
            "Referer": "https://pnote.eu/",
        }

    async def get_flashed_invaders(self) -> list[FlashedInvader]:
        """Fetch all invaders flashed by user.

        Returns:
            List of FlashedInvader objects

        Raises:
            AuthenticationError: If UID is invalid
            FlashInvaderConnectionError: If connection fails
            ParseError: If response cannot be parsed
            RateLimitError: If rate limited

        """
        _LOGGER.debug("Fetching flashed invaders from Flash Invader API")

        try:
            async with self._session.get(
                f"{FLASH_INVADER_BASE_URL}{FLASH_INVADER_ENDPOINT}",
                params={"uid": self._uid},
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                return await self._handle_response(response)

        except TimeoutError as err:
            _LOGGER.warning("Flash Invader API timeout")
            raise FlashInvaderConnectionError("Request timed out") from err

        except aiohttp.ClientError as err:
            _LOGGER.warning(
                "Flash Invader API connection error: %s", type(err).__name__
            )
            raise FlashInvaderConnectionError(f"Connection failed: {err}") from err

    async def _handle_response(
        self, response: aiohttp.ClientResponse
    ) -> list[FlashedInvader]:
        """Handle API response with status-specific error handling."""
        if response.status == 200:
            return await self._parse_response(response)

        if response.status == 401:
            _LOGGER.error("Flash Invader API: Invalid UID")
            raise AuthenticationError("Invalid UID")

        if response.status == 403:
            _LOGGER.error("Flash Invader API: Access forbidden")
            raise AuthenticationError("Access forbidden - UID may be blocked")

        if response.status == 429:
            retry_after = response.headers.get("Retry-After")
            _LOGGER.warning("Flash Invader API: Rate limited")
            raise RateLimitError(int(retry_after) if retry_after else None)

        if response.status == 400:
            body = await response.text()
            _LOGGER.error("Flash Invader API: Bad request (400) - UID format may be invalid. Response: %s", body[:200])
            raise AuthenticationError("Invalid UID format - check that your UID is correct")

        if response.status >= 500:
            _LOGGER.warning("Flash Invader API: Server error %d", response.status)
            raise FlashInvaderConnectionError(f"Server error: {response.status}")

        body = await response.text()
        _LOGGER.error("Flash Invader API: Unexpected status %d. Response: %s", response.status, body[:200])
        raise InvalidResponseError(f"Unexpected status: {response.status}")

    async def _parse_response(
        self, response: aiohttp.ClientResponse
    ) -> list[FlashedInvader]:
        """Parse JSON response."""
        try:
            data = await response.json()
        except (ValueError, aiohttp.ContentTypeError) as err:
            _LOGGER.error("Flash Invader API: Invalid JSON response")
            raise ParseError("Invalid JSON response") from err

        if "invaders" not in data:
            _LOGGER.error("Flash Invader API: Missing 'invaders' key")
            raise InvalidResponseError("Response missing 'invaders' key")

        invaders: list[FlashedInvader] = []
        for inv_id, inv_data in data["invaders"].items():
            try:
                invader = self._parse_invader(inv_id, inv_data)
                invaders.append(invader)
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning("Failed to parse invader %s: %s", inv_id, err)
                # Continue processing other invaders

        _LOGGER.debug("Parsed %d flashed invaders", len(invaders))
        return invaders

    def _parse_invader(self, inv_id: str, data: dict) -> FlashedInvader:
        """Parse a single invader from API response."""
        # Parse install date
        install_date_str = data.get("date_pos", "")
        try:
            install_date = datetime.strptime(install_date_str, "%Y-%m-%d").date()
        except ValueError:
            install_date = datetime.now().date()

        # Parse flash date
        flash_date_str = data.get("date_flash", "")
        try:
            flash_date = datetime.strptime(flash_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            flash_date = datetime.now()

        return FlashedInvader(
            id=inv_id,
            name=data.get("name", inv_id),
            city_id=int(data.get("city_id", 0)),
            points=int(data.get("point", 0)),
            image_url=data.get("image_url", ""),
            install_date=install_date,
            flash_date=flash_date,
        )
