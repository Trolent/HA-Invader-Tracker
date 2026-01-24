"""Invader Spotter scraper."""
from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

import aiohttp
from bs4 import BeautifulSoup

from ..const import INVADER_SPOTTER_BASE_URL
from ..exceptions import InvaderSpotterConnectionError, ParseError
from ..models import City, Invader, InvaderStatus

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

# Regex patterns
INVADER_ID_PATTERN = re.compile(r"^[A-Z]{2,5}_\d{1,4}$")
POINTS_PATTERN = re.compile(r"\[(\d+)\s*pts?\]", re.IGNORECASE)
DATE_PATTERN_FR = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# Status mappings (French to enum) - based on invader-spotter.art values
# Flashable: OK, Dégradé, Très dégradé
# NOT flashable: Détruit, Non visible, Inconnu
STATUS_MAPPING: dict[str, InvaderStatus] = {
    # OK status
    "ok": InvaderStatus.OK,
    "intact": InvaderStatus.OK,
    # Damaged (flashable)
    "dégradé": InvaderStatus.DAMAGED,
    "un peu dégradé": InvaderStatus.DAMAGED,
    # Very damaged (flashable)
    "très dégradé": InvaderStatus.VERY_DAMAGED,
    # Destroyed (NOT flashable)
    "détruit": InvaderStatus.DESTROYED,
    "détruit !": InvaderStatus.DESTROYED,
    "disparu": InvaderStatus.DESTROYED,
    # Not visible (NOT flashable)
    "non visible": InvaderStatus.NOT_VISIBLE,
    # Unknown (NOT flashable)
    "inconnu": InvaderStatus.UNKNOWN,
}


class InvaderSpotterScraper:
    """Scraper for invader-spotter.art."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the scraper.

        Args:
            session: aiohttp client session

        """
        self._session = session

    async def get_cities(self) -> list[City]:
        """Scrape list of all cities.

        Returns:
            List of City objects

        Raises:
            InvaderSpotterConnectionError: If connection fails
            ParseError: If page cannot be parsed

        """
        _LOGGER.debug("Fetching cities from invader-spotter.art")
        url = f"{INVADER_SPOTTER_BASE_URL}/villes.php"

        try:
            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    raise InvaderSpotterConnectionError(
                        f"HTTP {response.status} fetching cities"
                    )

                html_content = await response.text()
                return self._parse_cities_page(html_content)

        except TimeoutError as err:
            _LOGGER.warning("Invader Spotter timeout fetching cities")
            raise InvaderSpotterConnectionError("Timeout fetching cities") from err

        except aiohttp.ClientError as err:
            _LOGGER.warning("Invader Spotter connection error: %s", type(err).__name__)
            raise InvaderSpotterConnectionError(str(err)) from err

    def _parse_cities_page(self, html_content: str) -> list[City]:
        """Parse cities list page."""
        soup = BeautifulSoup(html_content, "html.parser")
        cities: list[City] = []
        seen_codes: set[str] = set()

        # Look for city links - they use javascript:envoi("CODE") format
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            
            # Match javascript:envoi("CODE") pattern
            match = re.search(r"javascript:envoi\(['\"]([A-Z0-9_]+)['\"]\)", href, re.IGNORECASE)
            if match:
                city_code = match.group(1).upper()
                
                # Skip if already seen (avoid duplicates from map and list)
                if city_code in seen_codes:
                    continue
                seen_codes.add(city_code)
                
                city_name = link.get_text(strip=True) or city_code

                # Clean up city name
                city_name = html.unescape(city_name)

                cities.append(
                    City(
                        code=city_code,
                        name=city_name,
                    )
                )

        _LOGGER.debug("Found %d cities", len(cities))
        return cities

    async def get_city_invaders(self, city_code: str, city_name: str = "") -> list[Invader]:
        """Scrape all invaders for a city (handles pagination).

        Args:
            city_code: City code (e.g., "PA", "LYN")
            city_name: City name (optional, for Invader objects)

        Returns:
            List of Invader objects

        Raises:
            InvaderSpotterConnectionError: If connection fails
            ParseError: If page cannot be parsed

        """
        _LOGGER.debug("Fetching invaders for city %s", city_code)
        
        all_invaders: list[Invader] = []
        page = 1
        max_pages = 100  # Safety limit
        
        while page <= max_pages:
            invaders, has_more = await self._fetch_city_page(
                city_code, city_name, page
            )
            all_invaders.extend(invaders)
            
            if not has_more or not invaders:
                break
            
            page += 1
            # Small delay between pages to be respectful
            await asyncio.sleep(0.5)
        
        _LOGGER.debug(
            "Fetched total %d invaders for %s across %d pages",
            len(all_invaders), city_code, page
        )
        return all_invaders

    async def _fetch_city_page(
        self, city_code: str, city_name: str, page: int
    ) -> tuple[list[Invader], bool]:
        """Fetch a single page of invaders for a city.
        
        Returns:
            Tuple of (invaders list, has_more_pages)
        """
        url = f"{INVADER_SPOTTER_BASE_URL}/listing.php"
        
        # The site requires POST with specific form data
        data = {
            "ville": city_code,
            "arron": "00",
            "mode": "lst",
            "page": str(page),
        }
        headers = {
            "Referer": f"{INVADER_SPOTTER_BASE_URL}/villes.php",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            async with self._session.post(
                url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    raise InvaderSpotterConnectionError(
                        f"HTTP {response.status} for city {city_code} page {page}"
                    )

                html_content = await response.text()
                invaders = self._parse_city_page(html_content, city_code, city_name)
                
                # Check if there are more pages
                has_more = self._has_next_page(html_content, page)
                
                return invaders, has_more

        except TimeoutError as err:
            _LOGGER.warning("Invader Spotter timeout for city %s page %d", city_code, page)
            raise InvaderSpotterConnectionError(f"Timeout for {city_code}") from err

        except aiohttp.ClientError as err:
            _LOGGER.warning(
                "Invader Spotter connection error for %s: %s",
                city_code,
                type(err).__name__,
            )
            raise InvaderSpotterConnectionError(str(err)) from err

    def _has_next_page(self, html_content: str, current_page: int) -> bool:
        """Check if there's a next page of results."""
        # Look for pagination links like changepage(N) where N > current_page
        pattern = rf"changepage\({current_page + 1}\)"
        return bool(re.search(pattern, html_content))

    def _parse_city_page(
        self, html_content: str, city_code: str, city_name: str
    ) -> list[Invader]:
        """Parse city invaders page."""
        soup = BeautifulSoup(html_content, "html.parser")
        invaders: list[Invader] = []
        parse_errors = 0

        # Try multiple selectors for invader entries
        # The actual structure may vary - we try common patterns
        entries = self._find_invader_entries(soup)

        if not entries:
            _LOGGER.warning(
                "No invader entries found for %s - page structure may have changed",
                city_code,
            )
            return []

        for entry in entries:
            try:
                invader = self._parse_invader_entry(entry, city_code, city_name)
                if invader:
                    invaders.append(invader)
            except Exception as err:  # noqa: BLE001
                parse_errors += 1
                _LOGGER.debug("Failed to parse entry in %s: %s", city_code, err)

        if parse_errors > 0:
            _LOGGER.warning(
                "Failed to parse %d/%d entries for %s",
                parse_errors,
                len(entries),
                city_code,
            )

        if not invaders and entries:
            raise ParseError(
                f"Found {len(entries)} entries for {city_code} but parsed 0 - "
                "HTML structure may have changed"
            )

        _LOGGER.debug(
            "Parsed %d invaders for %s (%d flashable)",
            len(invaders),
            city_code,
            sum(1 for inv in invaders if inv.is_flashable),
        )
        return invaders

    def _find_invader_entries(self, soup: BeautifulSoup) -> list:
        """Find invader entry elements - each invader is in a <td> with rowspan."""
        entries = []
        
        # The site structure: each invader is in a <td align="left" rowspan="2">
        # containing <b>XX_NN [pts]</b> and other info
        for td in soup.find_all("td", {"rowspan": "2"}):
            # Check if this td contains an invader ID pattern
            text = td.get_text()
            if re.search(r"[A-Z]{2,5}_\d{1,4}", text):
                entries.append(td)
        
        if entries:
            return entries

        # Fallback: Look for <b> tags with invader IDs
        for bold in soup.find_all("b"):
            text = bold.get_text()
            if re.search(r"[A-Z]{2,5}_\d{1,4}\s*\[\d+\s*pts?\]", text, re.IGNORECASE):
                # Get the parent td
                parent = bold.find_parent("td")
                if parent and parent not in entries:
                    entries.append(parent)

        return entries

    def _parse_invader_entry(
        self, entry, city_code: str, city_name: str
    ) -> Invader | None:
        """Parse a single invader entry."""
        text = entry.get_text(" ", strip=True)
        html_str = str(entry)

        # Extract invader ID
        inv_id = self._extract_invader_id(text, city_code)
        if not inv_id:
            return None

        # Extract points
        points = self._extract_points(text)

        # Extract status from images or text
        status = self._extract_status_from_html(html_str, text)

        # Extract install date
        install_date = self._extract_date(text)

        return Invader(
            id=inv_id,
            city_code=city_code,
            city_name=city_name or city_code,
            points=points,
            status=status,
            install_date=install_date,
        )

    def _extract_invader_id(self, text: str, city_code: str) -> str | None:
        """Extract and validate invader ID from text."""
        # Look for pattern like PA_001, LYN_42, etc.
        pattern = rf"({city_code}_\d{{1,4}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            inv_id = match.group(1).upper()
            if INVADER_ID_PATTERN.match(inv_id):
                return inv_id

        # Fallback: any invader ID pattern
        match = re.search(r"([A-Z]{2,5}_\d{1,4})", text)
        if match:
            inv_id = match.group(1).upper()
            if INVADER_ID_PATTERN.match(inv_id):
                return inv_id

        return None

    def _extract_points(self, text: str) -> int:
        """Extract points value from text."""
        match = POINTS_PATTERN.search(text)
        if match:
            try:
                points = int(match.group(1))
                # Sanity check - points are typically 10-100
                if 0 < points <= 1000:
                    return points
            except ValueError:
                pass
        return 0

    def _extract_status_from_html(self, html_str: str, text: str) -> InvaderStatus:
        """Extract status from HTML (checking images) or text."""
        html_lower = html_str.lower()
        text_lower = text.lower()
        
        # Check for status images first (more reliable)
        if "spot_invader_destroyed" in html_lower:
            return InvaderStatus.DESTROYED
        if "spot_invader_degraded" in html_lower:
            # Need to distinguish between "dégradé" and "très dégradé"
            if "très dégradé" in text_lower:
                return InvaderStatus.VERY_DAMAGED
            return InvaderStatus.DAMAGED
        if "spot_invader_ok" in html_lower:
            return InvaderStatus.OK
        if "spot_invader_unknown" in html_lower:
            return InvaderStatus.UNKNOWN
        if "spot_invader_notvisible" in html_lower or "non visible" in text_lower:
            return InvaderStatus.NOT_VISIBLE
        
        # Fallback to text-based extraction
        return self._extract_status(text)

    def _extract_status(self, text: str) -> InvaderStatus:
        """Extract status from text."""
        text_lower = text.lower()

        # Look for status keywords
        for keyword, status in STATUS_MAPPING.items():
            if keyword in text_lower:
                return status

        # Check for specific patterns
        if "dernier état" in text_lower or "état connu" in text_lower:
            # Try to find status after these phrases
            for keyword, status in STATUS_MAPPING.items():
                pattern = rf"(?:dernier état|état connu)[^:]*:\s*{keyword}"
                if re.search(pattern, text_lower):
                    return status

        return InvaderStatus.UNKNOWN

    def _extract_date(self, text: str) -> datetime | None:
        """Extract date from text (French format DD/MM/YYYY)."""
        match = DATE_PATTERN_FR.search(text)
        if match:
            try:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                return datetime(year, month, day).date()
            except ValueError:
                pass
        return None
