"""
Adds Support for Senors with Heatmiser Thermostat

Author: me

"""

from datetime import timedelta
import async_timeout

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity import Entity

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    PERCENTAGE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_VOLT,
)

DOMAIN = "atagone"
DEFAULT_NAME = "Atag One"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_TYPES = {
    "dhw_temp_setp": ["DHW Temp Setpoint", "°C", "mdi:thermometer"],
    "dhw_status": ["DHW Status", "", "mdi:water-boiler"],
    "dhw_mode": ["DHW Mode", "", "mdi:water-boiler"],
    "dhw_mode_temp": ["DHW Mode Temp", "°C", "mdi:thermometer"],
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([HeatmsierSensor(coordinator, sensor) for sensor in SENSOR_TYPES])

class HeatmiserSensor(Entity):
    """Representation of a Heatmiser Sensor."""

    def __init__(self, coordinator, sensor):
        """Initialize the sensor."""

        self.coordinator = coordinator
        self.type = sensor
        self._sensor_prefix = DEFAULT_NAME
        self._entity_type = SENSOR_TYPES[self.type][0]
        self._name = "{} {}".format(self._sensor_prefix, SENSOR_TYPES[self.type][0])
        self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]

    def boiler_status(self, state):
        """boiler status conversions"""
        state = state & 14
        if state == 8:
            self._unit = "Boiler"
            self._icon = "mdi:water-boiler"
        elif state == 10:
            self._unit = "Central"
            self._icon = "mdi:fire"
        elif state == 12:
            self._unit = "Water"
            self._icon = "mdi:fire"
        else:
            self._unit = "Idle"
            self._icon = "mdi:flash"

        return state

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return f"{self._sensor_prefix}_{self._entity_type}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            state = self.coordinator.data.sensors[self.type]
            if state:
                if self.type == "boiler_status":
                    return self.boiler_status(state)
                return state
            return 0
        except KeyError:
            _LOGGER.error("can't find %s", self.type)
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes of this device."""
        pass
