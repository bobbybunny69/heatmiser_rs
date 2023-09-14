"""Support for the PRT Heatmiser themostats using the V3 protocol."""
import logging
from typing import List

from . import heatmiserRS as heatmiser 
import voluptuous as vol

from .const import *

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    FAN_ON,
    FAN_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PORT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
#import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities, discovery_info=None):
    """Set up the heatmiser thermostat."""
    conf = config_entry.data
    _LOGGER.info("[RS] Climate Entry setup called with Config = {}".format(conf))

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    uh1 = heatmiser.UH1(conf[CONF_HOST], conf[CONF_PORT])
    uh1.connect()
     
    heatmiser_v3_thermostat = heatmiser.HeatmiserThermostat

    thermostats = conf[CONF_THERMOSTATS]

    async_add_entities(
        [
            HeatmiserATThermostat(heatmiser_v3_thermostat, thermostat, uh1)
            for thermostat in thermostats
        ],
        True,
    )
    
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_DHW_SCHEDULE,
        SET_DHW_SCHEDULE_SCHEMA,
        "async_set_dhw_schedule",
    )
    platform.async_register_entity_service(
        SERVICE_SET_HEAT_SCHEDULE,
        SET_HEAT_SCHEDULE_SCHEMA,
        "async_set_heat_schedule",
    )
    platform.async_register_entity_service(
        SERVICE_SET_DAYTIME,
        SET_DAYTIME_SCHEMA,
        "async_set_daytime",
    )



class HeatmiserATThermostat(ClimateEntity):
    """Representation of a Heatmiser thermostat in the AT0."""

    def __init__(self, hmv3_therm, device, uh1):
        """Initialize the thermostat."""
        self.therm = hmv3_therm(device[CONF_ID], uh1)    # Do not send UH1 handle as done in config flow
        self._name = device[CONF_NAME]
        self._current_temperature = None
        self._target_temperature = None
        self._attr_preset_modes = [PRESET_HOME, PRESET_AWAY]
        self._attr_preset_mode = None
        self._fan_mode = None
        self._id = device
        self._hvac_mode = None
        self._temperature_unit = TEMP_CELSIUS
        self._supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE | SUPPORT_FAN_MODE
 
    @property
    def supported_features(self):
        """Return the list of supported features (Note using FAN_MODE for water)"""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return self._temperature_unit

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return self._hvac_mode

    @property
    def fan_mode(self):
        """Return the current fan status."""
        return self._fan_mode
        
    @property
    def fan_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [FAN_ON, FAN_OFF]

    def set_fan_mode(self, set_mode_to):
        """Using set_fan_mode to set hot water status """
        if (set_mode_to == FAN_ON):
            _LOGGER.info("set_fan_mode called FAN_ON")
            self.therm.set_hotwater_state(HW_F_ON)
            self._fan_mode = FAN_ON
        else:
            _LOGGER.info("set_fan_mode called FAN_OFF - setting DHW off")
            self.therm.set_hotwater_state(HW_F_OFF)
            self._fan_mode = FAN_OFF
        
    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._target_temperature = int(temperature)
        self.therm.set_target_temp(self._target_temperature)

    async def async_update(self):
        _LOGGER.debug("[RS] async_update called")
        self.therm.refresh_data()
        self._temperature_unit = TEMP_CELSIUS  ## TODO:  Make it read units and adjust
        self._current_temperature = self.therm.get_room_temp()
        self._target_temperature = self.therm.get_target_temp()
        self._fan_mode = (
            FAN_OFF
            if (int(self.therm.get_hotwater_status()) == 0)
            else FAN_ON
        )
        self._hvac_mode = (
            HVAC_MODE_OFF
            if (int(self.therm.get_heat_status()) == 0)
            else HVAC_MODE_HEAT
        )
        self._attr_preset_mode = (
            PRESET_HOME
            if (int(self.therm.get_run_mode()) == HEAT_MODE)
            else PRESET_AWAY
        )
        _LOGGER.debug("[RS] Preset mode = {}".format(self._attr_preset_mode))

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        _LOGGER.debug("[RS] async_set_preset_mode called with {}".format(preset_mode))
 
        if preset_mode not in (self._attr_preset_modes):
            raise ValueError(
                f"Got unsupported preset_mode {preset_mode}. Must be one of {self._attr_preset_modes}"
            )
        if preset_mode == self._attr_preset_mode:
            # I don't think we need to call async_write_ha_state if we didn't change the state
            return
        else:
            if preset_mode == PRESET_HOME:
                self.therm.set_run_mode(HEAT_MODE)
                self.therm.set_hotwater_state(HW_TIMER)
            else:
                self.therm.set_run_mode(AWAY)
                self.therm.set_hotwater_state(HW_F_OFF)
            self._attr_preset_mode = preset_mode

    async def async_set_heat_schedule(self, day, time1, temp1, time2=None, temp2=15, time3=None, temp3=15, time4=None, temp4=15):
        """Handle Set heat schedule service call (hard coded arrays at moment)
            NOTE:  Can only program in 30 minute intrevals """
        day = day[0]
        hour1 = time1.hour
        mins1 = time1.minute
        if(time2 == None):
            hour2 = 24
            mins2 = 0
        else:
            hour2 = time2.hour
            mins2 = time2.minute
        if(time3 == None):
            hour3 = 24
            mins3 = 0
        else:
            hour3 = time3.hour
            mins3 = time3.minute
        if(time4 == None):
            hour4 = 24
            mins4 = 0
        else:
            hour4 = time4.hour
            mins4 = time4.minute
        if(mins1 in [0,30] and mins2 in [0,30] and mins3 in [0,30] and mins4 in [0,30]):
            _LOGGER.info("[RS] Set heat sched called with valid minute setting")
        else:
            _LOGGER.error("[RS] Set heat sched called with a non 30 minute interval")
        sched = [hour1,mins1, temp1, hour2,mins2, temp2, hour3,mins3, temp3, hour4,mins4, temp4]
        if day == 'sat':
            weekend = True
        elif day == 'sun':
            weekend = True
        else:
            weekend = False
        _LOGGER.info("[RS] Set heat sched with Weekend={}, {}".format(weekend, sched))
        self.therm.set_heat_schedule(weekend, sched)

    async def async_set_dhw_schedule(self, day, wakeup_time):
        """Handle Set DHW service call (hard coded arrays at moment)"""
        day = day[0]
        hour = wakeup_time.hour
        mins = wakeup_time.minute
#        _LOGGER.info("[RS] Set DHW sched with day={} hour={} mins={}".format(day, hour, mins))
        sched = [4,0, 4,30, hour,mins, hour+2,mins, 13,0, 13,30, 19,0, 21,0]
        if day == 'sat':
            weekend = True
        elif day == 'sun':
            weekend = True
        else:
            weekend = False
        _LOGGER.info("[RS] Set DHW sched with Weekend={}, {}".format(weekend, sched))
        self.therm.set_dhw_schedule(weekend, sched)

    async def async_set_daytime(self, day, set_time):
        """Handle Set Daytime service call"""
        days = {"mon":1, "tue":2, "wed":3, "thu":4, "fri":5, "sat":5, "sun":7}
        day = day[0]
        hour = set_time.hour
        mins = set_time.minute
        secs =set_time.second
        _LOGGER.info("[RS] Set daytime sched with day={} hour={} mins={} secs={}".format(day, hour, mins, secs))
        day_num = days[day]
        self.therm.set_daytime(day_num, hour, mins, secs)



