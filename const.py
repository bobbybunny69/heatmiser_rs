"""Constants for Heatmiser RS thermostats."""
from homeassistant.const import Platform
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_ID,
    CONF_NAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_ENTITY_ID
)

ATTR_DAY = "day"
ATTR_SET_TIME = "set_time"
ATTR_TIME_1 = "time1" 
ATTR_TIME_2 = "time2" 
ATTR_TIME_3 = "time3" 
ATTR_TIME_4 = "time4" 
ATTR_DUR_HRS1 = "dur_hrs1" 
ATTR_DUR_HRS2 = "dur_hrs2" 
ATTR_TEMPERATURE_1 = "temp1" 
ATTR_TEMPERATURE_2 = "temp2" 
ATTR_TEMPERATURE_3 = "temp3" 
ATTR_TEMPERATURE_4 = "temp4" 

DOMAIN = "heatmiser_rs"

PLATFORMS = [Platform.CLIMATE]

CONF_THERMOSTATS = "tstats"

MANUFACTURER = "Robby Saunders"

TEMP_HOLD_TIME_SEC = 43200
HOLIDAY_HOURS_MAX = 1008
HOLIDAY_HOURS_NONE = 0

HW_TIMER = 0
HW_F_ON = 1
HW_F_OFF = 2

HEAT_MODE = 0
AWAY = 1

CONN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.123.253"): str,
        vol.Required(CONF_PORT, default="5000"): str,
    }
)

TSTATS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Optional(CONF_NAME): str,
        vol.Optional("add_another"): cv.boolean,
    }
)

SET_DHW_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DAY): cv.weekdays,
        vol.Required(ATTR_TIME_1): cv.time,
        vol.Required(ATTR_DUR_HRS1): cv.positive_int,
        vol.Required(ATTR_TIME_2): cv.time,
        vol.Required(ATTR_DUR_HRS2): cv.positive_int,
    }
)

SET_HEAT_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DAY): cv.weekdays,
        vol.Required(ATTR_TIME_1): cv.time,
        vol.Required(ATTR_TEMPERATURE_1): cv.positive_int,
        vol.Optional(ATTR_TIME_2): cv.time,
        vol.Optional(ATTR_TEMPERATURE_2): cv.positive_int,
        vol.Optional(ATTR_TIME_3): cv.time,
        vol.Optional(ATTR_TEMPERATURE_3): cv.positive_int,
        vol.Optional(ATTR_TIME_4): cv.time,
        vol.Optional(ATTR_TEMPERATURE_4): cv.positive_int,
    }
)

SET_DAYTIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DAY): cv.weekdays,
        vol.Required(ATTR_SET_TIME): cv.time,
    }
)

SERVICE_SET_DHW_SCHEDULE = "set_dhw_schedule"
SERVICE_SET_HEAT_SCHEDULE = "set_heat_schedule"
SERVICE_SET_DAYTIME = "set_daytime"

