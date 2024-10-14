"""Constants for the Detailed Hello World Push integration."""

# This is the internal name of the integration, it should also match the directory
# name for the integration.
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_ENTITY_ID

DOMAIN = "heatmiser_rs"

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

SET_DHW_SCHEDULE_SCHEMA = {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DAY): cv.weekdays,
        vol.Required(ATTR_TIME_1): cv.time,
        vol.Required(ATTR_DUR_HRS1): cv.positive_int,
        vol.Required(ATTR_TIME_2): cv.time,
        vol.Required(ATTR_DUR_HRS2): cv.positive_int,
    }
SET_HEAT_SCHEDULE_SCHEMA = {
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

SET_DAYTIME_SCHEMA = {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DAY): cv.weekdays,
        vol.Required(ATTR_SET_TIME): cv.time,
    }

