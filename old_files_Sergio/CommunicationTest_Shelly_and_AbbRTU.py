import logging
import time
from datetime import datetime, timedelta

from OpenCEM.cem_lib_loggers import create_event_logger, create_statistics_logger, show_logger_in_console
from OpenCEM.cem_lib_components import power_sensor, OpenCEM_RTU_client, shelly_temp_and_hum_sensor, \
    shelly_relais_actuator

# initialize loggers
from sgr_library.modbusRTU_interface import SgrModbusRtuInterface

"""this script tests the communication of the ABB power-meters, a shelly relay and a shelly temperature sensor."""
create_event_logger()
create_statistics_logger()
# create_debug_logger() # debug-logger not needed
show_logger_in_console(20)  # activate logs in console with level 20 and above (INFO Level)

# initialize power sensors
# IMPORTANT! If a SmartGridready device with RTU exists, always initialize that one first.
# After that non SmartGridready devices can be initialized with the existing client from the SmartGridready device.
# the SmartGridready way with XML-FILE
AbbUni = power_sensor(is_smartgridready=True, id=1, has_energy_import=True, has_energy_export=False, XML_file="../xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_Uni.xml")

# Get the RTU client from the first power sensor.
RTU_global_client = OpenCEM_RTU_client(global_client=AbbUni.get_pymodbus_client()).get_OpenCEM_global_RTU_client()
# create RTU client when no SmartGridready device exists with the following command
#RTU_global_client = OpenCEM_RTU_client().get_OpenCEM_global_RTU_client()

# initialize the manual way with existing global RTU client
AbbBi = power_sensor(is_smartgridready=False, id=2, has_energy_import=True, has_energy_export=True, name="B23 312-100", manufacturer="ABB", bus_type="RTU", client=RTU_global_client)

# add modbus registry addresses manually
AbbBi.add_RTU_Power_entry(23316, 2, "WATTS", "int32", 0.01)
AbbBi.add_RTU_EnergyImport_entry(20480, 4, "KILOWATT_HOURS", "int64_u", 0.01)
AbbBi.add_RTU_EnergyExport_entry(20484, 4, "KILOWATT_HOURS", "int64_u", 0.01)

# add power sensors to a list
power_sensor_List = [AbbUni, AbbBi]

# initialize Shelly devices
# temperatur sensor
Temp_sensor = shelly_temp_and_hum_sensor("701f93")

# Shelly relay local initialisation, example for over cloud is in file Shelly_devices_demo.py
Shelly_relais = shelly_relais_actuator("192.168.1.112", 2)

logging.info("OpenCEM initialisation finished")

# input test config
testDurationMin = int(input("How long do you want to test? [minutes]"))
end_time = datetime.now() + timedelta(minutes=testDurationMin)
interval = int(input("what's the time between request? [seconds]"))
# log test config
logging.info(f"communication test for {testDurationMin} min.")
logging.info(f"power_value request intervall is {interval} sec.")


iteration = 0
break_out_flag = False
RetrySuccessful_power = True
RetrySuccessful2 = True
min_end_time = datetime.now()

while end_time > datetime.now():
    logging.info(f"Iteration: {iteration + 1}")

    for i, powerSensor in enumerate(power_sensor_List):

        # get power values from all the power sensors
        try:
            print(powerSensor.read_power())
        except AttributeError as e:
            logging.warning(f"Exception has occurred on Sensor with id {powerSensor.id}, retrying")
            RetrySuccessful_power = False
            for j in range(5):
                try:
                    print(powerSensor.read_power())
                    logging.info(f"Retry {j + 1} was successful")
                    RetrySuccessful_power = True
                    break  # will break retrying when getval was successful
                except AttributeError as e:
                    logging.warning(f"Retry {j + 1} failed")
                    time.sleep(0.5)  # waits 0.5s for next try

            if not RetrySuccessful_power:  # If retrying failed 5 times
                logging.error(f"Connection lost to Sensor {powerSensor.id}, -> while loop abort!")
                break_out_flag = True

        # get energy values once a minute
    if min_end_time < datetime.now():
        for i, powerSensor in enumerate(power_sensor_List):
            try:
                if powerSensor.has_energy_import:
                    powerSensor.read_energy_import()
                if powerSensor.has_energy_export:
                    powerSensor.read_energy_export()
            except AttributeError as e:
                logging.warning(f"Exception has occurred on Sensor with id {powerSensor.id}, retrying")
                RetrySuccessful2 = False
                for j in range(5):
                    try:
                        if powerSensor.has_energy_import:
                            powerSensor.read_energy_import()
                        if powerSensor.has_energy_export:
                            powerSensor.read_energy_export()

                        logging.info(f"Retry {j + 1} was successful")
                        RetrySuccessful2 = True
                        break  # will break retrying when getval was successful
                    except AttributeError as e:
                        logging.warning(f"Retry {j + 1} failed")
                        time.sleep(0.2)  # waits 0.2s for next try

            if not RetrySuccessful2:  # If retrying failed 5 times
                logging.error(f"Connection lost to Sensor {powerSensor.id}, -> while loop abort!")
                break_out_flag = True

        # read the temperature
        temperature = Temp_sensor.read_temperature()

        # switches relay channel once a min
        relay_state = Shelly_relais.read_channel(1)
        if relay_state is True:
            Shelly_relais.write_channel(1, "off")
        else:
            Shelly_relais.write_channel(1, "on")

        # new one-minute timer
        min_end_time = datetime.now() + timedelta(minutes=1)

    if break_out_flag:
        break  # will break the while loop
    iteration = iteration + 1
    time.sleep(interval)


SgrModbusRtuInterface.globalModbusRTUClient.client.close()
logging.info("connection closed and test finished")
