"""Support for the PRT Heatmiser themostats using the V3 protocol.  Supports:
        HVAC_MODE:  Heat, Off (does not modify DHW)
        PRESET_MODE:  Home, Away (also modifies DHW)
        FAN_MODE:  On, Off (Used for DHW control)  
    Also adds custom services to:
        set heating schedule (only Weekday/Weekend mode supportted)
        set DHW schedule (only Weekday/Weekend mode supportted)
        set date/time   """

import logging
from typing import List
from datetime import timedelta
import async_timeout

from . import heatmiserRS as heatmiser 
import voluptuous as vol

from .const import *

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the heatmiser thermostat."""
    conf = entry.data
    _LOGGER.info("[RS] Climate Entry setup called with Config = {}".format(conf))

    uh1 = heatmiser.UH1_com(conf[CONF_HOST], conf[CONF_PORT])
    heatmiser_v3_thermostat = heatmiser.HeatmiserThermostat
    thermostats = conf[CONF_THERMOSTATS]
 
    #heatmiser_rs_api = hass.data[DOMAIN][entry.entry_id]
    coordinator = HeatmiserRS_Coordinator(hass, uh1, conf[CONF_THERMOSTATS])
    
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #

    #await coordinator.async_refresh()
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
        HeatmiserATThermostat(coordinator, heatmiser_v3_thermostat, thermostat, uh1)
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

class HeatmiserRS_Coordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, uh1_con, thermostats):
        """Initialize my coordinator."""
        _LOGGER.debug("[RS] Coordinator _init_ with thermostats = {}".format(thermostats))
        super().__init__(
            hass,
            _LOGGER,    # Name of the data. For logging purposes.
            name="heatmiser_rs",
            update_interval=timedelta(seconds=30),        # Polling interval. Will only be polled if there are subscribers.
        )
        self.uh1_con = uh1_con
        self.tstats = thermostats
       
    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        async with async_timeout.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            _LOGGER.debug("[RS] Coordinator _async_update_data called with ids = {}".format(self.tstats))
            await self.uh1_con.async_read_dcbs(self.tstats)
            

class HeatmiserATThermostat(CoordinatorEntity, ClimateEntity):
    """Heatmiser thermostat Entity using CoordinatorEntity
    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available
    """

    def __init__(self, coordinator, hmv3_therm, device, uh1):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        
        """Initialize the thermostat."""
        self.therm = hmv3_therm(device[CONF_ID], device[CONF_NAME], uh1)    # Do not send UH1 handle as done in config flow
        self._name = device[CONF_NAME]
        self._current_temperature = None
        self._target_temperature = None
        self._preset_mode = None
        self._fan_mode = None
        self._id = device[CONF_ID]
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
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return self._hvac_mode
    
    async def async_set_hvac_mode(self, hvac_mode):
        """Set new HVAC mode."""
        _LOGGER.debug("[RS] async_set_hvac_mode called with {}".format(hvac_mode))
        """Stubbed out
        if (hvac_mode == HVAC_MODE_HEAT):
            _LOGGER.info("[RS] set_hvac_mode called MODE_HEAT")
            await self.therm.async_set_run_mode(HEAT_MODE)
            self._hvac_mode = HEAT_MODE
        else:
            _LOGGER.info("[RS] set_fan_mode called FAN_OFF - setting DHW off")
            await self.therm.async_set_run_mode(AWAY)
        self._hvac_mode = hvac_modeS"""

    @property
    def preset_modes(self) -> List[str]:
        """Return the list of available preset modes. """
        return [PRESET_HOME, PRESET_AWAY]

    @property
    def preset_mode(self):
        """Return the current preset status."""
        return self._preset_mode
        
    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        _LOGGER.debug("[RS] async_set_preset_mode called with {}".format(preset_mode))
 
        if preset_mode == PRESET_HOME:
            await self.therm.async_set_run_mode(HEAT_MODE)
            await self.therm.async_set_hotwater_state(HW_TIMER)
        else:
            await self.therm.async_set_run_mode(AWAY)
            await self.therm.async_set_hotwater_state(HW_F_OFF)
        self._preset_mode = preset_mode
        self.async_write_ha_state()

    @property
    def fan_mode(self):
        """Return the current fan status."""
        return self._fan_mode
        
    @property
    def fan_modes(self) -> List[str]:
        """Return the list of available Fan modes"""
        return [FAN_ON, FAN_OFF]
    
    async def async_set_fan_mode(self, fan_mode):
        """Using set_fan_mode to set hot water status """
        if (fan_mode == FAN_ON):
            _LOGGER.info("[RS] set_fan_mode called FAN_ON")
            await self.therm.async_set_hotwater_state(HW_F_ON)
        else:
            _LOGGER.info("[RS] set_fan_mode called FAN_OFF - setting DHW off")
            await self.therm.async_set_hotwater_state(HW_F_OFF)
        self._fan_mode = fan_mode
        self.async_write_ha_state()

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.debug("[RS] target_temperature read for tstat {} = {}".format(self._id, self._target_temperature))
        return self._target_temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._target_temperature = int(temperature)
        await self.therm.async_set_target_temp(self._target_temperature)
        self.async_write_ha_state()


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.info("[RS] _handle_coordinator_update called for tstat {}".format(self._id))
        self.therm.refresh_dcb()
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
        self.async_write_ha_state()

    """async def async_update(self):
        _LOGGER.info("[RS] async_update called for tstat {}".format(self._id))
        await self.therm.async_refresh_dcb()
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
        _LOGGER.debug("[RS] Preset mode = {}".format(self._attr_preset_mode))"""

    async def async_set_heat_schedule(self, day, time1, temp1, time2=None, temp2=15, time3=None, temp3=15, time4=None, temp4=15):
        """Handle Set heat schedule service call (hard coded arrays at moment)  NOTE:  Can only program in 30 minute intrevals """
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
            _LOGGER.info("[RS] async_set_heat_schedule called valid mins and day={}, time1={}, {}".format(day, time1, temp1))
        else:
            _LOGGER.error("[RS] Set heat sched called with a non 30 minute interval")
        sched = [hour1,mins1, temp1, hour2,mins2, temp2, hour3,mins3, temp3, hour4,mins4, temp4]
        if day == 'sat':
            weekend = True
        elif day == 'sun':
            weekend = True
        else:
            weekend = False
        _LOGGER.debug("[RS] Setting heat schedule with Weekend={}, {}".format(weekend, sched))
        await self.therm.async_set_heat_schedule(weekend, sched)

    async def async_set_dhw_schedule(self, day, time1, dur_hrs1, time2, dur_hrs2):
        """Handle Set DHW service call (hard coded arrays at moment)"""
        _LOGGER.info("[RS] async_set_dhw_schedule called with day={}, wakeup_time, duration={},{}".format(day, time1, dur_hrs1))
        day = day[0]
        hr1 = time1.hour
        mins1 = time1.minute
        hr2 = time2.hour
        mins2 = time2.minute
        sched = [4,0, 4,30, hr1,mins1, hr1+dur_hrs1,mins1, 13,0, 13,30, hr2,mins2, hr2+dur_hrs2,mins2]
        if day == 'sat':
            weekend = True
        elif day == 'sun':
            weekend = True
        else:
            weekend = False
        _LOGGER.debug("[RS] Setting DHW schedule with Weekend={}, {}".format(weekend, sched))
        await self.therm.async_set_dhw_schedule(weekend, sched)

    async def async_set_daytime(self, day, set_time):
        """Handle Set Daytime service call"""
        _LOGGER.info("[RS] async_set_daytime called with day={}, set_time={}".format(day, set_time))
        days = {"mon":1, "tue":2, "wed":3, "thu":4, "fri":5, "sat":6, "sun":7}
        day = day[0]
        hour = set_time.hour
        mins = set_time.minute
        secs =set_time.second
        _LOGGER.debug("[RS] Setting daytime with day={} hour={} mins={} secs={}".format(day, hour, mins, secs))
        day_num = days[day]
        await self.therm.async_set_daytime(day_num, hour, mins, secs)
