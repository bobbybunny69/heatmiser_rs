#
# Rob Saunders 2020
# Assume Python 3.10.x +
# My version to do a more atomic reading of the stats
import logging
import time
import asyncio
import serial_asyncio_fast as serial_asyncio
#from .const import *

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

print(_LOGGER)

BYTEMASK = 0xff
# Master address used (must be 129-160)
MASTER_ADDR = 0x81
MAX_CHANS = 8

READ=0
WRITE=1
WEEKEND = True
WEEKDAY = False

DUMMY_TEMP = 17.0
OFF = 0

HW_TIMER = 0
HW_F_ON = 1
HW_F_OFF = 2
HEAT_MODE = 0
AWAY = 1

#Thermo models
PRT = 2
PRTHW = 4

#DCB lengths
PRT_DCB_LEN = 75
PRTHW_DCB_LEN = 108

#DCB address indexes
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

#Unique write addresses (where different)
DAYTIME_ADDRW = 43
DHW_ADDRW = 42
WEEKDAY_ADDRW = 47
WEEKEND_ADDRW = 59
WEEKDAY_DHW_ADDRW = 71
WEEKEND_DHW_ADDRW = 87

TEMP_HOLD_TIME_SEC = 43200
HOLIDAY_HOURS_MAX = 1008
HOLIDAY_HOURS_NONE = 0

"""
UH1 connection to the Heatmiser system
"""
class UH1_com:    
    def __init__(self, host, port):
        _LOGGER.debug("[RS] UH1_com __init__ called")
        self.port = "socket://" + host + ":" + port
        self.dcb_dict = {}   # this will get emptied and filled as we read DCBs
        self.transport = None
        self.protocol = None
        self.read_buff = []
    
    async def async_open_conn(self, buf):
        class Protocol(asyncio.Protocol):
            def connection_made(self, transport):
                self.transport = transport
                _LOGGER.info("[RS] Port opened")

            def connection_lost(self, exc):
                _LOGGER.info("[RS] connection_lost callback called")
                self.transport.loop.stop()

            def data_received(self, data):
                #_LOGGER.debug("[RS] Read buffer: {}".format(buf))
                for b in data:
                    buf.append(b)
                self.read_buff = buf             

            def pause_reading(self):
                _LOGGER.debug("[RS] Paused reading tansport: Halting callbacks")
                self.transport.pause_reading()

            def resume_reading(self):
                _LOGGER.debug("[RS] Resumed reading tansport: Re-starting callbacks")
                self.transport.resume_reading()

            def pause_writing(self):
                _LOGGER.debug("[RS] Pause writing - buffer size {}".format(self.transport.get_write_buffer_size()))

            def resume_writing(self):
                _LOGGER.debug("[RS] Resume writing - buffer size {}".format(self.transport.get_write_buffer_size()))

        # Opens a non RFC2217 TCP/IP socket for serial
        _LOGGER.debug("[RS] Opening serial port")        
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = await serial_asyncio.create_serial_connection(loop, Protocol, self.port)

    async def async_read_dcbs(self, tstats_conf):
        """
        Read all DCBs in one shot via the eth:serial adapter, and store in self array
        """
        buf = []
        _LOGGER.debug("[RS] UH1 refreshing all DCBs data")
        await self.async_open_conn(buf)
        _LOGGER.debug("[RS] async_read_dcbs port: transport, protocol = {}, {}".format(self.transport, self.protocol))
        self.dcb_dict.clear()

        for tstat in tstats_conf:
            buf.clear()
            tstat_id = tstat['id']
            payload = 0  # Since reading - payload is length of bytes to write
            dcb_addr_lo = 0
            dcb_addr_hi = 0
            length_lo = 0xff  # Since reading full DCB
            length_hi = 0xff
            msg = [tstat_id, 10+payload, MASTER_ADDR, READ, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]
            crc = CRC16()
            msg = msg + crc.run(msg)
            string = bytes(msg)

            _LOGGER.debug("[RS] Writing bytes: {}".format(msg))
            self.transport.write(string)   # Write a string to trigger tsat to send back a DCB (64bytes since in 5/2 mode)
            await asyncio.sleep(0.3)       # Sleep to have chance to read array with protocol callback function

            crc_r = buf[len(buf)-2 : ]
            dcb = buf[9:len(buf)-2]
            _LOGGER.debug("[RS] Buffer = {}".format(buf))
            _LOGGER.debug("[RS] DCB = {}".format(dcb))
            _LOGGER.debug("[RS] CRC check Read:Computed = {}:{}".format(crc_r, crc.run(buf[:len(buf)-2])))  
            """ TODO: Check why CRC not matching  """
            self.dcb_dict[tstat_id] = dcb

        _LOGGER.debug("[RS] DCB dict = {}".format(self.dcb_dict))
        _LOGGER.debug("[RS] Closing serial port")        
        self.transport.close()          # Close the port
        return True

    async def async_write_bytes(self, tstat_id, dcb_addr, datal):
        msg = ""        
        read_buf = []
        payload = len(datal)  # Since writing - payload is length of bytes to write
        _LOGGER.debug("[RS] Writing num bytes: {} to tstatid={}, {}".format(payload,tstat_id,datal))

        dcb_addr_lo = dcb_addr & BYTEMASK
        dcb_addr_hi = (dcb_addr>>8) & BYTEMASK
        length_lo = payload  # Since reading less than 256 bytes
        length_hi = 0
        
        msg = [tstat_id, 10+payload, MASTER_ADDR, WRITE, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]
        msg=msg+datal
        
        crc = CRC16()
        msg = msg + crc.run(msg)

        await self.async_open_conn(read_buf)
        _LOGGER.debug("[RS] async_write_bytes port: transport, protocol = {}, {}".format(self.transport, self.protocol))
        self.transport.write(bytes(msg))

        await asyncio.sleep(0.2)    # Allow for readback of data response
        _LOGGER.debug("[RS] Write response buffer = {}".format(read_buf))

        _LOGGER.debug("[RS] Closing serial port")                
        self.transport.close()          # Close the port

    def get_thermostat(self, id_number, room):
        """
        Get a thermostat object by id number (just used to test connection)
        :param id_number: The ID of the desired thermostat (1-8 on a single UH1)
        """
        return (HeatmiserThermostat(id_number, room, self))

    def __del__(self):
        _LOGGER.info("[RS] UH1_com __del__ called, nothing to do...")

class HeatmiserThermostat(object):
    """Initialises a heatmiser thermostat, by taking an address and model."""
    def __init__(self, id_num, room, uh1):
        _LOGGER.debug("[RS] HeatmiserThermostat __init__ called with id, name {},{}".format(id_num, room))
        self.tstat_id = id_num
        self.dcb = None   # Dummy array of correct type
        self.room = room
        self.uh1_com = uh1
        self.target_temp = None
        
    def refresh_dcb(self):
        _LOGGER.debug("[RS] HeatmiserThermostat refresh_dcb called for tstat {}".format(self.tstat_id))
        self.dcb = self.uh1_com.dcb_dict[self.tstat_id]
        _LOGGER.debug("[RS] DCB contents {}".format(self.dcb))
        _LOGGER.debug("[RS] DCB contents (length): {}   ({})".format(self.dcb,len(self.dcb)))
        self.model = self.dcb[MODEL_ADDR] 

    def get_tstat_id(self):
        return self.tstat_id
    
    def get_room(self):
        return self.room

    def get_model(self):
        if self.dcb == None:
            return PRT
        return self.dcb[MODEL_ADDR]

    def get_target_temp(self):
        if self.dcb == None:
            return DUMMY_TEMP
        return self.dcb[TARGET_ADDR]

    def set_target_temp(self, temperature):
        """
        Updates the set taregt temperature and then 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_target_temp called")

        if 35 < temperature < 5:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (5-35)")
        else:
            datal = [temperature]
            self.uh1_com.write_bytes(self.tstat_id, TARGET_ADDR, datal)
 
    def get_away_temp(self):
        if self.dcb == None:
            return DUMMY_TEMP
        return self.dcb[AWAYTEMP_ADDR]

    ### TODO Fix make async but dont think I use this in HA  
    def set_away_temp(self, temperature):
        """
        Updates the Away temperature 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_away_temp called")

        if 17 < temperature < 7:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (7-17)")
        else:
            datal = [temperature]
            self.uh1_com.write_bytes(self.tstat_id, AWAYTEMP_ADDR, datal)
 
    def get_heat_status(self):
        if self.dcb == None:
            return OFF
        return self.dcb[HEAT_ADDR]

    def get_run_mode(self):
        if self.dcb == None:
            return HEAT_MODE
        return self.dcb[RUNMODE_ADDR]

    def set_run_mode(self, heat_away):
        """
        Updates the set run_mode HEAT_MODE=0 (deafult) AWAY=1 (aka frost protect)
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_run_mode called with {}".format(heat_away))

        datal = [heat_away]
        self.uh1_com.write_bytes(self.tstat_id, RUNMODE_ADDR, datal)
        
    #def get_heat_state(self):
        #return int.from_bytes(self.dcb[RUNMODE_ADDR+9],'little')

    def get_room_temp(self):
        if self.dcb == None:
            return DUMMY_TEMP
        msb = self.dcb[ROOMTEMP_ADDR]<<8
        lsb = self.dcb[ROOMTEMP_ADDR+1]
        return ((msb+lsb)/10)

    def get_hotwater_status(self):
        if self.dcb == None:
            return OFF
        if self.get_model() == PRTHW:
            _LOGGER.debug("[RS] HeatmiserThermostat support HW - read status")
            return self.dcb[DHW_ADDR]
        else:
            return (0)

    def set_hotwater_state(self, onoff):
        """
        Sets the HW state - NOTE:  0=TIMER,  ON=1,  FORCE OFF=2
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_hotwater_state called with {}".format(onoff))

        if self.get_model() != PRTHW:
            _LOGGER.error("[RS] Refusing to set hot-water as incorrect thermo model")
        else:
            datal = [onoff]
            self.uh1_com.write_bytes(self.tstat_id, DHW_ADDRW, datal)

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
        await self.uh1_com.async_write_bytes(self.tstat_id, DAYTIME_ADDRW, datal)

    def get_heat_schedule(self, weekend):
        """
        NOTE:  not using the self data array but reading direct from thermo
        """
        if self.dcb == None:
            return None
        if (weekend == WEEKEND):
            dcb_addr = WEEKEND_ADDR
        else:
            dcb_addr = WEEKDAY_ADDR
        if self.get_model() == PRTHW:
            dcb_addr += 1

        data_array = self.dcb[dcb_addr : dcb_addr+12] #read 12 bytes
        return data_array

    def get_dhw_schedule(self, weekend):
        """
        NOTE:  not using the self data array but reading direct from thermo
        """
        if self.dcb == None:
            return None
        if self.get_model() != PRTHW:
            return None
        if (weekend == WEEKEND):
            dcb_addr = WEEKEND_DHW_ADDR
        else:
            dcb_addr = WEEKDAY_DHW_ADDR

        data_array = self.dcb[dcb_addr : dcb_addr+16]   #read 16 bytes for 4 on/offs
        return data_array

    def set_heat_schedule(self, weekend, sched_array):
        """
        not using the self data array but setting direct to thermo
        NOTE: CAN ONLY USE 30 Minute intervals to program 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_schedule called (Heating)")
        if (weekend == WEEKEND):
            dcb_addr = WEEKEND_ADDRW
        else:
            dcb_addr = WEEKDAY_ADDRW

        _LOGGER.info("[RS] set_heat_schedule called with tsatid={}, DCB={}, {}".format(self.tstat_id, dcb_addr, sched_array))
        self.uh1_com.write_bytes(self.tstat_id, dcb_addr, sched_array)

    def set_dhw_schedule(self, weekend, sched_array):
        """
        NOTE:  not using the self data array but setting direct to thermo
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_dhw_schedule called (Hot water)")
        if (weekend == WEEKEND):
            dcb_addr = WEEKEND_DHW_ADDRW
        else:
            dcb_addr = WEEKDAY_DHW_ADDRW

        self.uh1_com.write_bytes(self.tstat_id, dcb_addr, sched_array)

    def get_holiday(self):
        if self.dcb == None:
            return None
        msb = self.dcb[HOLIDAYLEN_ADDR]<<8
        lsb = self.dcb[HOLIDAYLEN_ADDR+1]
        return (msb+lsb)

    async def async_set_holiday(self, hours=HOLIDAY_HOURS_MAX):
        """
        Assume we jam holiday to max 1008 hrs (42 days) (note it swaps to read)  
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_holiday called with {} hours".format(hours))

        lo = hours & 255
        hi = int (hours/256)
        datal = [lo, hi]
        _LOGGER.info("[RS] Setting holiday with following data bytes {}".format(datal))
        await self.uh1_com.async_write_bytes(self.tstat_id, HOLIDAYLEN_ADDR, datal)

#
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