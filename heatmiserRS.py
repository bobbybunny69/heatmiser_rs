"""
Rob Saunders 2024
Assume Python 3.10.x +
My version to work async and witha  DataCoordinatoir class in HASS
based of a demonstration 'hub' that connects several devices.
"""
from __future__ import annotations

import asyncio, async_timeout
import serial_asyncio_fast as serial_asyncio
import random

import logging, traceback
_LOGGER = logging.getLogger(__name__)

BYTEMASK = 0xff
MASTER_ADDR = 0x81     # Master address used (must be 129-160)
MAX_CHANS = 8
READ=0
WRITE=1
#Thermo models
PRT = 2
PRTHW = 4
W_TIMER = 0
HW_F_ON = 1
HW_F_OFF = 2
HEAT_MODE = 0
AWAY = 1

TEMP_HOLD_TIME_SEC = 43200
HOLIDAY_HOURS_MAX = 1008
HOLIDAY_HOURS_NONE = 0
MIN_TEMP = 5
MAX_TEMP = 35

#DCB indexes
WEEKDAY_ADDR=40   ### Add 1 for HW thermo for both
WEEKEND_ADDR=52

WEEKDAY_DHW_ADDR=65
WEEKEND_DHW_ADDR=81

MODEL_ADDR = 4
TARGET_ADDR = 18
HEAT_ADDR = 35
RUNMODE_ADDR = 23
AWAYTEMP_ADDR = 17
ROOMTEMP_ADDR = 32
DHW_ADDR = 36
DAY_ADDR = 36 ### Add 1 for HW thermo
TIME_ADDR = 37  ### Ditto
HOLIDAYLEN_ADDR = 24
HEAT_STATUS_ADDR = 41

#Unique write addresses (where different)
DAYTIME_ADDRW = 43
DHW_ADDRW = 42
WEEKDAY_ADDRW = 47
WEEKEND_ADDRW = 59
WEEKDAY_DHW_ADDRW = 71
WEEKEND_DHW_ADDRW = 87


class UH1:
    """Hub for heatmiser control"""
    manufacturer = "Heatmiser"

    def __init__(self, socket: str) -> None:
        """Init dummy hub."""
        _LOGGER.debug("[RS] UH1 __init__ called with socket: {}".format(socket))
        self.socket = socket
        self.socket_grabbed = False 
        self.id = socket.lower()
        self.thermos = [
            Thermostat(self, f"1", f"Kitchen", PRTHW),
            Thermostat(self, f"2", f"Boot Room"),
            Thermostat(self, f"3", f"Living Room"),
            Thermostat(self, f"4", f"Downstairs"),
            Thermostat(self, f"5", f"Upstairs"),
        ]
        self.online = True
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None

    def __del__(self):
        _LOGGER.info("[RS] UH1_com __del__ called")
        #self.writer.close()
 
    async def async_open_connection(self):
        _LOGGER.debug("[RS] Opening serial port")
        if(self.reader != None and self.writer != None):
            _LOGGER.debug("[RS] Serial port already open - skipping")
            return True
        # Using stream reader and writer
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(url=self.socket)
        except Exception as e:
            _LOGGER.error("Error opening connection {}".format(e))
            _LOGGER.error(traceback.format_exc())
            return False
        _LOGGER.debug("[RS] Opened with reader, writer: ".format(self.reader, self.writer))
        return True

    async def async_grab_connection(self):
        _LOGGER.debug("[RS] Checking for serial port contention")
        for i in range (20):   # 2 second dealy
            if(self.socket_grabbed == False):
                _LOGGER.debug("[RS] Managed to get socket")
                self.socket_grabbed = True
                return True
            await asyncio.sleep(0.1)            
        _LOGGER.debug("[RS] Failed to get socket")            
        return False
        

    async def async_read_dcbs(self):
        """
        Read all DCBs in one shot via the eth:serial adapter, and store in thermo dcb array
        """
        _LOGGER.debug("[RS] UH1 refreshing all DCBs data")
        for thermo in self.thermos:
            return_flag = True
            payload = 0  # Since reading - payload is length of bytes to write
            dcb_addr_lo = dcb_addr_hi = 0
            length_lo = length_hi = 0xff  # Since reading full DCB
            msg = [thermo._id, 10+payload, MASTER_ADDR, READ, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]
            crc = CRC16()
            msg = msg + crc.run(msg)
            _LOGGER.debug("[RS] Writing bytes: {}".format(msg))
            self.writer.write(bytes(msg))   # Write a string to trigger tsat to send back a DCB (64bytes since in 5/2 mode)

            _LOGGER.debug("[RS] reading back 9 bytes with timeout incase no connection:")
            try:
                async with async_timeout.timeout(3) as timer:
                    header = await self.reader.readexactly(9)    #  Setup read ready to receive the 9 header bytes
                    _LOGGER.debug("[RS] Header bytes = {}".format(list(header)))
            except Exception as e:
                _LOGGER.warning("Thermo {}:  Error {}".format(thermo._id, e))
                return_flag = False
                continue

            num_bytes = list(header)[7]            
            bytes_read = await self.reader.readexactly(num_bytes+2)    #  Read DCB + CRC
            thermo.dcb = list(bytes_read)[:-2]
            _LOGGER.debug("[RS] DCB bytes = {}".format(thermo.dcb))
            await asyncio.sleep(0.1)       # Added delay as I think I am choking the reader with back2back DCB calls
        return return_flag

    async def async_write_bytes(self, tstat_id, dcb_addr, datal):
        payload = len(datal)  # Since writing - payload is length of bytes to write
        _LOGGER.debug("[RS] Writing {} bytes to tstatid {}: {}".format(payload, tstat_id, datal))
        dcb_addr_lo = dcb_addr & BYTEMASK
        dcb_addr_hi = (dcb_addr>>8) & BYTEMASK
        length_lo = payload  # Since reading less than 256 bytes
        length_hi = 0
        msg = [tstat_id, 10+payload, MASTER_ADDR, WRITE, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]
        msg=msg+datal        
        crc = CRC16()
        msg = msg + crc.run(msg)
        _LOGGER.debug("[RS] Writing bytes: {}".format(msg))
        self.writer.write(bytes(msg))   # Write a string to trigger tsat to send back a DCB (64bytes since in 5/2 mode)

        _LOGGER.debug("[RS] reading back 7 bytes with timeout incase no connection")
        response = await self.reader.readexactly(7)    #  Setup read ready to receive the 9 header bytes
        _LOGGER.debug("[RS] Header bytes = {}".format(list(response)))
        await self.async_update_heat_state(tstat_id)  # In case whatever we did changed heating state
        await asyncio.sleep(0.1)       # Added delay as I think I am choking the reader with back2back DCB calls
        return True

    async def async_update_heat_state(self, tstat_id):
        """ Reading heat status atomically  """ 
        dcb_addr_lo = HEAT_STATUS_ADDR & BYTEMASK
        dcb_addr_hi = (HEAT_STATUS_ADDR>>8) & BYTEMASK
        length_lo = 1
        length_hi = 0
        msg = [tstat_id, 10, MASTER_ADDR, READ, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]       
        crc = CRC16()
        msg = msg + crc.run(msg)
        _LOGGER.debug("[RS] Writing bytes: {}".format(msg))
        self.writer.write(bytes(msg))   # Write a string to trigger tsat to send back heating status only

        _LOGGER.debug("[RS] reading back 12 bytes")
        response = await self.reader.readexactly(12)    #  Setup read ready to receive the 9 header bytes
        _LOGGER.debug("[RS] Heating status bytes = {}".format(list(response)))
        self.thermos[tstat_id-1].dcb[HEAT_ADDR] = list(response)[9]  #  Hacky way of setting right DCB byte for heat status
        return True

class Thermostat():
    """Dummy thermostat (device for HA) for Hello World example."""
    def __init__(self, uh1: UH1, tstat_id: str, name: str, model: int = PRT) -> None:
        """Init dummy thermo."""
        _LOGGER.debug("[RS] Thermostat __init__ called with id, name: {}, {}".format(tstat_id,name) )
        self._id = int(tstat_id)
        self.uh1 = uh1
        self.name = name
        self.dcb = []
        # Some static information about this device
        self.firmware_version = f"0.0.{random.randint(1, 9)}"

    def get_tstat_id(self):
        return self.tstat_id
    
    def get_name(self):
        return self.name

    def get_model(self):
        return 'PRTHW' if self.dcb[MODEL_ADDR]==PRTHW else 'PRT'

    def get_target_temp(self):
        if self.dcb == None:
            return DUMMY_TEMP
        return self.dcb[TARGET_ADDR]

    async def async_set_target_temp(self, temperature: int):
        """
        Updates the set taregt temperature and then 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_target_temp called")

        if 35 < temperature < 5:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (5-35)")
        else:
            datal = [temperature]
            await self.uh1.async_write_bytes(self._id, TARGET_ADDR, datal)
 
    def get_away_temp(self):
        if self.dcb == None:
            return DUMMY_TEMP
        return self.dcb[AWAYTEMP_ADDR]

    async def async_set_away_temp(self, temperature):
        """
        Updates the Away temperature 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_away_temp called")

        if 17 < temperature < 7:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (7-17)")
        else:
            datal = [temperature]
            self.uh1.async_write_bytes(self._id, AWAYTEMP_ADDR, datal)
 
    def get_heat_status(self) -> bool:
        if self.dcb == None:
            return False
        return True if self.dcb[HEAT_ADDR]==1 else False

    def get_run_mode(self):
        if self.dcb == None:
            return HEAT_MODE
        return self.dcb[RUNMODE_ADDR]

    async def async_set_run_mode(self, heat_away):
        """
        Updates the set run_mode HEAT_MODE=0 (deafult) AWAY=1 (aka frost protect)
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_run_mode called with {}".format(heat_away))

        datal = [heat_away]
        await self.uh1.async_write_bytes(self._id, RUNMODE_ADDR, datal)
        
    def get_room_temp(self):
        if self.dcb == None:
            return DUMMY_TEMP
        msb = self.dcb[ROOMTEMP_ADDR]<<8
        lsb = self.dcb[ROOMTEMP_ADDR+1]
        return ((msb+lsb)/10)

    def get_hotwater_status(self):
        if self.dcb == None:
            return False
        if self.get_model() == PRTHW:
            _LOGGER.debug("[RS] HeatmiserThermostat supports HW - read status")
            return True if self.dcb[DHW_ADDR]==1 else False
        else:
            return False

    async def async_set_hotwater(self, onoff):
        """
        Sets the HW state - NOTE:  0=TIMER,  ON=1,  FORCE OFF=2
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_hotwater_state called with {}".format(onoff))

        if self.get_model() != PRTHW:
            _LOGGER.error("[RS] Refusing to set hot-water as incorrect thermo model")
        else:
            datal = [onoff]
            await self.uh1.async_write_bytes(self._id, DHW_ADDRW, datal)

    def get_day(self):
        if self.dcb == None:
            return None
        if self.get_model() == PRTHW:
            return self.dcb[DAY_ADDR+1]
        else:
            return self.dcb[DAY_ADDR]

    def get_time(self):
        if self.dcb == None:
            return None
        if self.get_model() == PRTHW:
            i=TIME_ADDR+1
        else:
            i=TIME_ADDR
        time = self.dcb[i]*3600 
        time+= self.dcb[i+1]*60
        time+= self.dcb[i+2]
        return time

    async def async_set_daytime(self, day, hour, mins, secs):
        """
        Update the day and time NOTE: have to do together as in the same funtion group (see Hetamiser v3 protocol doc)  
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_daytime called with tsatid={}, DD,HH,MM,SS={},{},{},{}".format(self.tstat_id, day,hour,mins,secs))
        datal = [day, hour, mins, secs]
        await self.uh1.async_write_bytes(self._id, DAYTIME_ADDRW, datal)

    def get_holiday(self):
        if self.dcb == None:
            return None
        msb = self.dcb[HOLIDAYLEN_ADDR]<<8
        lsb = self.dcb[HOLIDAYLEN_ADDR+1]
        return False if lsb+msb == 0 else True
        
    async def async_set_holiday(self, hours=HOLIDAY_HOURS_MAX):
        """
        Assume we jam holiday to max 1008 hrs (42 days) (note it swaps to read)  
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_holiday called with {} hours".format(hours))

        lo = hours & 255
        hi = int (hours/256)
        datal = [lo, hi]
        _LOGGER.info("[RS] Setting holiday with following data bytes {}".format(datal))
        await self.uh1.async_write_bytes(self._id, HOLIDAYLEN_ADDR, datal)

    @property
    def tstat_id(self) -> str:
        """Return ID for roller."""
        return self._id

    @property
    def current_temperature(self) -> float:
        """Dummy temeperature generation"""
        _LOGGER.debug("[RS] Thermostat random temp ~12")
        return round(random.random() * 3 + 10, 2)

    @property
    def target_temperature(self) -> float:
        """Return ID for roller."""
        _LOGGER.debug("[RS] Thermostat random set temp ~12")
        return random.randint(16, 27)

    @property
    def online(self) -> float:
        """Thermostat is online."""
        # The dummy thermo is offline about 10% of the time. Returns True if online,
        # False if offline.
        return True


# Believe this is known as CCITT (0xFFFF)
# This is the CRC function converted directly from the Heatmiser C code
# provided in their API
class CRC16:
    """This is the CRC hashing mechanism used by the V3 protocol."""
    LookupHigh = [
        0x00, 0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70,
        0x81, 0x91, 0xa1, 0xb1, 0xc1, 0xd1, 0xe1, 0xf1
    ]
    LookupLow = [
        0x00, 0x21, 0x42, 0x63, 0x84, 0xa5, 0xc6, 0xe7,
        0x08, 0x29, 0x4a, 0x6b, 0x8c, 0xad, 0xce, 0xef
    ]

    def __init__(self):
        self.high = BYTEMASK
        self.low = BYTEMASK

    def extract_bits(self, val):
        """Extras the 4 bits, XORS the message data, and does table lookups."""
        # Step one, extract the Most significant 4 bits of the CRC register
        thisval = self.high >> 4
        # XOR in the Message Data into the extracted bits
        thisval = thisval ^ val
        # Shift the CRC Register left 4 bits
        self.high = (self.high << 4) | (self.low >> 4)
        self.high = self.high & BYTEMASK    # force char
        self.low = self.low << 4
        self.low = self.low & BYTEMASK      # force char
        # Do the table lookups and XOR the result into the CRC tables
        self.high = self.high ^ self.LookupHigh[thisval]
        self.high = self.high & BYTEMASK    # force char
        self.low = self.low ^ self.LookupLow[thisval]
        self.low = self.low & BYTEMASK      # force char

    def update(self, val):
        """Updates the CRC value using bitwise operations."""
        self.extract_bits(val >> 4)    # High nibble first
        self.extract_bits(val & 0x0f)   # Low nibble

    def run(self, message):
        """Calculates a CRC"""
        for value in message:
            self.update(value)
        return [self.low, self.high]