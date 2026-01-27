# Quick Reference Guide

A quick lookup guide for common tasks and entity names in Invader Tracker.

## Entity Name Reference

### Sensor Entities

Replace `{city}` with your city code (e.g., `paris`, `lyon`):

```
sensor.invader_{city}_total         # Total invaders in city
sensor.invader_{city}_flashed       # Invaders you've flashed
sensor.invader_{city}_unflashed     # Available targets (not flashed, not destroyed)
sensor.invader_{city}_unflashed_gone # Missed opportunities (destroyed before flashing)
sensor.invader_{city}_new           # New or reactivated invaders
sensor.invader_{city}_to_flash      # Priority targets (unflashed & flashable)
```

### Binary Sensor Entities

```
binary_sensor.invader_{city}_has_new # ON when new invaders detected
```

## Common Automations

### Alert on New Invaders

```yaml
automation new_invaders:
  alias: "New Space Invaders Found!"
  trigger:
    - platform: state
      entity_id: binary_sensor.invader_paris_has_new
      to: "on"
  action:
    - service: notify.mobile_app
      data:
        title: "🎨 New Invaders!"
        message: |
          {{ states('sensor.invader_paris_new') }} new targets in Paris
```

### Daily Progress Summary

```yaml
automation daily_summary:
  alias: "Daily Invader Report"
  trigger:
    - platform: time
      at: "20:00:00"
  action:
    - service: notify.mobile_app
      data:
        title: "📊 Today's Hunting Stats"
        message: |
          Paris: {{ states('sensor.invader_paris_unflashed') }} left
          Total: {{ states('sensor.invader_paris_flashed') }} flashed
```

### Track Progress Milestone

```yaml
automation milestone:
  alias: "Milestone Alert"
  trigger:
    - platform: numeric_state
      entity_id: sensor.invader_paris_flashed
      above: 100
  action:
    - service: notify.mobile_app
      data:
        title: "🏆 Achievement!"
        message: "100+ invaders flashed in Paris!"
```

## Sensor Attributes

Each sensor includes helpful attributes accessible in templates:

### Available Attributes

```yaml
sensor.invader_{city}_unflashed:
  state: 42                                  # Unflashed count
  invaders: [{id: PA_001, points: 20}, ...]  # Invader details
  total_points: 840                          # Total available points

sensor.invader_{city}_new:
  state: 3                                   # New + reactivated count
  new_invaders: ['PA_1554', ...]             # Newly added IDs
  reactivated_invaders: ['PA_042', ...]      # Reactivated IDs
  potential_points: 60                       # Points available

sensor.invader_{city}_to_flash:
  state: "PA_1554, PA_042, PA_789"           # CSV list of IDs (text)
  new_count: 2                               # New invader count
  reactivated_count: 1                       # Reactivated count
  potential_points: 60                       # Points available
```

## Template Examples

### Get Invader List for Notification

```jinja2
{% set invaders = state_attr('sensor.invader_paris_new', 'invader_ids') %}
New invaders: {{ invaders | join(', ') }}
```

### Calculate Completion Percentage

```jinja2
{% set total = states('sensor.invader_paris_total') | int(0) %}
{% set flashed = states('sensor.invader_paris_flashed') | int(0) %}
Completion: {{ (flashed / total * 100) | round(1) }}%
```

### Check if Targets Available

```jinja2
{% if states('sensor.invader_paris_unflashed') | int(0) > 0 %}
  Targets available in Paris
{% else %}
  All Paris invaders flashed or destroyed!
{% endif %}
```

## Dashboard Card Examples

### Simple Status Card

```yaml
type: entities
entities:
  - entity: sensor.invader_paris_total
    name: Total Invaders
  - entity: sensor.invader_paris_flashed
    name: Flashed
  - entity: sensor.invader_paris_unflashed
    name: Available
  - entity: binary_sensor.invader_paris_has_new
    name: New Available?
```

### Progress Bar Card

```yaml
type: custom:bar-card
entities:
  - entity: sensor.invader_paris_flashed
    name: Flashed
    max: 500  # Adjust to your city total
    unit_of_measurement: invaders
```

## Configuration Tips

### Optimize Performance

**High Priority (faster refresh):**
```yaml
Scrape Interval: 6-12 hours
API Interval: 1-2 hours
```

**Balanced (recommended):**
```yaml
Scrape Interval: 24 hours
API Interval: 6 hours
```

**Low Bandwidth:**
```yaml
Scrape Interval: 168 hours
API Interval: 24 hours
```

### Multi-City Tracking

To track progress across cities, create template sensors:

```yaml
template:
  - sensor:
      - name: "Total Invaders All Cities"
        state: |
          {% set paris = states('sensor.invader_paris_total') | int(0) %}
          {% set lyon = states('sensor.invader_lyon_total') | int(0) %}
          {{ paris + lyon }}
        
      - name: "Total Flashed All Cities"
        state: |
          {% set paris = states('sensor.invader_paris_flashed') | int(0) %}
          {% set lyon = states('sensor.invader_lyon_flashed') | int(0) %}
          {{ paris + lyon }}
```

## Debugging

### Check Integration Status

```yaml
# In Developer Tools → States
sensor.invader_paris_total
# Look for "unknown" or "unavailable"
```

### View Last Update

Check sensor attributes for timestamp information in **Developer Tools → States**.

### Enable Debug Logging

```yaml
logger:
  logs:
    custom_components.invader_tracker: debug
```

Then check **Settings → System → Logs**.

### Common Issues

| Issue | Solution |
|-------|----------|
| Sensors show "unknown" | Wait for first update (check intervals) |
| "Unavailable" error | Check network connectivity and logs |
| No new invaders alert | Verify binary_sensor.invader_*_has_new exists |
| Updates not happening | Check update intervals in integration options |

## Useful Links

- **GitHub:** https://github.com/Trolent/HA-Invader-Tracker
- **Issues:** https://github.com/Trolent/HA-Invader-Tracker/issues
- **Invader-Spotter:** https://www.invader-spotter.art/
- **Space Invader:** https://www.space-invaders.com/

## Keyboard Shortcuts

**In Home Assistant:**
- `?` - Show help overlay
- `c` - Open frontend code inspector
- `r` - Refresh frontend

## Entity Naming Convention

The integration follows Home Assistant naming standards:

```
{domain}.{integration}_{city}_{sensor_type}

Examples:
sensor.invader_paris_total
binary_sensor.invader_lyon_has_new
```

Replace spaces in city names with underscores (e.g., "New York" → `invader_new_york_*`).

---

**Last Updated:** January 27, 2026
**Integration Version:** 1.3.3

For more details, see:
- [README.md](README.md) - Full documentation
- [INSTALL.md](INSTALL.md) - Installation instructions
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide
- [docs/architecture.md](docs/architecture.md) - Technical architecture
