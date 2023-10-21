#
# Rob Saunders 2020
# Assume Python 3.10.x +
# My version to do a more atomic reading of the stats


import asyncio
import serial
import logging

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

    async def async_set_target_temp(self, temperature):
        """
        Updates the set taregt temperature and then 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_target_temp called")

        if 35 < temperature < 5:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (5-35)")
        else:
            datal = [temperature]
            await self.uh1_com.async_write_bytes(self.tstat_id, TARGET_ADDR, datal)
 
    def get_away_temp(self):
        if self.dcb == None:
            return DUMMY_TEMP
        return self.dcb[AWAYTEMP_ADDR]

    ### TODO Fix make async but dont think I use this in HA  
    async def async_set_away_temp(self, temperature):
        """
        Updates the Away temperature 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_away_temp called")

        if 17 < temperature < 7:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (7-17)")
        else:
            datal = [temperature]
            await self.uh1_com.async_write_bytes(self.tstat_id, AWAYTEMP_ADDR, datal)
 
    def get_heat_status(self):
        if self.dcb == None:
            return OFF
        return self.dcb[HEAT_ADDR]

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
        await self.uh1_com.async_write_bytes(self.tstat_id, RUNMODE_ADDR, datal)
        
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

    async def async_set_hotwater_state(self, onoff):
        """
        Sets the HW state - NOTE:  0=TIMER,  ON=1,  FORCE OFF=2
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_hotwater_state called with {}".format(onoff))

        if self.get_model() != PRTHW:
            _LOGGER.error("[RS] Refusing to set hot-water as incorrect thermo model")
        else:
            datal = [onoff]
            await self.uh1_com.async_write_bytes(self.tstat_id, DHW_ADDRW, datal)

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

    async def async_set_heat_schedule(self, weekend, sched_array):
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
        await self.uh1_com.async_write_bytes(self.tstat_id, dcb_addr, sched_array)

    async def async_set_dhw_schedule(self, weekend, sched_array):
        """
        NOTE:  not using the self data array but setting direct to thermo
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_dhw_schedule called (Hot water)")
        if (weekend == WEEKEND):
            dcb_addr = WEEKEND_DHW_ADDRW
        else:
            dcb_addr = WEEKDAY_DHW_ADDRW

        await self.uh1_com.async_write_bytes(self.tstat_id, dcb_addr, sched_array)

    def get_holiday(self):
        if self.dcb == None:
            return None
        msb = self.dcb[HOLIDAYLEN_ADDR]>>8
        lsb = self.dcb[HOLIDAYLEN_ADDR+1]
        return (msb+lsb)

    async def async_set_holiday(self, hours):
        """
        Jam holiday to max 1008 hrs (42 days) (note it swaps to read)  
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_holiday called")

        lo = hours & 255
        hi = int (hours/256)
        datal = [lo, hi]
        _LOGGER.info("[RS] Wirting following data bytes {}".format(datal))
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

"""
UH1 connection to the Heatmiser system
"""
class UH1_com:
    def __init__(self, ipaddress, port):
        _LOGGER.debug("[RS] UH1 __init__ called")
        try:
            _LOGGER.debug("[RS] Opening socket to brdige")
            # Opens a non RFC2217 TCP/IP socket for serial
            serport = serial.serial_for_url("socket://" + ipaddress + ":" + port, timeout=1)
        except serial.serialutil.SerialException as serror:
            _LOGGER.error("[RS] Error opening TCP/IP serial: {}".format(serror))
        self.serport = serport
        _LOGGER.info("[RS] Serial port conn handle = {}".format(self.serport))
        self.dcb_dict = {}

    async def async_read_dcb(self, tstat_id):
        """ Send command frame to read entire DCB for tstat_id """
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
        string = bytes(msg)
        self.serport.write(string)   # Write a string to trigger tsat to send back a DCB

        """ Read 9 byte header and get length of DCB """
        read_bytes=[]
        HEADER_BYTES=9
        read_bytes = list(self.serport.read(HEADER_BYTES))
        _LOGGER.debug("[RS] Header bytes read = {}".format(read_bytes))
        dcb_bytes = read_bytes[HEADER_BYTES-2]
        _LOGGER.debug("[RS] Number of bytes in DCB = {}".format(dcb_bytes))

        """ Now we know DCB length, read remnainder (+2 for CRC) """
        read_bytes = read_bytes + list(self.serport.read(dcb_bytes+2))
        crc_r = read_bytes[len(read_bytes)-2 : ]
        del read_bytes[len(read_bytes)-2 : ]   # Remove CRC bytes
        dcb=read_bytes[9:]
        _LOGGER.debug("[RS] DCB read = {}".format(dcb))
        _LOGGER.debug("[RS] CRC check Read:Computed = {}:{}".format(crc_r, crc.run(read_bytes)))  
        """ TODO: Check why CRC not matching  """

        return(dcb)

    async def async_read_dcbs(self, tstats):
        if(self.serport.is_open==False):
            try:
                self.serport.open()
            except serial.SerialTimeoutException as serror:
                _LOGGER.error("[RS] Error openinng port: {}".format(serror))
                return None

        tstat_ids = [ t["id"] for t in tstats ]
        _LOGGER.debug("[RS] UH1 async_read_dcbs called - for TSTATs {}".format(tstat_ids))
        for t in tstat_ids:
            dcb = await self.async_read_dcb(t)
            if(dcb!=None):
                self.dcb_dict[t] = dcb

        def blocking_serport_close():
            self.serport.close()
        loop=asyncio.get_running_loop()
        await loop.run_in_executor(None, blocking_serport_close)

    async def async_write_bytes(self, tstat_id, dcb_addr, datal):
        if(self.serport.is_open==False):
            try:
                self.serport.open()
            except serial.SerialTimeoutException as serror:
                _LOGGER.error("[RS] Error openinng port: {}".format(serror))
                return None

        """ Construct and send the command frame """
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
        string = bytes(msg)
        _LOGGER.debug("[RS] Writing bytes: {}".format(msg))
        self.serport.write(string)   # Write a message (no reply)
        
        """ Read reply frame  """
        REPLY_BYTES=7
        read_bytes = list(self.serport.read(REPLY_BYTES))
        _LOGGER.debug("[RS] Response bytes read = {}".format(read_bytes))
        
        def blocking_serport_close():
            self.serport.close()
        loop=asyncio.get_running_loop()
        await loop.run_in_executor(None, blocking_serport_close)
        return True

    def get_thermostat(self, id_number, room):
        """
        Get a thermostat object by id number (just used to test connection)
        :param id_number: The ID of the desired thermostat (1-8 on a single UH1)
        """
        return (HeatmiserThermostat(id_number, room, self))