"""Platform for climate integration."""
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .heatmiserRS import UH1
from .const import DOMAIN
from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__name__)
DEFAULT_TEMP = 16

class HMCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, config_entry, socket_str):
        """Initialize my coordinator."""
        _LOGGER.debug("[RS] Coordinator _init_ with socket= {}".format(socket_str))
        
        super().__init__(
            hass,
            _LOGGER,    # Name of the data. For logging purposes.
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_method=self.async_update_data,  # method to call on update interval
            update_interval=timedelta(seconds=60),   # Polling interval. Will only be polled if there are subscribers.
            )

        self.uh1 = UH1(socket_str)

    async def _async_setup(self):
        """Set up the coordinator
        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.
        For me this is to open the serail connection
        """
        _LOGGER.debug("[RS] Coordinator _async_setup called with uh1 = {}".format(self.uh1))
        #await self.uh1.async_open_connection()

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        #async with async_timeout.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
        _LOGGER.debug("[RS] Coordinator _async_update_data called with uh1 = {}".format(self.uh1))
        return await self.uh1.async_read_dcbs()


