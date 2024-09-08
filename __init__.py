"""The Detailed Hello World Push integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from collections.abc import Callable
from dataclasses import dataclass
from .const import DOMAIN
from .coordinator import HMCoordinator

import logging
_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE]

# List of platforms to support. There should be a matching .py file for each,
# eg <cover.py> and <sensor.py>

@dataclass
class RuntimeData:
    """Class to hold your data."""
    coordinator: DataUpdateCoordinator
    cancel_update_listener: Callable


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""
    # Store an instance of the "connecting" class that does the work of speaking
    # with your actual devices.
    _LOGGER.debug("[RS] async_setup_entry called with entry.data: {}".format(entry.data))

    hass.data.setdefault(DOMAIN, {})

    # Initialise the coordinator that manages data updates from your api.
    # pass socket string so that we can initiailise the connection
    socket_str = "socket://" + entry.data[CONF_HOST] + ":" + entry.data[CONF_PORT]
    coordinator = HMCoordinator(hass, entry, socket_str)
    await coordinator.async_config_entry_first_refresh()

    # Test to see if api initialised correctly, else raise ConfigNotReady to make HA retry setup
    # TODO: Add a connected property to my UH1 class
    #if not coordinator.uh1_con.connected:
    #    raise ConfigEntryNotReady

    # Initialise a listener for config flow options changes.
    # See config_flow for defining an options setting that shows up as configure on the integration.
    cancel_update_listener = entry.add_update_listener(_async_update_listener)
 
    entry.runtime_data = RuntimeData(coordinator, cancel_update_listener)
    _LOGGER.debug("[RS] entry.runtime_data= {}".format(entry.runtime_data))

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)

async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update. Is this still needed?"""
    await hass.config_entries.async_reload(config_entry.entry_id)



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    _LOGGER.debug("[RS] async_unload_entry called with entry.data: {}".format(entry.data))
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok
