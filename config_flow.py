"""Config flow for the Heatmiser RS integration (UH1 hub via an eth:serial adapter)."""
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

# Form shown to the user - labels/descriptions come from strings.json / translations/en.json
CONN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.123.253"): str,
        vol.Required(CONF_PORT, default="5000"): str,
    }
)
_LOGGER.debug("[RS] config flow started? with DATA_SCHEMA = {}".format(CONN_SCHEMA))

async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect and that at least one thermo responds.

    Data has the keys from CONN_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("[RS] config flow validate_input step data: {}".format(data))

    if len(data[CONF_HOST]) < 3:
        raise InvalidHost
    if not data[CONF_PORT].isdigit() or not 1 <= int(data[CONF_PORT]) <= 65535:
        raise InvalidPort

    # Do one full poll - opens and closes the connection, and proves the RS485 side works too
    socket_str = "socket://" + data[CONF_HOST] + ":" + data[CONF_PORT]
    uh1 = UH1(socket_str)
    if not await uh1.async_read_dcbs():
        if not uh1.online:
            raise CannotConnect
        raise NoThermostats

    _LOGGER.debug("[RS] config flow validate_input exiting returning: {}".format(data))
    return {"title": f"Heatmiser RS - {data[CONF_HOST]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Heatmiser RS."""

    VERSION = 1
    # Connection class (local polling) is now set by iot_class in manifest.json

    _LOGGER.debug("[RS] config flow ConfigFlow class setup with DOMAIN {}".format(DOMAIN))
    async def async_step_user(self, user_input=None):
        """Show the host/port form, validate it and create the config entry."""
        _LOGGER.debug("[RS] async_step_user called with user input: {}".format(user_input))
        errors = {}
        if user_input is not None:
            user_input = {
                CONF_HOST: user_input[CONF_HOST].strip(),
                CONF_PORT: user_input[CONF_PORT].strip(),
            }
            # One entry per hub - abort before connecting so we don't talk over an existing entry's polls
            await self.async_set_unique_id("{}:{}".format(user_input[CONF_HOST], user_input[CONF_PORT]))
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                _LOGGER.debug("[RS] await validate input called returning result: {}".format(info))
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NoThermostats:
                errors["base"] = "no_thermostats"
            except InvalidHost:
                errors[CONF_HOST] = "invalid_host"
            except InvalidPort:
                errors[CONF_PORT] = "invalid_port"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("[RS] Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                _LOGGER.debug("[RS] setting up entry with title, data: {}, {}".format(info["title"], user_input))
                return self.async_create_entry(title=info["title"], data=user_input)

        # No input yet, or there were errors - show the form again (keeping what the user typed)
        _LOGGER.debug("[RS] Showing config form with errors: {}".format(errors))
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONN_SCHEMA, user_input),
            errors=errors,
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect to the eth:serial adapter."""


class NoThermostats(exceptions.HomeAssistantError):
    """Error to indicate we connected but no thermostats responded."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""


class InvalidPort(exceptions.HomeAssistantError):
    """Error to indicate the port is not a number between 1 and 65535."""
