"""Config flow for Hello World integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN  # pylint:disable=unused-import
from .heatmiserRS import UH1

_LOGGER = logging.getLogger(__name__)

CONN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.123.253"): str,
        vol.Required(CONF_PORT, default="5000"): str,
    }
)
# This is the schema that used to display the UI to the user. This simple
# schema has a single required host field, but it could include a number of fields
# such as username, password etc. See other components in the HA core code for
# further examples.
# Note the input displayed to the user will be translated. See the
# translations/<lang>.json file and strings.json. See here for further information:
# https://developers.home-assistant.io/docs/config_entries_config_flow_handler/#translations
# At the time of writing I found the translations created by the scaffold didn't
# quite work as documented and always gave me the "Lokalise key references" string
# (in square brackets), rather than the actual translated value. I did not attempt to
# figure this out or look further into it.
_LOGGER.debug("[RS] config flow started? with DATA_SCHEMA = {}".format(CONN_SCHEMA))

async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # Validate the data can be used to set up a connection.
    _LOGGER.debug("[RS] config flow validate_input step data: {}".format(data))
    
    # This is a simple example to show an error in the UI for a short hostname
    # The exceptions are defined at the end of this file, and are used in the
    # `async_step_user` method below.
    if len(data[CONF_HOST]) < 3:
        raise InvalidHost

    socket_str = "socket://" + data[CONF_HOST] + ":" + data[CONF_PORT]
    uh1 = UH1(socket_str)
    # The dummy hub provides a `test_connection` method to ensure it's working
    # as expected
    result = await uh1.async_open_connection()
    if not result:
        # If there is an error connecting, raise an exception to notify HA that there was a
        # problem. The UI will also show there was a problem
        raise CannotConnect

    _LOGGER.debug("[RS] config flow validate_input exiting returning: {}".format(data))
    return {"title": f"Heatmiser RS - {data[CONF_HOST]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hello World."""

    VERSION = 1
    # Pick one of the available connection classes in homeassistant/config_entries.py
    # This tells HA if it should be asking for updates, or it'll be notified of updates
    # automatically. Using PollT
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    _LOGGER.debug("[RS] config flow ConfigFlow class setup with DOMAIN {}".format(DOMAIN))
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        # This goes through the steps to take the user through the setup process.
        # Using this it is possible to update the UI and prompt for additional
        # information. This example provides a single form (built from `CONN_SCHEMA`),
        # and when that has some validated input, it calls `async_create_entry` to
        # actually create the HA config entry. Note the "title" value is returned by
        # `validate_input` above.
        _LOGGER.debug("[RS] async_step_user called wither user input: ".format(user_input))
        errors = {}
        if user_input is not None:
            _LOGGER.debug("[RS] Config flow path if user_input is not None user_input = {}".format(user_input))
            try:
                info = await validate_input(self.hass, user_input)
                _LOGGER.debug("[RS] await validate input called returning result: {}".format(info))
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                # Validation was successful, so create the config entry
                _LOGGER.debug("[RS] setting up entry with title, data: {}, {}".format("Heatmiser RS",user_input))
                return self.async_create_entry(title=info["title"], data=user_input)

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        _LOGGER.debug("[RS] If there is no user input or there were errors, show the form again, including any errors")
        return self.async_show_form(step_id="user", data_schema=CONN_SCHEMA, errors=errors)

class CannotConnect(exceptions.HomeAssistantError):
    #_LOGGER.debug("[RS] CannotConnect called with: {}".format(exceptions.HomeAssistantError))
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    #_LOGGER.debug("[RS] InvalidHost called with: {}".format(exceptions.HomeAssistantError))
    """Error to indicate there is an invalid hostname."""
