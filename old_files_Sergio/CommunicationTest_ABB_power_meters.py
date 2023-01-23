"""
First test for communication with ABB B23 power meters over Modbus RTU. Some methods used in this code are depreciated.
"""
import logging
from OpenCEM import cem_lib_loggers
from sgr_library.modbusRTU_interface import SgrModbusRtuInterface
import time
from datetime import datetime, timedelta
from OpenCEM.cem_lib_loggers import Log_power_sensor_values
from OpenCEM.cem_lib_components import power_sensor


#cem_lib_loggers.create_debug_logger()
cem_lib_loggers.create_event_logger()
csvLogger = cem_lib_loggers.create_statistics_logger()
cem_lib_loggers.show_logger_in_console(20)

ABBMeterUni = power_sensor(is_smartgridready=True, id=1, has_energy=True, XML_file="../xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_Uni.xml")
ABBMeterBI = power_sensor(is_smartgridready=True, id=2, has_energy=True, XML_file="../xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_Bi.xml")

SensorList = [ABBMeterUni, ABBMeterBI]

logging.info("OpenCEM initialisation finished")

testDurationMin = int(input("How long do you want to test? [minutes]"))
end_time = datetime.now() + timedelta(minutes=testDurationMin)
interval = int(input("what's the time between request? [seconds]"))

iteration = 0
break_out_flag = False


while end_time > datetime.now():
    logging.info(f"Iteration: {iteration + 1}")

    for SensorNr, powerSensorObj in enumerate(SensorList):
        try:
            Power, has_energy, EnergyImport, EnergyExport, error_code = powerSensorObj.read()
            print(f'Sensor{SensorNr}; Power {Power}; Import {EnergyImport}; Export {EnergyExport}')
            Log_power_sensor_values(csvLogger, "PowerSensor " + str(SensorNr), Power, EnergyImport, EnergyExport)
        except Exception as e:
            logging.warning(f"Exception has occurred on Sensor {SensorNr}, retrying")
            RetrySuccessful = False
            for j in range(5):
                try:
                    Power, has_energy, EnergyImport, EnergyExport, error_code = powerSensorObj.read()
                    logging.info(f"Retry {j + 1} was successful")
                    RetrySuccessful = True
                    print(f'Sensor{SensorNr}; Power {Power}; Import {EnergyImport}; Export {EnergyExport}')
                    Log_power_sensor_values(csvLogger, "PowerSensor " + str(SensorNr), Power, EnergyImport, EnergyExport)
                    break  # will break retrying when getval was successful
                except:
                    logging.warning(f"Retry {j + 1} failed")
                    time.sleep(0.5)  # waits 0.5s for next try

            if not RetrySuccessful:  # If retrying failed 5 times
                logging.error(f"Connection lost to Sensor {SensorNr}, -> while loop abort!")
                break_out_flag = True

    if break_out_flag:
        break  # will break the while loop
    iteration = iteration + 1
    time.sleep(interval)

SgrModbusRtuInterface.globalModbusRTUClient.client.close()
logging.info("connection closed and finished")
