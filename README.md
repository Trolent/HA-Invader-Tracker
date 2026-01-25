# Invader Tracker for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Trolent/HA-Invader-Tracker.svg)](https://github.com/Trolent/HA-Invader-Tracker/releases)
[![License](https://img.shields.io/github/license/Trolent/HA-Invader-Tracker.svg)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg?logo=buy-me-a-coffee)](https://buymeacoffee.com/trolent)

Track [Space Invader](https://www.space-invaders.com/) street art mosaics in Home Assistant. This integration combines data from:

- **[invader-spotter.art](https://www.invader-spotter.art/)** - Community database of all known invaders with status
- **Flash Invader App** - Your personal flashed invaders via your account UID

## Features

- **Track multiple cities** - Monitor invaders across any cities you choose
- **Flash status** - See which invaders you've flashed vs which are still available
- **New invader alerts** - Get notified when new invaders appear or old ones are reactivated
- **Missed invaders** - Track invaders that were destroyed before you could flash them
- **Easy automations** - Binary sensor triggers when new invaders are detected

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/username/ha-invader-tracker` with category "Integration"
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/username/ha-invader-tracker/releases)
2. Extract and copy `custom_components/invader_tracker` to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Invader Tracker"
4. Enter your Flash Invader UID (see below)
5. Select the cities you want to track
6. Configure update intervals

### Finding Your Flash Invader UID

Your UID is a unique identifier for your Flash Invader account. To find it:

1. Use a network proxy tool (like mitmproxy or Charles Proxy) on your phone
2. Open the Flash Invader app and refresh your gallery
3. Look for requests to `space-invaders.com`
4. The `uid` header contains your UID (format: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`)

## Entities

For each tracked city, the integration creates a device with these entities:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.invader_{city}_total` | Sensor | Total number of invaders in the city |
| `sensor.invader_{city}_flashed` | Sensor | Number of invaders you've flashed |
| `sensor.invader_{city}_unflashed` | Sensor | Unflashed invaders still available |
| `sensor.invader_{city}_unflashed_gone` | Sensor | Unflashed invaders that are now destroyed |
| `sensor.invader_{city}_new` | Sensor | New or reactivated invaders since last update |
| `binary_sensor.invader_{city}_has_new` | Binary Sensor | ON when there are new invaders |

Each sensor includes detailed attributes with invader IDs and point values.

## Automations

### Notify on New Invaders

```yaml
automation:
  - alias: "New Invaders Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.invader_paris_has_new
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "New Invaders in Paris!"
          message: >
            {{ state_attr('sensor.invader_paris_new', 'new_count') }} new invaders detected.
            IDs: {{ state_attr('sensor.invader_paris_new', 'new_invaders') | join(', ') }}
```

### Daily Summary

```yaml
automation:
  - alias: "Daily Invader Summary"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app
        data:
          title: "Invader Tracker Daily Summary"
          message: >
            Paris: {{ states('sensor.invader_paris_unflashed') }} unflashed
            ({{ states('sensor.invader_paris_flashed') }} flashed)
```

## Troubleshooting

### Integration shows "unavailable"

1. Check logs: **Settings** → **System** → **Logs** → Filter by "invader_tracker"
2. Common causes:
   - Network connectivity issues
   - invader-spotter.art is down
   - Flash Invader API changed

### "Authentication failed" error

1. Your UID may have changed or expired
2. Re-obtain UID from Flash Invader app
3. Reconfigure the integration with new UID

### Data not updating

1. Check last update time in diagnostic attributes
2. Verify update interval in integration options
3. Check logs for rate limiting warnings

### Enable debug logging

Add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.invader_tracker: debug
```

## Contributing

Contributions are welcome! Please submit issues and pull requests on GitHub.

## Support

If you find this integration useful, consider buying me a coffee! ☕

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/trolent)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Space Invader, the Flash Invader app, or invader-spotter.art. Use responsibly and respect the data sources.
