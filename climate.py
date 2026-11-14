"""Platform for climate integration."""
from homeassistant.core import callback

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    FAN_ON,
    FAN_OFF,
    PRESET_HOME,
    PRESET_AWAY,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import entity_platform, service
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE, ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .heatmiserRS import Thermostat, MIN_TEMP, MAX_TEMP, HOLIDAY_HOURS_MAX, HW_F_ON, HW_F_OFF, HEAT_MODE, AWAY
from .const import DOMAIN, SET_DHW_SCHEDULE_SCHEMA, SET_HEAT_SCHEDULE_SCHEMA, SET_DAYTIME_SCHEMA
from . coordinator import HMCoordinator
import logging
import asyncio
_LOGGER = logging.getLogger(__name__)
DEFAULT_TEMP = 16
CONN_RETRIES = 3

# Each thermostat climate are added at
# the same time to the same list. This way only a single async_add_devices call is
# required.
async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Add thermos for passed config_entry in HA."""
    _LOGGER.debug("[RS] climate.py async_setup_entry called with config_entry: {}".format(config_entry))

    # This gets the data update coordinator from hass.data as specified in your __init__.py
    coordinator: HMCoordinator = config_entry.runtime_data.coordinator
    _LOGGER.debug("[RS] coordinator = {}".format(coordinator))
  
    # Enumerate all the Thermos in your data value from your DataUpdateCoordinator 
    # and add an instance of HMThermostat class to a list for each one.
    thermos = [
        HMThermostat(coordinator, t)
        for t in coordinator.uh1.thermos
    ]   
    # Create the thermostats
    async_add_entities(thermos)
    _LOGGER.debug("[RS] async_add_entries callback called with {}".format(thermos))

    # Register the entity service callbacks to set schedules, time, etc
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_dhw_schedule",
        SET_DHW_SCHEDULE_SCHEMA,
        "async_set_dhw_schedule",
    )
    platform.async_register_entity_service(
        "set_heat_schedule",
        SET_HEAT_SCHEDULE_SCHEMA,
        "async_set_heat_schedule",
    )
    platform.async_register_entity_service(
        "set_daytime",
        SET_DAYTIME_SCHEMA,
        "async_set_daytime",
    )


# This class is for the Heatmiser Thermostat
class HMThermostat(CoordinatorEntity, ClimateEntity):
    """Heatmiser Thermostat entity."""
    #should_poll = True   # this should get overidden by CoordinatorEntity

    def __init__(self, coordinator, thermo: Thermostat):
        """Initialize the themrostat."""
        _LOGGER.debug("[RS] HMThermostat __init__ called with coord,thermo {} {}".format(coordinator, thermo))
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=thermo)
        self._thermo: Thermostat = thermo
        self._name = self._thermo.name
        self._id = self._thermo._id
        
        self._attr_unique_id = "hmrsthermo_" + str(self._id)
        self._attr_name = self._thermo.name

        self._attr_min_temp = MIN_TEMP
        self._attr_max_temp = MAX_TEMP

        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature_step = 1
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_supported_features |= ClimateEntityFeature.TURN_ON
        self._attr_supported_features |= ClimateEntityFeature.TURN_OFF
        self._attr_supported_features |=  ClimateEntityFeature.PRESET_MODE
        if self._thermo.get_model() == "PRTHW":
            self._attr_supported_features |=  ClimateEntityFeature.FAN_MODE

        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_fan_modes = [FAN_OFF, FAN_ON]
        self._attr_preset_modes = [PRESET_HOME, PRESET_AWAY]

        self._attr_hvac_mode = self._get_hvac_mode()
        self._attr_hvac_action = self._get_hvac_action()
        self._attr_preset_mode = PRESET_AWAY if self._thermo.get_holiday() else PRESET_HOME
        self._attr_fan_mode = FAN_ON if self._thermo.get_hotwater_status() else FAN_OFF
        self._attr_native_current_temperature = self._thermo.get_room_temp()
        self._attr_native_target_temperature = self._thermo.get_target_temp()

    def _get_hvac_mode(self):
        """HEAT for normal run mode, OFF for frost protect run mode"""
        return HVACMode.HEAT if self._thermo.get_run_mode() == HEAT_MODE else HVACMode.OFF

    def _get_hvac_action(self):
        """HEATING if the thermo is calling for heat (can happen in frost protect), else IDLE or OFF"""
        if self._thermo.get_heat_status():
            return HVACAction.HEATING
        return HVACAction.IDLE if self._get_hvac_mode() == HVACMode.HEAT else HVACAction.OFF

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("[RS] _handle_coordinator_update updating _attr_ feilds for thermo {}".format(self._id))
        self._attr_hvac_mode = self._get_hvac_mode()
        self._attr_hvac_action = self._get_hvac_action()
        self._attr_preset_mode = PRESET_AWAY if self._thermo.get_holiday() else PRESET_HOME
        self._attr_fan_mode = FAN_ON if self._thermo.get_hotwater_status() else FAN_OFF
        self._attr_native_current_temperature = self._thermo.get_room_temp()
        self._attr_native_target_temperature = self._thermo.get_target_temp()
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, off mode."""
        _LOGGER.debug("[RS] hvac_mode for tstat-{} returns {}".format(self._id,self._attr_hvac_mode))
        return self._attr_hvac_mode

    @property
    def hvac_action(self):
        """Return current action ie. heating (calling for heat), idle or off."""
        _LOGGER.debug("[RS] hvac_action for tstat-{} returns {}".format(self._id,self._attr_hvac_action))
        return self._attr_hvac_action

    @property
    def preset_mode(self) -> str:
        """Return preset mode ie. home or away."""
        _LOGGER.debug("[RS] preset_mode for tstat-{} returns {}".format(self._id,self._attr_preset_mode))
        return self._attr_preset_mode

    @property
    def fan_mode(self):
        """Return the current fan status (overidden for hot water control)"""
        _LOGGER.debug("[RS] fan_mode for tstat-{} returns {}".format(self._id,self._attr_fan_mode))
        return self._attr_fan_mode

    @property
    def native_current_temperature(self):
        """Return the current temperature."""
        _LOGGER.debug("[RS] current_temperature for tstat-{} returns {}".format(self._id,self._attr_native_current_temperature))
        return self._attr_native_current_temperature

    @property
    def native_target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.debug("[RS] target_temperature for tstat-{} returns {}".format(self._id,self._attr_native_target_temperature))
        return self._attr_native_target_temperature

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        _LOGGER.info("[RS] set_temperature called with {}".format(kwargs.get(ATTR_TEMPERATURE)))
        temperature = kwargs.get(ATTR_TEMPERATURE)
        result =  await self._thermo.async_set_target_temp(int(temperature))
        self._check_write(result, "set target temperature")
        self._attr_native_target_temperature = temperature
        self._attr_hvac_action = self._get_hvac_action()
        self.async_write_ha_state()
        return result

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        _LOGGER.info("[RS] set_preset_mode called with {}".format(preset_mode))

        if preset_mode == PRESET_HOME:
            result = await self._thermo.async_set_holiday(0)
        else:
            result = await self._thermo.async_set_holiday(HOLIDAY_HOURS_MAX)
        self._check_write(result, "set preset mode")
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
        return result

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set HEAT (normal run mode) or OFF (frost protect run mode)"""
        _LOGGER.info("[RS] set_hvac_mode called with {}".format(hvac_mode))
        run_mode = HEAT_MODE if hvac_mode == HVACMode.HEAT else AWAY
        result = await self._thermo.async_set_run_mode(run_mode)
        self._check_write(result, "set HVAC mode")
        self._attr_hvac_mode = hvac_mode
        self._attr_hvac_action = self._get_hvac_action()
        self.async_write_ha_state()
        return result

    async def async_set_fan_mode(self, mode: str):
        """Set new preset mode."""
        _LOGGER.info("[RS] set_fan_mode called with {}".format(mode))
        if mode == FAN_OFF:
            result = await self._thermo.async_set_hotwater(HW_F_OFF)  # Force off
        else:
            result = await self._thermo.async_set_hotwater(HW_F_ON)
        self._check_write(result, "set hot water")
        self._attr_fan_mode = mode
        self.async_write_ha_state()
        return result

    @property
    def device_info(self):
        """Information about this entity/device."""
        _LOGGER.debug("[RS] device info called")
        return {
            "identifiers": {(DOMAIN, self._thermo._id)},
            # If desired, the name for the device could be different to the entity
            "name": self._thermo.name,
            "sw_version": self._thermo.fw_version,
            "model": self._thermo.get_model(),
            "manufacturer": self._thermo.uh1.manufacturer
        }

    @property
    def icon(self) -> str | None:
        """Icon of the entity, based on heat state."""
        return "mdi:thermostat"

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return False if the coordinator poll failed or thermo has failed MAX_FAILS reads in a row"""
        _LOGGER.debug("[RS] HMThermostat available: Thermo online = {}, fail count = {} ".format(self._thermo.online, self._thermo.fail_count))
        return super().available and self._thermo.available

    def _check_write(self, result, action: str) -> None:
        """Raise an error (shown in the UI / stops automations) if a write to the thermo failed"""
        if not result:
            raise HomeAssistantError("Heatmiser: failed to {} on {} (hub offline or no ACK)".format(action, self._thermo.name))

    async def async_set_daytime(self, day, set_time):
        """Handle Set Daytime service call"""
        days = {"mon":1, "tue":2, "wed":3, "thu":4, "fri":5, "sat":6, "sun":7}
        day = day[0]
        hour = set_time.hour
        mins = set_time.minute
        secs =set_time.second
        _LOGGER.info("[RS] Set daytime sched with day={} hour={} mins={} secs={}".format(day, hour, mins, secs))
        day_num = days[day]
        result = await self._thermo.async_set_daytime(day_num, hour, mins, secs)
        self._check_write(result, "set day/time")
        return result
       
    async def async_set_heat_schedule(self, day, time1, temp1, time2=None, temp2=None, time3=None, temp3=None, time4=None, temp4=None):
        """Handle Set heat schedule service call  NOTE: Can only program in 30 minute intrevals """
        day = day[0]
        sched = []
        prev_mins = None
        prev_slot = 0
        for n, (t, temp) in enumerate([(time1, temp1), (time2, temp2), (time3, temp3), (time4, temp4)], start=1):
            if t is None and temp is None:
                sched += [24, 0, 15]    # Hour 24 = period cancelled
                continue
            if t is None or temp is None:
                raise ServiceValidationError("Heatmiser: time{0} and temp{0} must be given together".format(n))
            if prev_slot != n-1:
                raise ServiceValidationError("Heatmiser: time{} given but time{} is missing (periods must be filled in order)".format(n, n-1))
            if t.minute not in [0, 30]:
                raise ServiceValidationError("Heatmiser: time{} ({:02d}:{:02d}) must be on the hour or half hour".format(n, t.hour, t.minute))
            if not MIN_TEMP <= temp <= MAX_TEMP:
                raise ServiceValidationError("Heatmiser: temp{} ({}) must be between {} and {}".format(n, temp, MIN_TEMP, MAX_TEMP))
            mins = t.hour*60 + t.minute
            if prev_mins is not None and mins <= prev_mins:
                raise ServiceValidationError("Heatmiser: time{} ({:02d}:{:02d}) must be later than time{}".format(n, t.hour, t.minute, n-1))
            prev_mins = mins
            prev_slot = n
            sched += [t.hour, t.minute, temp]
        if day=='sat' or day=='sun':
            weekend = True
        else:
            weekend = False
        _LOGGER.info("[RS] Set heat sched with Weekend={}, {}".format(weekend, sched))
        result = await self._thermo.async_set_heat_schedule(weekend, sched)
        self._check_write(result, "set heat schedule")
        return result

    async def async_set_dhw_schedule(self, day, time1, dur_hrs1, time2, dur_hrs2):
        """Handle Set DHW service call - fixed 04:00-04:30 and 13:00-13:30 slots, plus a morning and evening period"""
        _LOGGER.debug("[RS] async_set_dhw_schedule called with day={}, times={},{} durations={},{}".format(day, time1, time2, dur_hrs1, dur_hrs2))
        day = day[0]
        hr1 = time1.hour
        mins1 = time1.minute
        hr2 = time2.hour
        mins2 = time2.minute
        if dur_hrs1 < 1 or dur_hrs2 < 1:
            raise ServiceValidationError("Heatmiser: DHW durations must be at least 1 hour")
        if (hr1, mins1) < (4, 30):
            raise ServiceValidationError("Heatmiser: DHW morning on time ({:02d}:{:02d}) must be 04:30 or later (after the fixed 04:00-04:30 slot)".format(hr1, mins1))
        if (hr1+dur_hrs1, mins1) > (13, 0):
            raise ServiceValidationError("Heatmiser: DHW morning period ({:02d}:{:02d} for {}h) must end by 13:00 (before the fixed 13:00-13:30 slot)".format(hr1, mins1, dur_hrs1))
        if (hr2, mins2) < (13, 30):
            raise ServiceValidationError("Heatmiser: DHW evening on time ({:02d}:{:02d}) must be 13:30 or later (after the fixed 13:00-13:30 slot)".format(hr2, mins2))
        if hr2+dur_hrs2 >= 24:
            raise ServiceValidationError("Heatmiser: DHW evening period ({:02d}:{:02d} for {}h) must end before 24:00".format(hr2, mins2, dur_hrs2))
        sched = [4,0, 4,30, hr1,mins1, hr1+dur_hrs1,mins1, 13,0, 13,30, hr2,mins2, hr2+dur_hrs2,mins2]
        if day == 'sat':
            weekend = True
        elif day == 'sun':
            weekend = True
        else:
            weekend = False
        _LOGGER.info("[RS] Setting DHW schedule with Weekend={}, {}".format(weekend, sched))
        result = await self._thermo.async_set_dhw_schedule(weekend, sched)
        self._check_write(result, "set DHW schedule")
        return result
