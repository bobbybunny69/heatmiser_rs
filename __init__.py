"""
This is my heatmiser_rs custom component
v1:  this was the first attempt using config flow and works well
v2:  change logging level to DEBUG now I have it working for majority of messages
v3:  move to awaiting async_forward_entry_setups, only open serport at init instead of each access
v4:  Added coordinator task and fixed blocking calls issue (by adding add_executor asyncio call for serport.close) 
v5:  Working version locked to start improvements
"""
from __future__ import annotations
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Heatmiser from a config entry."""
    # Forward the setup to the climate platform.
    data = config_entry.data
    _LOGGER.info("[RS] __init__ Entry setup called with Config = {}".format(data))
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = data
    
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Registers update listener to update config entry when options are updated.
    #unsub_options_update_listener = config_entry.add_update_listener(options_update_listener)
    
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    #  Older way???? hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the config and platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok

async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update. Is this still needed?"""
    await hass.config_entries.async_reload(config_entry.entry_id)

