"""Platform for climate integration."""
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    FAN_ON,
    FAN_OFF,
    PRESET_HOME,
    PRESET_AWAY,
    ATTR_HVAC_MODE,
    ATTR_FAN_MODE,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

from .heatmiserRS import Thermostat, MIN_TEMP, MAX_TEMP, HOLIDAY_HOURS_MAX, HW_F_ON, HW_F_OFF
from .const import DOMAIN
from . coordinator import HMCoordinator
import asyncio
import logging
_LOGGER = logging.getLogger(__name__)
DEFAULT_TEMP = 16

# Each thermostat climate are added at
# the same time to the same list. This way only a single async_add_devices call is
# required.
async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Add thermos for passed config_entry in HA."""
    _LOGGER.debug("[RS] climate.py async_setup_entry called with config_entry: {}".format(config_entry))

    coordinator: HMCoordinator = config_entry.runtime_data.coordinator
    #hub: Hub  = config_entry.runtime_data  # hub object was stored in runtime_data in config flow
    _LOGGER.debug("coordinator = {}".format(coordinator))

    # This gets the data update coordinator from hass.data as specified in your __init__.py
    #coordinator = HMCoordinator(hass, hub)
    # Fetch initial data so we have data when entities subscribe
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #await coordinator.async_config_entry_first_refresh()
    
    # Enumerate all the sensors in your data value from your DataUpdateCoordinator and add an instance of your sensor class
    # to a list for each one.
    thermos = [
        HMThermostat(coordinator, t)
        for t in coordinator.uh1.thermos
    ]   

    # Create the thermostats
    _LOGGER.debug("async_add_entries callback called with {}".format(thermos))
    async_add_entities(thermos)

# This class is for the Heatmiser Thermostat
class HMThermostat(CoordinatorEntity, ClimateEntity):
    """Heatmiser Thermostat entity."""
    #should_poll = True   # this should get overidden by CoordinatorEntity

    def __init__(self, coordinator, thermo: Thermostat):
        """Initialize the themrostat."""
        _LOGGER.debug("HMThermostat __init__ called with coord,thermo {} {}".format(coordinator, thermo))
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=thermo)
        self._thermo = thermo
        self._name = self._thermo.name
        self._id = self._thermo._id
        
        self._attr_unique_id = "hmrsthermo_" + str(self._id)
        self._attr_name = self._thermo.name

        self._attr_min_temp = MIN_TEMP
        self._attr_max_temp = MAX_TEMP

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
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

        self._attr_hvac_mode = HVACMode.HEAT if self._thermo.get_heat_status() else HVACMode.OFF
        self._attr_preset_mode = PRESET_AWAY if self._thermo.get_holiday() else PRESET_HOME
        self._attr_fan_mode = FAN_ON if self._thermo.get_hotwater_status() else FAN_OFF
        self._attr_current_temperature = self._thermo.get_room_temp()
        self._attr_target_temperature = self._thermo.get_target_temp()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("[RS] uopdating _attr_ feilds for thermo {}".format(self._id))
        self._attr_hvac_mode = HVACMode.HEAT if self._thermo.get_heat_status() else HVACMode.OFF
        self._attr_preset_mode = PRESET_AWAY if self._thermo.get_holiday() else PRESET_HOME
        self._attr_fan_mode = FAN_ON if self._thermo.get_hotwater_status() else FAN_OFF
        self._attr_current_temperature = self._thermo.get_room_temp()
        self._attr_target_temperature = self._thermo.get_target_temp()
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, off mode."""
        _LOGGER.debug("[RS] hvac_mode for tstat-{} returns {}".format(self._id,self._attr_hvac_mode))
        return self._attr_hvac_mode

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
    def current_temperature(self):
        """Return the current temperature."""
        _LOGGER.debug("[RS] current_temperature for tstat-{} returns {}".format(self._id,self._attr_current_temperature))
        return self._attr_current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.debug("[RS] target_temperature for tstat-{} returns {}".format(self._id,self._attr_target_temperature))
        return self._attr_target_temperature

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        _LOGGER.debug("[RS] set_temperature called with {}".format(kwargs.get(ATTR_TEMPERATURE)))
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._attr_target_temperature = temperature
        result =  await self._thermo.async_set_target_temp(int(temperature))
        self._attr_hvac_mode = HVACMode.HEAT if self._thermo.get_heat_status() else HVACMode.OFF
        self.async_write_ha_state()
        return result

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        _LOGGER.debug("[RS] set_preset_mode called with {}".format(preset_mode))
        self._attr_preset_mode = preset_mode

        if preset_mode == PRESET_HOME:
            result = await self._thermo.async_set_holiday(0)
        else:
            result = await self._thermo.async_set_holiday(HOLIDAY_HOURS_MAX)
        self.async_write_ha_state()
        return result

    async def async_set_hvac_mode(self, **kwargs):
        """Dummy stub as not sure this can be made to do anything sensible but needed to show heat state?"""
        _LOGGER.debug("[RS] set_hvac_mode called with {} but ignoring".format(kwargs))

    async def async_set_fan_mode(self, mode: str):
        """Set new preset mode."""
        _LOGGER.debug("[RS] set_fan_mode called with {}".format(mode))
        self._attr_fan_mode = mode
        if mode == FAN_OFF:
            result = await self._thermo.async_set_hotwater(HW_F_OFF)  # Force off
        else:
            result = await self._thermo.async_set_hotwater(HW_F_ON)
        self.async_write_ha_state()
        return result

    @property
    def device_info(self):
        """Information about this entity/device."""
        _LOGGER.debug("[RS] device info called")
        return {
            "identifiers": {(DOMAIN, self._thermo.tstat_id)},
            # If desired, the name for the device could be different to the entity
            "name": self._thermo.name,
            "sw_version": self._thermo.firmware_version,
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
        """Return True if roller and hub is available."""
        _LOGGER.debug("HMThermostat avaiable returning {} and {} ".format(self._thermo.online, self._thermo.uh1.online))
        return self._thermo.online and self._thermo.uh1.online
