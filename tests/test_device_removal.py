"""Tests for city device removal functionality."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from custom_components.invader_tracker.const import (
    CONF_CITIES,
    CONF_UID,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_city_removal_deletes_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Test that removing a city deletes its device."""
    # Setup initial integration with 2 cities
    initial_cities = {"PA": "Paris", "LYN": "Lyon"}
    config_entry.data = {
        CONF_UID: "12345678-1234-1234-1234-123456789abc",
        CONF_CITIES: initial_cities,
    }
    
    # Mock device registry - Lyon's device (the one being removed)
    device_registry = MagicMock(spec=DeviceRegistry)
    device_registry.async_get_device = MagicMock(return_value=MagicMock(id="device_id_lyn"))
    device_registry.async_remove_device = MagicMock()
    
    with patch("homeassistant.helpers.device_registry.async_get") as mock_get_registry:
        mock_get_registry.return_value = device_registry
        
        # Setup the entry with mocked coordinators
        with patch("custom_components.invader_tracker.async_setup_entry") as mock_setup:
            mock_setup.return_value = True
            
            # Simulate options update - removing Lyon
            new_cities = {"PA": "Paris"}
            config_entry.options = {CONF_CITIES: new_cities}
            
            # Import after patches are set
            from custom_components.invader_tracker import async_update_options
            
            # Mock the hass.data structure
            hass.data[DOMAIN] = {
                config_entry.entry_id: {
                    "spotter_coordinator": MagicMock(update_cities=MagicMock()),
                    "processor": MagicMock(set_city_names=MagicMock()),
                }
            }
            
            # Mock async_unload_platforms and async_forward_entry_setups
            with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload, \
                 patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward:
                
                mock_unload.return_value = True
                mock_forward.return_value = True
                
                # Call update options
                await async_update_options(hass, config_entry)
            
            # Verify device registry was called to get the device
            device_registry.async_get_device.assert_called_once_with(
                identifiers={(DOMAIN, f"{config_entry.entry_id}_LYN")}
            )
            
            # Verify device was removed (Lyon's device)
            device_registry.async_remove_device.assert_called_once_with("device_id_lyn")
            
            # Verify coordinators were updated
            runtime_data = hass.data[DOMAIN][config_entry.entry_id]
            runtime_data["spotter_coordinator"].update_cities.assert_called_once_with(new_cities)
            runtime_data["processor"].set_city_names.assert_called_once_with(new_cities)


@pytest.mark.asyncio
async def test_city_removal_no_device_found(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Test handling when device is not found in registry."""
    initial_cities = {"PA": "Paris", "LYN": "Lyon"}
    config_entry.data = {
        CONF_UID: "12345678-1234-1234-1234-123456789abc",
        CONF_CITIES: initial_cities,
    }
    
    # Mock device registry - device not found
    device_registry = MagicMock(spec=DeviceRegistry)
    device_registry.async_get_device = MagicMock(return_value=None)
    device_registry.async_remove_device = MagicMock()
    
    with patch("homeassistant.helpers.device_registry.async_get") as mock_get_registry:
        mock_get_registry.return_value = device_registry
        
        # Simulate options update - removing Lyon
        new_cities = {"PA": "Paris"}
        config_entry.options = {CONF_CITIES: new_cities}
        
        from custom_components.invader_tracker import async_update_options
        
        hass.data[DOMAIN] = {
            config_entry.entry_id: {
                "spotter_coordinator": MagicMock(update_cities=MagicMock()),
                "processor": MagicMock(set_city_names=MagicMock()),
            }
        }
        
        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload, \
             patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward:
            
            mock_unload.return_value = True
            mock_forward.return_value = True
            
            await async_update_options(hass, config_entry)
        
        # Verify device removal was not called since device wasn't found
        device_registry.async_remove_device.assert_not_called()


@pytest.mark.asyncio
async def test_city_addition_no_device_removal(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Test that adding a city doesn't trigger device removal."""
    initial_cities = {"PA": "Paris"}
    config_entry.data = {
        CONF_UID: "12345678-1234-1234-1234-123456789abc",
        CONF_CITIES: initial_cities,
    }
    
    device_registry = MagicMock(spec=DeviceRegistry)
    
    with patch("homeassistant.helpers.device_registry.async_get") as mock_get_registry:
        mock_get_registry.return_value = device_registry
        
        # Simulate options update - adding Lyon
        new_cities = {"PA": "Paris", "LYN": "Lyon"}
        config_entry.options = {CONF_CITIES: new_cities}
        
        from custom_components.invader_tracker import async_update_options
        
        hass.data[DOMAIN] = {
            config_entry.entry_id: {
                "spotter_coordinator": MagicMock(update_cities=MagicMock()),
                "processor": MagicMock(set_city_names=MagicMock()),
            }
        }
        
        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload, \
             patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward:
            
            mock_unload.return_value = True
            mock_forward.return_value = True
            
            await async_update_options(hass, config_entry)
        
        # Verify device registry was not called (no removals)
        device_registry.async_get_device.assert_not_called()
        device_registry.async_remove_device.assert_not_called()
