# Homeassistant Heatmiser custom component (experimental)
This is my personal custom componet modified from the standard Heatmiser componet by Andy Lockran that fixes a few issues I found and also added a few twaeakes (hacks) to enable adjustemnt of the heating schedule and also control Domestic HW - no problems to use or borrow but do not expect too much
 

![Image](https://github.com/home-assistant/brands/blob/master/core_integrations/heatmiser/logo.png)

# Installation
* Clone this repo into your `custom_components` folder inside your configuration. So it will be: `custom_components/heatmiser_rs`. 


# Configuration
* Should work with the graphical config flow but may have hard coded some of it
* Assumes Thermos are in the first 'n' channels

# Controlling the Thermostats
* Supports Home and Away modes (fals back to fallback teno when away)
* Use the fan mode as an overided way of controling Domestic HW (if thermostat supports it)

# ToDO
- [ ] Get read of the bocking call compaints in Home Assistant
- [ ] Make the DHW thermostat detection automated

