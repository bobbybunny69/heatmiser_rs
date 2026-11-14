"""Platform for climate integration."""
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .heatmiserRS import UH1, MAX_FAILS
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
        self.hub_fail_count = 0     # Consecutive polls where the hub (or every thermo) failed

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
        Raises UpdateFailed (entities go unavailable) if the hub has failed MAX_FAILS polls
        in a row, or straight away on the first refresh so HA retries the setup.
        """
        _LOGGER.debug("[RS] Coordinator _async_update_data called with uh1 = {}".format(self.uh1))
        if await self.uh1.async_read_dcbs():
            self.hub_fail_count = 0
            return True

        self.hub_fail_count += 1
        if self.data is None or self.hub_fail_count >= MAX_FAILS:
            raise UpdateFailed("[RS] Hub offline or no thermos responded ({} failed polls in a row)".format(self.hub_fail_count))
        _LOGGER.warning("[RS] Hub offline or no thermos responded ({} of {} failed polls before unavailable)".format(self.hub_fail_count, MAX_FAILS))
        return False
