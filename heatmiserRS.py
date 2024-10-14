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
TIMEOUT = 1
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
        self.id = socket.lower()
        self.thermos = [
            Thermostat(self, f"1", f"Kitchen", PRTHW),
            Thermostat(self, f"2", f"Boot Room"),
            Thermostat(self, f"3", f"Living Room"),
            Thermostat(self, f"4", f"Downstairs"),
            Thermostat(self, f"5", f"Upstairs"),
        ]
        self.online = False
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None

    def __del__(self):
       _LOGGER.info("[RS] UH1_com __del__ called - nothing to do")
 
    async def async_open_connection(self):
        _LOGGER.debug("[RS] async_open_connection Opening serial port")
        # Using stream reader and writer
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(url=self.socket)
        except Exception as e:
            _LOGGER.error("Error opening connection {}".format(e))
            _LOGGER.debug(traceback.format_exc())
            self.online = False
            return False
        _LOGGER.debug("[RS] Opened with reader, writer: ".format(self.reader, self.writer))
        return True

    async def async_read_dcb(self, thermo: Thermostat, timeout):
        payload = 0  # Since reading - payload is zero
        dcb_addr_lo = dcb_addr_hi = 0
        length_lo = length_hi = 0xff  # Since reading full DCB
        msg = [thermo._id, 10+payload, MASTER_ADDR, READ, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]
        crc = CRC16()
        msg = msg + crc.run(msg)        
        _LOGGER.debug("[RS] Writing bytes: {}".format(msg))
        self.writer.write(bytes(msg))   # Write a string to trigger tsat to send back a DCB
        
        _LOGGER.debug("[RS] reading back 9 byte header with timeout incase no connection")
        try:
            async with async_timeout.timeout(timeout) as timer:
                header = await self.reader.readexactly(9)    #  Setup read ready to receive the 9 header bytes
                _LOGGER.debug("[RS] Header bytes = {}".format(list(header)))
        except Exception as e:
            _LOGGER.error("Thermo {}:  Error {}".format(thermo._id, e))
            _LOGGER.debug(traceback.format_exc())
            thermo.online = False
            return False

        _LOGGER.debug("[RS] reading back rest of DCB")
        num_bytes = list(header)[7]            
        bytes_read = await self.reader.readexactly(num_bytes+2)    #  Read DCB + CRC
        thermo.dcb = list(bytes_read)[:-2]
        _LOGGER.debug("[RS] DCB bytes = {}".format(thermo.dcb))
        thermo.online = any_thermos_live = True            
        await asyncio.sleep(0.1)    # Added delay as I think I am choking the reader with back2back DCB calls

    async def async_read_dcbs(self):
        """
        Read all DCBs in one shot via the eth:serial adapter, and store in thermo dcb array
        """
        _LOGGER.debug("[RS] async_read_dcbs UH1 refreshing all DCBs data")
        if not await self.async_open_connection():
            _LOGGER.info("[RS] Hub offline!!!")
            return False
        any_thermos_live = False
        for thermo in self.thermos:
            if await self.async_read_dcb(thermo, TIMEOUT):
                thermo.online = any_thermos_live = True                    
        self.writer.close()
        return any_thermos_live         #  return status (True/False)

    async def async_write_bytes(self, thermo: Thermostat, dcb_addr, datal=[]):
        """
        Write specifc bytes via the eth:serial adapter, and readback DCB in case it triggered a change
        """
        _LOGGER.debug("[RS] async_write_bytes UH1 called")
        if not await self.async_open_connection():
            _LOGGER.info("[RS] Hub offline!!!")
            return False

        payload = len(datal)  # Since writing - payload is length of bytes to write
        _LOGGER.debug("[RS] Writing {} bytes to tstatid {}: {}".format(payload, thermo._id, datal))
        length_lo = payload
        length_hi = 0       # since reading back less than 256 bytes
        dcb_addr_lo = dcb_addr & BYTEMASK
        dcb_addr_hi = (dcb_addr>>8) & BYTEMASK
        msg = [thermo._id, 10+payload, MASTER_ADDR, WRITE, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]
        msg=msg+datal        
        crc = CRC16()
        msg = msg + crc.run(msg)
        _LOGGER.debug("[RS] Writing bytes: {}".format(msg))
        self.writer.write(bytes(msg))   # Write payload to correct thermo
        await self.writer.drain()

        _LOGGER.debug("[RS] reading back 7 byte ACK with timeout incase no connection")
        try:
            async with async_timeout.timeout(TIMEOUT) as timer:
                response = await self.reader.readexactly(7)    #  Setup read ready to receive the 9 header bytes
                _LOGGER.debug("[RS] Ack bytes = {}".format(list(response)))
        except Exception as e:
            _LOGGER.error("Thermo {}:  Error {}".format(thermo._id, e))
            _LOGGER.debug(traceback.format_exc())
            return False
        await self.async_read_dcb(thermo, TIMEOUT)
        self.writer.close()
        await asyncio.sleep(0.1)
        return True

class Thermostat():
    """Dummy thermostat (device for HA) for Hello World example."""
    def __init__(self, uh1: UH1, tstat_id: str, name: str, model: int = PRT) -> None:
        """Init dummy thermo."""
        _LOGGER.debug("[RS] Thermostat __init__ called with id, name: {}, {}".format(tstat_id,name) )
        self._id = int(tstat_id)
        self.uh1 = uh1
        self.name = name
        self.dcb = None
        self.online = False
        self.model = PRT
        self.fw_version = 'v6.x.y.x'

    def get_tstat_id(self):
        return self._id
    
    def get_name(self):
        return self.name

    def get_model(self):
        if self.online == True:
            self.model = self.dcb[MODEL_ADDR]
        return 'PRTHW' if self.model==PRTHW else 'PRT'

    def get_target_temp(self):
        if self.online == False:
            return None
        return self.dcb[TARGET_ADDR]

    async def async_set_target_temp(self, temperature: int):
        """
        Updates the set taregt temperature and then 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_target_temp called")

        if MAX_TEMP < temperature < MIN_TEMP:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (5-35)")
        else:
            datal = [temperature]
            await self.uh1.async_write_bytes(self, TARGET_ADDR, datal)
 
    def get_away_temp(self):
        if self.online == False:
            return None
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
            self.uh1.async_write_bytes(self, AWAYTEMP_ADDR, datal)
 
    def get_heat_status(self) -> bool:
        if self.online == False:
            return False
        return True if self.dcb[HEAT_ADDR]==1 else False

    def get_hotwater_status(self):
        if self.online == False:
            return False
        if self.dcb[MODEL_ADDR] == PRTHW:
            _LOGGER.debug("[RS] HeatmiserThermostat supports HW - read status")
            return True if self.dcb[DHW_ADDR]==1 else False
        else:
            return False

    async def async_set_hotwater(self, onoff):
        """
        Sets the HW state - NOTE:  0=TIMER,  ON=1,  FORCE OFF=2
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_hotwater_state called with {}".format(onoff))

        if self.dcb[MODEL_ADDR] != PRTHW:
            _LOGGER.error("[RS] Refusing to set hot-water as incorrect thermo model")
            return False
        else:
            datal = [onoff]
            return await self.uh1.async_write_bytes(self, DHW_ADDRW, datal)

    def get_holiday(self):
        if self.online == False:
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
        return await self.uh1.async_write_bytes(self, HOLIDAYLEN_ADDR, datal)

    def get_run_mode(self):
        if self.online == False:
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
        if self.online == False:
            return None
        msb = self.dcb[ROOMTEMP_ADDR]<<8
        lsb = self.dcb[ROOMTEMP_ADDR+1]
        return ((msb+lsb)/10)

    async def async_set_daytime(self, day, hour, mins, secs):
        """
        Update the day and time NOTE: have to do together as in the same funtion group (see Hetamiser v3 protocol doc)  
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_daytime called with tsatid={}, DD,HH,MM,SS={},{},{},{}".format(self._id, day,hour,mins,secs))
        datal = [day, hour, mins, secs]
        return await self.uh1.async_write_bytes(self, DAYTIME_ADDRW, datal)

    async def async_set_heat_schedule(self, weekend, sched_array):
        """
        Sending direct to thermo
        NOTE: CAN ONLY USE 30 Minute intervals to program 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_schedule called (Heating)")
        if (weekend == True):
            dcb_addr = WEEKEND_ADDRW
        else:
            dcb_addr = WEEKDAY_ADDRW
        _LOGGER.info("[RS] set_heat_schedule called with tsatid={}, DCB={}, {}".format(self._id, dcb_addr, sched_array))
        return await self.uh1.async_write_bytes(self, dcb_addr, sched_array)

    async def async_set_dhw_schedule(self, weekend, sched_array):
        """
        NOTE:  not using the self data array but setting direct to thermo
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_dhw_schedule called (Hot water)")
        if (weekend == True):
            dcb_addr = WEEKEND_DHW_ADDRW
        else:
            dcb_addr = WEEKDAY_DHW_ADDRW
        _LOGGER.info("[RS] set_dhw_schedule called with tsatid={}, DCB={}, {}".format(self._id, dcb_addr, sched_array))
        return await self.uh1.async_write_bytes(self, dcb_addr, sched_array)

    def get_day(self):
        if self.online == False:
            return None
        if self.get_model() == 'PRTHW':
            return self.dcb[DAY_ADDR+1]
        else:
            return self.dcb[DAY_ADDR]

    def get_time(self):
        if self.online == False:
            return None
        if self.get_model() == 'PRTHW':
            i=TIME_ADDR+1
        else:
            i=TIME_ADDR
        time = self.dcb[i]*3600 
        time+= self.dcb[i+1]*60
        time+= self.dcb[i+2]
        return time

    def get_heat_schedule(self, weekend):
        if self.online == False:
            return None
        if (weekend == True):
            dcb_addr = WEEKEND_ADDR
        else:
            dcb_addr = WEEKDAY_ADDR
        if self.get_model() == 'PRTHW':
            dcb_addr += 1
        data_array = self.dcb[dcb_addr : dcb_addr+12] #read 12 bytes
        return data_array

    def get_dhw_schedule(self, weekend):
        if self.online == False:
            return None
        if self.get_model() == 'PRTHW':
            _LOGGER.debug("[RS] HeatmiserThermostat support HW - read status")
            if (weekend == True):
                dcb_addr = WEEKEND_DHW_ADDR
            else:
                dcb_addr = WEEKDAY_DHW_ADDR
            data_array = self.dcb[dcb_addr : dcb_addr+16]   #read 16 bytes for 4 on/offs
            return data_array
        else:
            _LOGGER.error("[RS] Trying to get DHW schedule from non PRTHW model")
            return False

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