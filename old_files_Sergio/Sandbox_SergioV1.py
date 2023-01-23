import logging
from OpenCEM import cem_lib_loggers
from sgr_library.modbusRTU_interface import SgrModbusRtuInterface
from sgr_library.generic_interface import GenericInterface
import time

cem_lib_loggers.create_debug_logger()
#cem_lib_loggers.create_event_logger()
cem_lib_loggers.show_logger_in_console(20)

ABBMeterUni = GenericInterface("xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_edited_S.Ferreira.xml")
ABBMeterBI = GenericInterface("xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_edited_S.Ferreira_Bi.xml")

SensorList = [ABBMeterUni, ABBMeterBI]

logging.info("OpenCEM initialisation finished")


for x in range(1000):
    print(f"Iteration: {x + 1}")

    for SensorNr, powerSensor in enumerate(SensorList):
        try:
            ActivePowerACtot = powerSensor.getval('ActivePowerAC', 'ActivePowerACtot')
            print(f"ActivePowerACtot Sensor {SensorNr} : {ActivePowerACtot}")
            time.sleep(0.1)
        except Exception as e:
            logging.warning(f"Exception has occurred on Sensor {SensorNr}, retrying")

            RetrySuccessful = False
            for j in range(3):
                try:
                    ActivePowerACtot = powerSensor.getval('ActivePowerAC', 'ActivePowerACtot')
                    print(f"ActivePowerACtot Sensor {SensorNr} : {ActivePowerACtot}")
                    logging.info(f"Retry {j+1} was successful")
                    RetrySuccessful = True
                    break  # will break retrying when getval was successful
                except:
                    logging.warning(f"Retry {j+1} failed")
                    time.sleep(0.5)  # waits 0.5s for next try

            if not RetrySuccessful:  # If retrying failed
                logging.error(f"Connection lost to Sensor {SensorNr}")

    time.sleep(2)

SgrModbusRtuInterface.globalModbusRTUClient.client.close()
logging.info("connection closed and finished")
