# Homeassistant Heatmiser custom component (experimental)
This is my personal custom componet modified from the standard Heatmiser componet by Andy Lockran that fixes a few issues I found and also added a few twaeakes (hacks) to enable adjustemnt of the heating schedule and also control Domestic HW - no problems to use or borrow but do not expect too much

__Note:__   `sensors.py` not used but just in case I want to add later
 

![Image](https://github.com/home-assistant/brands/blob/master/core_integrations/heatmiser/logo.png)

# Installation
* Clone this repo into your `custom_components` folder inside your configuration. So it will be: `custom_components/heatmiser_rs`. 


# Configuration
* Should work with the graphical config flow but may have hard coded some of it
* Assumes Thermos are in the first 'n' channels

# Controlling the Thermostats
* Supports Home and Away modes (falls back to fallback temp when away)
* Use the fan mode as an overiden way of controling Domestic HW (if thermostat supports it)
* creates services for setting the DHW (if supportted) and heating schedules on each thermostats

# Versions (GIT tags)
* v1:  this was the first attempt using config flow and works well
* v2:  change logging level to DEBUG now I have it working for majority of messages
* v3:  move to awaiting async_forward_entry_setups, only open serport at init instead of each access
* v4:  Added coordinator task and fixed blocking calls issue (by adding add_executor asyncio call for serport.close) 

# ToDo
- [ ] Cooridnator task not updating set values immediately - find out why and fix
- [ ] Make the DHW thermostat detection automated (and possibly a sensor)

