# Changelog

All notable changes to the Invader Tracker integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.1] - 2026-04-13

### Added

- **Détection automatique des nouveaux joueurs suivis** — l'intégration se recharge automatiquement quand un nouveau joueur est suivi dans l'app Flash Invader, créant le nouvel appareil et ses entités sans intervention manuelle.

### Fixed

- Corrections CI : mypy (`ConfigFlowResult`, types `CoordinatorEntity`, `_attr_state_class`), ruff (imports inutilisés), listener async via `hass.async_create_task`
- Tests mis à jour pour correspondre aux attributs simplifiés des capteurs

## [2.2.0] - 2026-04-13

### Added

- **Option "Track followed players"** — nouvelle option dans les réglages de l'intégration pour activer ou désactiver le suivi des joueurs suivis. Désactivé = aucun appel API supplémentaire, aucune entité créée. Activé par défaut (comportement inchangé pour les installations existantes).

## [2.1.1] - 2026-04-13

### Added

- **Registration Date** — nouvelle entité sur le profil principal
- **Device par joueur suivi** — chaque joueur suivi a maintenant son propre appareil "Invader Tracker - {NOM}" avec 3 entités : `Score`, `Rank` (attribut `rank_str`), `Invaders Found`

### Fixed

- `New & Reactivated` excluait incorrectement les invaders déjà flashés — utilise désormais `unflashed_new_count` pour être cohérent avec `Invaders To Flash`

### Changed

- Le device profil principal s'appelle désormais **"Invader Tracker - {pseudo}"** (ex: "Invader Tracker - TROPLENT") au lieu de "Invader Tracker - Profil"
- `sensor.score` n'a plus `rank`/`rank_str` en attributs — ces infos sont sur `sensor.rank`
- `sensor.rank` a `rank_str` en attribut (cohérent avec les joueurs suivis)

## [2.1.0] - 2026-04-12

### Added

- **Player Profile device** — nouveau device "Invader Tracker - Profil" créé automatiquement dès qu'un UID est configuré :
  - `sensor.score` — score total (attributs : `rank`, `rank_str`)
  - `sensor.rank` — classement global
  - `sensor.invaders_found` — total d'invaders flashés toutes villes confondues
  - `sensor.cities_found` — nombre de villes distinctes avec au moins un flash
- **Joueurs suivis** — une entité par joueur suivi (valeur = score, attributs = `rank`, `rank_str`, `invaders_count`)
- **Retry sur timeout scraper** — les timeouts sur invader-spotter.art déclenchent jusqu'à 3 tentatives avec backoff exponentiel (2s, 4s), réduisant les mises à jour partielles
- Nouveaux endpoints API : `get_player_profile()` et `get_followed_players()` dans `FlashInvaderAPI`
- Nouveau coordinator : `FlashInvaderProfileCoordinator`
- Nouveaux modèles : `PlayerProfile`, `FollowedPlayer`

### Changed

- Attributs des entités ville simplifiés — suppression des listes verboses, seuls les compteurs essentiels sont conservés :
  - `Total Invaders` : supprimé `invader_ids`, conservé `flashable_count`
  - `Flashed`, `Unflashed (Available)`, `Unflashed (Gone)` : aucun attribut
  - `New & Reactivated` : valeur = total (new + reactivated), attributs = `new_count` + `reactivated_count`
  - `Invaders To Flash` : valeur = liste CSV des IDs, aucun attribut
  - `Has New Invaders` : binaire pur, aucun attribut

## [2.0.0] - 2026-01-27

### Added

- Comprehensive test suite: 101 tests across 7 test files (processor, coordinator, sensor, flash_invader, invader_spotter, models, device_removal)
- CI pipeline via GitHub Actions (ruff lint, mypy type-check, pytest with coverage)
- HACS validation workflow
- Comprehensive documentation suite: CHANGELOG.md, CONTRIBUTING.md, DOCUMENTATION.md, INSTALL.md, QUICK_REFERENCE.md
- Expanded README.md with entity docs, automation examples, troubleshooting
- Brand submission assets (`brands_submission/`)
- `pyproject.toml` now tracked in git (test/lint/type-check config)

### Fixed

- Critical bug: `flash_date.isoformat()` crash when `flash_date` is `None` in flashed sensor attributes
- Type annotation: `_extract_date` return type corrected from `datetime | None` to `date | None`

### Changed

- Replaced empty `pass` in `TYPE_CHECKING` blocks with actual type imports
- Removed redundant `TYPE_CHECKING` imports in `__init__.py`, `flash_invader.py`, `invader_spotter.py`
- Fixed `TimeoutError` to `asyncio.TimeoutError` in both API clients
- Removed unused loop variable in coordinator
- Renamed `old_status` to `previous_inv_status` to avoid variable shadowing
- Made `install_date` and `flash_date` optional in `FlashedInvader` model (prevents crashes on malformed data)
- Improved date parsing: returns `None` instead of silently falling back to `datetime.now()`
- Fixed test mock paths to patch correct import locations
- Added `config_entry` fixture in conftest.py
- Trailing whitespace cleanup across all files
- Updated architecture document to v2.0.0 (aligned with actual codebase)

### Removed

- Deleted BUGFIX_CITY_REMOVAL.md (fix already shipped in v1.3.2)
- Removed `pyproject.toml` from `.gitignore`

## [1.3.2] - 2026-01-25

### Fixed

- Suppress city devices on removal from config (device registry cleanup)

### Changed

- Bumped version to 1.3.2

## [1.3.0] - 2026-01-25

### Added

- Text sensor `to_flash` showing invader IDs to flash as a comma-separated list
- Fixed binary sensor display for `has_new`

## [1.2.0] - 2026-01-24

### Added

- News scraper (`news.php`) for detecting new and reactivated invaders
- Smart caching with per-city cache and 6-hour news TTL
- Fallback to expired cache during API failures
- New/reactivated invader detection via news events + state snapshot comparison
- Icon added to repo root for HACS display

### Fixed

- Options flow: read current values from options first, then data
- Entity creation: read cities from options first
- City parsing: use `javascript:envoi` pattern for city discovery
- Invader-spotter scraping: POST method, pagination support, status mapping
- Flash Invader API: use `api.space-invaders.com` with UID as query parameter

## [1.0.0] - 2026-01-23

### Added

- Initial release
- Integration with invader-spotter.art (HTML scraping for city invaders)
- Flash Invader API support via personal UID
- Config flow with UID validation and city selection
- Options flow for reconfiguring cities and intervals
- Reauth flow on credential failure
- 5 sensor entities per city: total, flashed, unflashed, unflashed_gone, new
- 1 binary sensor per city: has_new
- Device per tracked city in HA device registry
- State persistence via `StateStore` for change detection
- Custom exception hierarchy
- English and French translations
- Rate limiting (2s between city scrapes)

## [0.1.1] - 2026-01-22

### Added

- Release workflow (GitHub Actions)

## [0.1.0] - 2026-01-22

### Added

- Initial commit with basic integration scaffold

---

## Version Policy

- **MAJOR** version for incompatible changes (config format, entity structure)
- **MINOR** version for new features (new sensors, API support)
- **PATCH** version for bug fixes and improvements
