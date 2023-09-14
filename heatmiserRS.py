#
# Rob Saunders 2020
# Assume Python 3.7.x +
# My version to do a more atomic reading of the stats

import sys
import serial
import logging
import requests

BYTEMASK = 0xff
# Master address used (must be 129-160)
MASTER_ADDR = 0x81

READ=0
WRITE=1

HW_TIMER = 0
HW_F_ON = 1
HW_F_OFF = 2
HEAT_MODE = 0
AWAY = 1

WEEKDAY_ADDR=47
WEEKEND_ADDR=59

WEEKDAY_DHW_ADDR=71
WEEKEND_DHW_ADDR=87

_LOGGER = logging.getLogger(__name__)


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


class HeatmiserThermostat(object):
    """Initialises a heatmiser thermostat, by taking an address and model."""
    def __init__(self, id_num, uh1=None):
        _LOGGER.debug("[RS] HeatmiserThermostat __init__ called")
        self.address = id_num
        if(uh1 != None):
            self.uh1_conn = uh1
        self.room = None
        self.model = BYTEMASK    # 2,3 =PRT, 4 =PRT-HW
        self.target_temp = None
        self.heat_status = None
        self.run_mode = None
        self.away_temp = None
        self.hw_status = None
        self.room_temp = None
        self.day = None
        self.time = None
        
        self.refresh_data()
        
    def read_bytes(self, dcb_addr, num_bytes):
        tstat_id = self.address
        payload = 0  # Since reading - payload is length of bytes to write
        dcb_addr_lo = dcb_addr & BYTEMASK
        dcb_addr_hi = (dcb_addr>>8) & BYTEMASK
        length_lo = num_bytes  # Since reading less than 256 bytes
        length_hi = 0
        msg = [tstat_id, 10+payload, MASTER_ADDR, READ, dcb_addr_lo, dcb_addr_hi, length_lo, length_hi]
#        print ("Sent", msg)

        crc = CRC16()
        msg = msg + crc.run(msg)
#        print ("Sent+CRC", msg)
        
        string = bytes(msg)
        try:
            self.uh1_conn.serport.write(string)   # Write a string to trigger tsat to send back a DCB
        except serial.SerialTimeoutException:
            _LOGGER.error("[RS] Write timeout error: {}".format(serror))
            return False
        
        byteread = self.uh1_conn.serport.read(11+num_bytes) 
        datal = list(byteread)

        ##  TODO:  Proper un-packing and CRC check
        del datal[0:9]    # Remove the header bytes
        del datal[num_bytes:(num_bytes+2)]   # And the 16 bit CRC

        return datal   # and return the remainder bytes as a list
        
    def write_bytes(self, dcb_addr, datal):
        tstat_id = self.address
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
#       print ("String wirtten =", string)

        try:
            self.uh1_conn.serport.write(string)   # Write a message (no reply)
            return True
        except serial.SerialTimeoutException:
            _LOGGER.error("[RS] Write timeout error: {}".format(serror))
            return False              

    def refresh_data(self):
        _LOGGER.debug("[RS] HeatmiserThermostat refresh_data called")

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed - abort read")
        else:
            if self.model == BYTEMASK:
                self.model = self.read_bytes(4,1)[0]    # 2,3 =PRT, 4 =PRT-HW

            self.target_temp = self.read_bytes(18,1)[0]
            self.heat_status = self.read_bytes(41,1)[0]
            self.run_mode = self.read_bytes(23,1)[0]
            self.away_temp = self.read_bytes(17,1)[0]

            dataw = self.read_bytes(38,2)
            msb = dataw[0]<<8
            lsb = dataw[1]
            self.room_temp = (msb + lsb) / 10

            if self.model == 4:
                _LOGGER.debug("[RS] HeatmiserThermostat support HW - read status")
                self.hw_status = self.read_bytes(42,1)[0]
            else:
                self.hw_status = 0
        
            self.day = self.read_bytes(43,1)[0]
            datal=self.read_bytes(44,3)
            self.time = datal[0]*3600 + datal[1]*60 + datal[2] 
            
            datal=self.read_bytes(24,2)
            self.holiday = datal[0]*256+datal[1]

        self.uh1_conn.close_port()

    def get_model(self):
        return self.model

    def get_target_temp(self):
        return self.target_temp

    def set_target_temp(self, temperature):
        """
        Updates the set taregt temperature and then 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_target_temp called")

        if 35 < temperature < 5:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (5-35)")
        else:
            if self.uh1_conn.open_port() == False:
                _LOGGER.error("[RS] Port open failed - abort write")
            else:
                datal = [temperature]
                self.write_bytes(18, datal)
                self.target_temp = temperature
            self.uh1_conn.close_port()

    def get_away_temp(self):
        return self.away_temp

    def set_away_temp(self, temperature):
        """
        Updates the Away temperature 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_away_temp called")

        if 17 < temperature < 7:
            _LOGGER.error("[RS] Refusing to set temp outside of allowed range (7-17)")
        else:
            if self.uh1_conn.open_port() == False:
                _LOGGER.error("[RS] Port open failed - abort write")
            else:
                datal = [temperature]
                self.write_bytes(17, datal)
                self.away_temp = temperature
            self.uh1_conn.close_port()

    def get_heat_status(self):
        return self.heat_status

    def get_run_mode(self):
        return self.run_mode

    def set_run_mode(self, heat_away):
        """
        Updates the set run_mode HEAT_MODE=0 (deafult) AWAY=1 (aka frost protect)
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_run_mode called with {}".format(heat_away))

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed - abort write")
        else:
            datal = [heat_away]
            self.write_bytes(23, datal)  #Set away mode        
            self.run_mode = heat_away
            """ if heat_away == HEAT_MODE:
                self.set_holidy(0)           # Set holiday to 0 hours
            else:                            # then it must be away mode
                self.set_holidy(1008)        # Set holiday to 1008 hours to ensure HW stays off
            """            
            self.uh1_conn.close_port()

    def get_heat_state(self):
        return self.heat_state

    def get_room_temp(self):
        return self.room_temp

    def get_hotwater_status(self):
        return self.hw_status

    def set_hotwater_state(self, onoff):
        """
        Sets the HW state - NOTE:  0=TIMER,  ON=1,  FORCE OFF=2
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_hotwater_state called with {}".format(onoff))

        if self.model != 4:
            _LOGGER.error("[RS] Refusing to set hot-water as incorrect thermo model")
        else:
            if self.uh1_conn.open_port() == False:
                _LOGGER.error("[RS] Port open failed - abort write")
            else:
                datal = [onoff]
                self.write_bytes(42, datal)
            self.uh1_conn.close_port()

    def get_day(self):
        return self.day

    def get_time(self):
        return self.time

    def set_daytime(self, day, hour, mins, secs):
        """
        Update the day and time NOTE: have to do together as in the same funtion group (see Hetamiser v3 protocol doc)  
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_daytime called with tsatid={}, DD,HH,MM,SS={},{},{},{}".format(self.address, day,hour,mins,secs))

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed - abort read")
        else:
            datal = [day, hour, mins, secs]
            self.write_bytes(43, datal)
        self.uh1_conn.close_port()

    def get_heat_schedule(self, weekend):
        """
        NOTE:  not using the self data array but reading direct from thermo
        """
        if (weekend == True):
            dcb_addr = WEEKDAY_ADDR
        else:
            dcb_addr = WEEKEND_ADDR

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed in get_schedule - continue read")
        data_array = self.read_bytes(dcb_addr, 12) #read 12 bytes
        self.uh1_conn.close_port()
        return data_array

    def get_dhw_schedule(self, weekend):
        """
        NOTE:  not using the self data array but reading direct from thermo
        """
        if (weekend == True):
            dcb_addr = WEEKEND_DHW_ADDR
        else:
            dcb_addr = WEEKDAY_DHW_ADDR

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed in get_dhw_schedule - abort read")
        else:
            data_array = self.read_bytes(dcb_addr, 16) #read 16 bytes for 4 on/offs
        self.uh1_conn.close_port()
        return data_array

    def set_heat_schedule(self, weekend, sched_array):
        """
        not using the self data array but setting direct to thermo
        NOTE: CAN ONLY USE 30 Minute intervals to program 
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_schedule called (Heating)")
        if (weekend == True):
            dcb_addr = WEEKEND_ADDR
        else:
            dcb_addr = WEEKDAY_ADDR

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed in set_heat_schedule - continue write")
        _LOGGER.info("[RS] set_heat_schedule called with tsatid={}, DCB={}, {}".format(self.address, dcb_addr, sched_array))
        err_code = self.write_bytes(dcb_addr, sched_array) #write schedule array (12 bytes)
        self.uh1_conn.close_port()
        return err_code

    def set_dhw_schedule(self, weekend, sched_array):
        """
        NOTE:  not using the self data array but setting direct to thermo
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_dhw_schedule called (Hot water)")
        if (weekend == True):
            dcb_addr = WEEKEND_DHW_ADDR
        else:
            dcb_addr = WEEKDAY_DHW_ADDR

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed in set_dhw_schedule- continue write")
        err_code = self.write_bytes(dcb_addr, sched_array) #write schedule array (16 bytes)
        self.uh1_conn.close_port()
        return err_code


    def get_holiday(self):
        return self.holiday

    def set_holiday(self, hours):
        """
        Jam holiday to max 1008 hrs (42 days) (note it swaps to read)  
        """
        _LOGGER.info("[RS] HeatmiserThermostat set_holiday called")

        if self.uh1_conn.open_port() == False:
            _LOGGER.error("[RS] Port open failed - abort read")
        else:
            lo = hours & 255
            hi = int (hours/256)
            datal = [lo, hi]
            _LOGGER.info("[RS] Wirting following data bytes {}".format(datal))

            self.write_bytes(24, datal)
        self.uh1_conn.close_port()

class UH1(object):
    """
    UH1 connection to the Heatmiser system
    """
    def __init__(self, ipaddress, port):
        _LOGGER.info("[RS] UH1 __init__ called")
        self._host = ipaddress
        self._port = port
        self.serport = None

    def connect(self):
        if self.serport:
            _LOGGER.info("[RS] Using existing UH1 session")
            return

        try:
            _LOGGER.info("[RS] Opening socket to brdige")
            # Opens a non RFC2217 TCP/IP socket for serial
            serport = serial.serial_for_url("socket://" + self._host + ":" + self._port, timeout=1)
            # Close the port agin since defaults open and want to manually open
            serport.close() 
        except serial.serialutil.SerialException:
            _LOGGER.error("[RS] Error opening TCP/IP serial: {}".format(serror))
            raise Exception("Connection Error")   
        self.serport = serport
        _LOGGER.info("[RS] Conn handle = {}".format(self.serport))

    def get_thermostat(self, id_number):
        """
        Get a thermostat object by id number (just used to test connection)
        :param id_number: The ID of the desired thermostat (1-8 on a single UH1)
        """
        return (HeatmiserThermostat(id_number, self))
        
    def open_port(self):
        _LOGGER.debug("[RS] HeatmiserConn open_port called")
        _LOGGER.debug("[RS] Oppning Conn handle = {}".format(self.serport))
        
        if self.serport == None:
            _LOGGER.error("[RS] Soemthing wrong - no conn handel")
            return (False)

        if self.serport.is_open == True:
            _LOGGER.error("[RS] Serial port already open - abort read")
            return (False)
        else:
            _LOGGER.debug("[RS] Opening serial port.")
            self.serport.open()

        return (True)

    def close_port(self):
        _LOGGER.debug("[RS] close_port called, closing Conn = {}".format(self.serport))
        try:
            self.serport.close() 
        except serial.serialutil.SerialException:
            _LOGGER.error("[RS] Error closing serial: {}".format(serror))
            raise Exception("Connection Error")   
		
    def __del__(self):
        _LOGGER.info("[RS] __del__ called, closing Conn = {}".format(self.serport))
        try:
            self.serport.close() 
        except serial.serialutil.SerialException:
            _LOGGER.error("[RS] Error closing serial: {}".format(serror))
            raise Exception("Connection Error")   
         

