#!/bin/python3
"""
 Tests the heatmiser DH1 connection - simulates home assisatnt but thrashes 
"""
import heatmiserRS as heatmiser
import time
import asyncio
import logging

from const import *
"""
Read all thermos and benchmark time taken
"""
HW_TIMER = 0
HW_F_ON = 1
HW_F_OFF = 2
HEAT_MODE = 0
AWAY = 1
WEEKEND = True
WEEKDAY = False

IP_ADDRESS='192.168.123.253'
PORT='5000'

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG)
delay=None
# Set-up port connection to heatmiser system
uh1 = heatmiser.UH1("socket://" + IP_ADDRESS + ":" + PORT)
loop = asyncio.get_event_loop()
if not loop.run_until_complete(uh1.async_open_connection()):
    print("Connection failed...  do retry action")
    exit(1)

"""
Benchmark getting all thermos data 
"""
while(True):
    tic = time.perf_counter()
    loop.run_until_complete(uh1.async_read_dcbs())

    for t in uh1.thermos:
        print ("===",t.get_name(),"===")
        print("Room temp:  ", t.get_room_temp() )
        print("Model:  ", t.get_model() )
        print("Target temp:  ", t.get_target_temp() )
        print("Heat status:  ", t.get_heat_status() )
        print("Run mode (Heat-mode=0, Away=1):  ", t.get_run_mode() )
        print("Away fallback temp:  ", t.get_away_temp() )
        print("Holiday mode hours:  ", t.get_holiday() )
        print("Hot-water:  ", t.get_hotwater_status() )
        print("Day (Mon=1, Sun=7)" , t.get_day())
        print("Time" , time.strftime('%H:%M:%S', time.gmtime(t.get_time())))
        print("Weekday sched: ",t.get_heat_schedule(WEEKDAY))
        print("Weekend sched: ",t.get_heat_schedule(WEEKEND))
        print("Weekday DHW sched: ",t.get_dhw_schedule(WEEKDAY))
        print("Weekend DHW sched: ",t.get_dhw_schedule(WEEKEND))
        print("Online status: ",t.online)
    
    print("**HUB status**: ",uh1.online)
    toc = time.perf_counter()
    print(f"Time taken: {toc - tic:0.4f} seconds")
    if delay != None:
        time.sleep(delay)
    else:
        key = input("[q]uit, [t]hrash, [w]rite command menu")
        if(key == 'q'):
            break
        elif(key== 'w'):
            key = input("[1] update datetime, [2] hol hours min, [3] hol hours max")
            
            if(key == '1'):
                """ Update datetime """
                async def async_write_thermo(t: heatmiser.Thermostat):
                    print ("===",t.get_name(),"===")
                    time2set=time.localtime()
                    day=time2set.tm_wday+1
                    hour=time2set.tm_hour
                    mins=time2set.tm_min
                    secs=time2set.tm_sec
                    print("Day:{}, Hour:{}, Mins:{}, Secs:{}".format(day,hour,mins,secs))
                    await t.async_set_daytime(day, hour, mins, secs)
                for t in uh1.thermos:
                    loop.run_until_complete(async_write_thermo(t))
            elif(key == '2'):
                """ Update to set to 0 holiday hours (i.e. home)"""
                async def async_write_thermo(t: heatmiser.Thermostat):
                    print ("===",t.get_name(),"===")
                    await t.async_set_holiday(0)
                for t in uh1.thermos:
                    asyncio.run(async_write_thermo(t))
                    time.sleep(0.3)

            elif(key == '3'):
                """ Update to set to max holiday hours (i.e. away)"""
                async def async_write_thermo(t: heatmiser.Thermostat):
                    print ("===",t.get_name(),"===")
                    await t.async_set_holiday(1008)
                for t in uh1.thermos:
                    asyncio.run(async_write_thermo(t))
                    time.sleep(0.3)
        elif(key == 't'):
            key = input("Enter thrash period in seconds...")
            delay = int(key)        