"""This is the conifg flow my heatmiser_rs integration"""
import logging

from . import heatmiserRS as heatmiser 
import requests.exceptions
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_ID,
    CONF_NAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from .const import DOMAIN, CONF_THERMOSTATS, CONN_SCHEMA, TSTATS_SCHEMA
_LOGGER = logging.getLogger(__name__)

class HeatmiserRSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Heatmiser RS."""      
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Invoked when a user initiates a flow via the user interface."""
        errors = {}

        if user_input is not None:
            # .Validate the user input connects
            self.uh1 = heatmiser.UH1_com(user_input[CONF_HOST], user_input[CONF_PORT])

            if "base" not in errors:
                # Input is valid, set data
                self.data = user_input
                self.data[CONF_THERMOSTATS] = []
                # Return the form of the next step.
                return await self.async_step_tstats()

        return self.async_show_form(step_id="user", data_schema=CONN_SCHEMA, errors=errors)

    async def async_step_tstats(self, user_input=None):
        """Second step in config flow to add thermos."""
        errors = {}
        if user_input is not None:
            # Validate the thermos connect with user input.
 
            try:
                self.uh1.get_thermostat(user_input[CONF_ID], user_input[CONF_NAME])
            except requests.exceptions.Timeout as ex:
                errors["base"] = "invalid_thermostat"
                raise InvalidThermostat from ex
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
    
            if "base" not in errors:
                # Input is valid, set data.
                self.data[CONF_THERMOSTATS].append(
                    {
                        CONF_ID: user_input[CONF_ID],
                        CONF_NAME: user_input[CONF_NAME],
                    }
                )
                # If user ticked the box show this form again so they can add an
                # additional repo.
                if user_input.get("add_another", False):
                    return await self.async_step_tstats()
    
                # User is done adding thermos, create the config entry.
                _LOGGER.info("[RS] Tstat user input = {}".format(self.data))
                return self.async_create_entry(title="heatmiser_config", data=self.data)

        return self.async_show_form(step_id="tstats", data_schema=TSTATS_SCHEMA, errors=errors)

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
    
class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""#

class InvalidThermostat(exceptions.HomeAssistantError):
    """Error to indicate there is invalid thermostat."""

