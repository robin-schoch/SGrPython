"""
Author: Sergio Ferreira

This script is the final communication testing script of the P5. It tests the communication with following devices:
over RTU ABB B23 112-100, ABB B23 312-100
over local Network: Shelly Pro 2PM, Shelly Pro 4PM, Shelly 3EM, Shelly H&T

One ABB Powermeter gets initialized with SmartGridready and the other one with the name ABB B23 312-100.

The test stops after the timer is finished or if a device looses connection for more than 5 consecutive requests.
"""
import logging
import time
from datetime import datetime, timedelta

from OpenCEM.cem_lib_loggers import create_event_logger, create_statistics_logger, show_logger_in_console
from OpenCEM.cem_lib_components import power_sensor, OpenCEM_RTU_client, shelly_temp_and_hum_sensor, \
    shelly_relais_actuator, shelly_power_sensor
from sgr_library.modbusRTU_interface import SgrModbusRtuInterface

# initialize loggers

create_event_logger()
create_statistics_logger()
# create_debug_logger() # debug-logger not needed
show_logger_in_console(20)  # activate logs in console with level 20 and above (INFO Level)

# initialize power sensors
# IMPORTANT! If a SmartGridready device with RTU exists, always initialize that one first.
# After that non SmartGridready devices can be initialized with the existing client from the SmartGridready device.
# the SmartGridready way with XML-FILE
AbbUni = power_sensor(is_smartgridready=True, id=1, has_energy_import=True, has_energy_export=False,
                      XML_file="xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_Uni.xml")

# Get the RTU client from the first power sensor.
RTU_global_client = OpenCEM_RTU_client(global_client=AbbUni.get_pymodbus_client()).get_OpenCEM_global_RTU_client()
# create RTU client when no SmartGridready device exists with the following command
# RTU_global_client = OpenCEM_RTU_client().get_OpenCEM_global_RTU_client()

# initialize the manual way with existing global RTU client
# ABB B23 312-100 modbus registers are saved in cem_lib_components and get added automatically if the name matches
AbbBi = power_sensor(is_smartgridready=False, id=2, has_energy_import=True, has_energy_export=True, name="ABB B23 312-100",
                     manufacturer="ABB", bus_type="RTU", client=RTU_global_client)

# It is possible to add modbus registry addresses manually like this:
# AbbBi.add_RTU_Power_entry(23316, 2, "WATTS", "int32", 0.01)
# AbbBi.add_RTU_EnergyImport_entry(20480, 4, "KILOWATT_HOURS", "int64_u", 0.01)
# AbbBi.add_RTU_EnergyExport_entry(20484, 4, "KILOWATT_HOURS", "int64_u", 0.01)

# initialize Shelly 3EM power sensor
Shelly3EM = shelly_power_sensor("192.168.1.113")

# add power sensors to a list
power_sensor_List = [AbbUni, AbbBi, Shelly3EM]

# initialize temp sensor and relays
# temperatur sensor
Temp_sensor = shelly_temp_and_hum_sensor("701f93")

# Shelly relay local initialisation, example for over cloud is in file Shelly_devices_demo.py
Shelly2PM = shelly_relais_actuator("192.168.1.112", 2, name="2PM")  # ip, number of channels
Shelly4PM = shelly_relais_actuator("192.168.1.114", 4, name="4PM")

logging.info("OpenCEM initialisation finished")

# input test config
testDurationMin = int(input("How long do you want to test? [minutes]"))
end_time = datetime.now() + timedelta(minutes=testDurationMin)
interval = int(input("what's the time between request? [seconds]"))
slower_loop_interval = int(input("what's the loop time for the slower loop? [seconds]"))
# log test config
logging.info(f"communication test for {testDurationMin} min.")
logging.info(f"power_value request intervall is {interval} sec.")
logging.info(f"slower_loop_interval intervall is {slower_loop_interval} sec.")

# some variables
iteration = 0
break_out_flag = False
RetrySuccessful_power = True
RetrySuccessful2 = True
min_end_time = datetime.now()

# main loop
while end_time > datetime.now():
    logging.info(f"Iteration: {iteration + 1}")

    for i, powerSensor in enumerate(power_sensor_List):

        # get power values from all the power sensors
        try:
            power_value, unit, error_code = powerSensor.read_power()
            print(f"{powerSensor.name} {powerSensor.id}: {power_value} {unit}")
            powerSensor.exception_counter = 0  # reset exception counter after successful request
        except Exception or AttributeError as e:
            powerSensor.exception_counter = powerSensor.exception_counter + 1
            logging.warning(
                f"Exception has occurred on Sensor with id {powerSensor.id}, retrying. Exception counter: {powerSensor.exception_counter}")
            # take last value #TODO does not work yet. will get fixed with error handling next semester
            power_value, unit, error_code = powerSensor.power_value, "KILOWATT", 1  # Error_code 1 = took last value

            # to many exception on a sensor, probably lost connection
            if powerSensor.exception_counter > 5:
                logging.error(f"Connection lost to Sensor {powerSensor.id}, -> while loop abort!")
                break_out_flag = True   # the main loop will stop if break_out_flag is true

    # slower loop
    if min_end_time < datetime.now():

        # get all energy values from all the power senors
        for i, powerSensor in enumerate(power_sensor_List):
            try:
                if powerSensor.has_energy_import:
                    energy_value_import, unit, error_code = powerSensor.read_energy_import()
                    print(f"{powerSensor.name} {powerSensor.id} Energy import: {energy_value_import} {unit}")
                if powerSensor.has_energy_export:
                    energy_value_import, unit, error_code = powerSensor.read_energy_export()
                    print(f"{powerSensor.name} {powerSensor.id} Energy export: {energy_value_import} {unit}")
                powerSensor.exception_counter = 0  # reset exception counter after successful requests

            except Exception or AttributeError as e:
                powerSensor.exception_counter = powerSensor.exception_counter + 1
                logging.warning(
                    f"Exception has occurred on Sensor with id {powerSensor.id}, retrying. Exception counter: {powerSensor.exception_counter}")

            if powerSensor.exception_counter > 5:
                logging.error(f"Connection lost to Sensor {powerSensor.id}, -> while loop abort!")
                break_out_flag = True

        # read the temperature
        temperature, timestamp, is_valid = Temp_sensor.read_temperature()
        print(f"Measured temperature {temperature} Celsius")
        # switches relay channel once a min
        relay_state = Shelly2PM.read_channel(1)
        if relay_state is True:
            Shelly2PM.write_channel(1, "off")
            Shelly4PM.write_channel(0, "on")
            Shelly4PM.read_channel(0)
        else:
            Shelly2PM.write_channel(1, "on")
            Shelly2PM.read_channel(1)
            Shelly4PM.write_channel(0, "off")
            Shelly4PM.read_channel(0)

        # read relay channel states
        print(f"Shelly 2PM channel 1 state: {Shelly2PM.read_channel(1)}")
        print(f"Shelly 4PM channel 0 state: {Shelly4PM.read_channel(0)}")

        # reset timer for slower loop
        min_end_time = datetime.now() + timedelta(seconds=slower_loop_interval)

    if break_out_flag:
        break  # will break the while loop
    iteration = iteration + 1
    time.sleep(interval)

# close connections
SgrModbusRtuInterface.globalModbusRTUClient.client.close()
logging.info("connection closed and test finished")
