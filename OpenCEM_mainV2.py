# Generative AI was used for some Code
"""
This File runs the OpenCEM main function
"""


# Imports
import asyncio
import logging
import urllib

import aiohttp
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
import subprocess
import OpenCEM.cem_lib_components
import yaml

from OpenCEM.cem_lib_components import PowerSensor, ShellyPowerSensor, ShellyTempSensor, \
    ShellyTrvTempSensor, ShellyRelais, CentralPowerMeter, PvPlant, HeatPump, EvCharger, \
    HouseholdAppliance, PowerToHeat,RemainingConsumption
from OpenCEM.cem_lib_controllers import ExcessController, DynamicExcessController, PriceController, \
    update_global_controller_values, Controller, StepwiseExcessController, coverage_controller
from OpenCEM.cem_lib_loggers import create_statistics_logger_devices, create_event_logger, show_logger_in_console
from datetime import datetime, timedelta
from OpenCEM.cem_lib_auxiliary_functions import create_webpage_dict, send_data_to_webpage, parse_yaml, check_OpenCEM_shutdown
from sgr_library.modbusRTU_interface_async import SgrModbusRtuInterface


# devices loop
async def calculation_loop(devices: list, period_fast: int, period_slow: int, HTTP_client):
    OpenCEM_speed_up_factor = OpenCEM.cem_lib_components.OpenCEM_speed_up_factor
    time_slow_loop = datetime.now() + timedelta(seconds=period_slow / OpenCEM_speed_up_factor)
    do_slow_loop = True
    while True:

        if datetime.now() > time_slow_loop:
            time_slow_loop = datetime.now() + timedelta(seconds=period_slow / OpenCEM_speed_up_factor)  # reset time
            do_slow_loop = True

        for index, device in enumerate(devices):
            if isinstance(device, RemainingConsumption):
                continue
            response = await device.read_power_sensor()
            error_code = response[3]


            if do_slow_loop and isinstance(device, (HeatPump, PowerToHeat)):  # read aux sensors for these device types
                await device.read_aux_sensors()

        do_slow_loop = False  # reset variable

        update_global_controller_values(devices)  # calculates total consumption and production

        for index, device in enumerate(devices):
            if device.controller is not None:
                await device.calc_controller()
            device.log_values()

        # log global values (eg. total consumption)
        Controller.log_global_power_values()

        # update webpage
        webpage_dict = create_webpage_dict(devices)
        await send_data_to_webpage(webpage_dict, HTTP_client)

        # reset reserved power before the next iteration
        Controller.global_power_reserved = 0
        await asyncio.sleep(period_fast / OpenCEM_speed_up_factor)  # repeat loop every (period_fast) seconds

        # check if a restart is requested
        restart_requested = await check_OpenCEM_shutdown(HTTP_client)
        if restart_requested:
            print("OpenCEM is restarting soon")
            return


async def start_simulations(device_list: list):
    for device in device_list:
        if device.simulated:
            device.simulation_task = asyncio.create_task(device.simulate_device())


async def main():

    # load OpenCEM settings
    with open("yaml/OpenCEM_settings.yaml", "r") as f:
        settings = yaml.safe_load(f)
        OpenCEM_speed_up = settings.get("OpenCEM_speed_up")
        fast_loop_time = settings.get("fast_loop_time")
        slow_loop_time = settings.get("slow_loop_time")
        simulation_loop_time = settings.get("simulation_loop_time")
        duration = settings.get("duration")
        log_events = settings.get("log_events")
        log_stats = settings.get("log_stats")
        console_logging_level = settings.get("console_logging_level")
        installation = settings.get("installation")
        password = settings.get("password")
        token = settings.get("token")
        backend_url = settings.get("backend_url")
        path_OpenCEM_config = settings.get("path_OpenCEM_config")

    # set variables for the library
    OpenCEM.cem_lib_components.OpenCEM_speed_up_factor = OpenCEM_speed_up
    OpenCEM.cem_lib_components.simulation_loop_time = simulation_loop_time

    # start logging
    if log_stats:
        create_statistics_logger_devices()
    if log_events:
        create_event_logger()
    if console_logging_level >= 0:
        show_logger_in_console(console_logging_level)
    logging.info("OpenCEM started")

    # start GUI webserver
    gui_subprocess = subprocess.Popen(["venv/Scripts/python", "GUI_server.py"])  # Important!!! for Windows venv/Scripts/python, Linux myenv/bin/python
    await asyncio.sleep(2)    # wait 2 seconds so that the GUI is ready

    # load OpenCEM YAML configuration if available
    if path_OpenCEM_config is None or path_OpenCEM_config == "":
        url = backend_url + "/installations/" + installation + "/configuration?token=" + urllib.parse.quote_plus(token)
        async with aiohttp.request('GET', url) as response:
            status_code = response.status
            yaml_text = await response.text()

        if status_code == 200:
            try:
                with open("yaml/openCEM_config.yaml", "w") as f:
                    yaml.dump(yaml.safe_load(yaml_text), f, sort_keys=False)
                    path_OpenCEM_config = "yaml/openCEM_config.yaml"
                    logging.info("Downloaded YAML configuration successfully.")
            except EnvironmentError:
                logging.error("Error with writing downloaded YAML to disk")
        else:
            logging.warning(
                "YAML could not be downloaded from the server. Check installation nr., backend url and token.")
            gui_subprocess.terminate()  # close GUI subprocess
            logging.info("GUI closed, OpenCEM stopped due to error with downloading configuration YAML.")
            return  # OpenCEM gets stopped

    # parse yaml
    communication_channels_list, actuators_list, sensors_list, controllers_list, devices_list = await parse_yaml(path_OpenCEM_config)
    http_main_channel = next((obj for obj in communication_channels_list if obj.type == "HTTP_MAIN"),
                             None)  # returns the HTTP_MAIN from the list
    http_main_client = http_main_channel.client     # gets the main client from the communicationChannel

    # start pymodbus clients
    for channel in communication_channels_list:
        if channel.type in ["MODBUS_TCP", "MODBUS_RTU"]:
            await channel.client.connect()

    # start calculation loop
    await start_simulations(devices_list)
    task_calculation_loop = asyncio.create_task(
        calculation_loop(devices_list, fast_loop_time, slow_loop_time, http_main_client))

    # run main for given duration
    if duration != 0:
        await asyncio.sleep(duration)
        task_calculation_loop.cancel()
    # if no duration is given OpenCEM will run till stopped through the GUI
    else:
        await task_calculation_loop

    # stop programm
    task_calculation_loop.cancel()
    for device in devices_list:
        if device.simulated:
            device.simulation_task.cancel()

    # close running communication clients
    for obj in communication_channels_list:
        if obj.client is not None:
            if isinstance(obj.client, aiohttp.ClientSession):
                await obj.client.close()
            else:
                obj.client.close()

    gui_subprocess.terminate()
    logging.info("GUI closed, OpenCEM stopped")

# to run infinite don't set duration
asyncio.run(main())
