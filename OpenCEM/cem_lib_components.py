# Generative AI was used for some Code

import asyncio
import logging
import math

import aiohttp
import time
from audioop import mul
from operator import truediv
from pprint import pprint
from pymodbus.constants import Endian

import OpenCEM.cem_lib_controllers as controllers
import random
import sys, os
from datetime import datetime, timedelta

# Smartgrid Ready Libraries
from sgr_library.generic_interface import GenericInterface

# pymodbus
from pymodbus.client import ModbusSerialClient, AsyncModbusTcpClient, AsyncModbusSerialClient

from sgr_library.modbusRTU_interface_async import SgrModbusRtuInterface
from sgr_library.payload_decoder import PayloadDecoder
from datetime import datetime

# Authentication Key and corresponding server for the Shelly Cloud
shelly_auth_key = "MTUyNjU5dWlk6D393AB193944CE2B1D84E0B573EAB1271DA6F2AF2BC54F67779F5BC27C31E90AD7C7075E0F813D8"
shelly_server_address = "https://shelly-54-eu.shelly.cloud/"

# Simulation parameters:
OpenCEM_speed_up_factor = 1  # will be overwritten by setting yaml
sim_start_time = None
simulation_loop_time = 1  # loop time in seconds for simulated devices, will be overwritten by setting yaml


class OpenCEM_RTU_client:
    """
    creates a global RTU Client for OpenCEM. There can only be one client globally.
    If there already exist a smartGridready, put it as keyword argument global_client = client.
    """
    OpenCEM_global_RTU_client = None

    def __init__(self, port: str = "COM5", baudrate: int = 19200, parity: str = "E", client_timeout: int = 1, *,
                 global_client=None):  # global_client:if there already exist a SmartGridready client it can be put here
        # if there does not exist a SmartGridready client
        if global_client is None:
            if OpenCEM_RTU_client.OpenCEM_global_RTU_client is None:
                self.client = ModbusSerialClient(method="rtu", port=port, parity=parity,
                                                 baudrate=baudrate, timeout=client_timeout)
                self.client.connect()
            else:
                self.client = OpenCEM_RTU_client.OpenCEM_global_RTU_client
        # if there is a smartGridReady client
        else:
            OpenCEM_RTU_client.OpenCEM_global_RTU_client = global_client
            self.client = global_client

    def get_OpenCEM_global_RTU_client(self):
        if self.client is not None:
            return self.client
        else:
            raise NotImplementedError


class SmartGridreadyComponent:
    # class for component with smartgridready compatibility

    def __init__(self, XML_file: str):

        interface_file = XML_file
        self.sgr_component = GenericInterface(interface_file)

    async def read_value(self, functional_profile: str, data_point: str):
        # read one value from a given data point within a functional profile
        error_code = 0
        data_point = self.sgr_component.find_dp(functional_profile, data_point)
        value = await self.sgr_component.getval(data_point)
        multiplicator = self.sgr_component.get_multiplicator(data_point)
        power_10 = self.sgr_component.get_power_10(data_point)
        unit = self.sgr_component.get_unit(data_point)

        if multiplicator > 0:
            return_value = value * 10 ** power_10 / multiplicator  # --- CHECK IF CORRECT ! ---
        else:
            return_value = value * 10 ** power_10

        return [return_value, unit, error_code]

    async def read_value_with_conversion(self, functional_profile: str, data_point: str):
        # read a power or energy value with unit conversion to kW, kWh

        [value, unit, error_code] = await self.read_value(functional_profile, data_point)
        if unit.upper() == 'W' or unit.upper() == 'WATT' or unit.upper() == 'WATTS':
            value = value / 1000  # convert W to kW
            unit = "KILOWATT"  # change output unit to kW
        if unit.upper() == 'WH' or unit.upper() == 'WATT HOURS' or unit.upper() == 'WATTHOURS' or unit.upper() == "WATT_HOURS":
            value = value / 1000  # convert Wh to kWh
            unit = "KILOWATT_HOURS"  # change output unit to kWh

        return [round(value, 4), unit, error_code]  # value gets rounded

    def write_value(self, functional_profile: str, data_point: str, value):
        # write one value to a given data point within a functional profile

        error_code = 0

        self.sgr_component.setval(functional_profile, data_point, value)

        return error_code

    def read_device_profile(self):
        # get basic info from device profile such as name, nominal power consumption, level of operation, etc.

        device_profile = self.sgr_component.get_device_profile()
        return [device_profile.brand_name, device_profile.nominal_power, device_profile.dev_levelof_operation]

    def read_device_information(self):
        name = self.sgr_component.get_device_name()
        manufacturer = self.sgr_component.get_manufacturer()
        bus_type = self.sgr_component.get_modbusInterfaceSelection()

        return name, manufacturer, bus_type


class Sensor():
    # base class for any sensor (e.g. power, temperature, etc.)
    def __init__(self, *, is_smartgridready: bool, id: str, name: str = "", manufacturer: str = "", bus_type: str = "",
                 client=None,
                 XML_file: str = "",
                 is_logging: bool = True,
                 OpenCEM_id: str = ""):  # is_smartgridready und id wird in jedem Fall gebraucht, der Rest ist optional
        # client has to be a ModbusSerialClient or an aiohttp.ClientSession

        # initialize sensor
        self.is_smartgridready = is_smartgridready
        self.sensor_type = 'any'  # ist der Sensortype irgendwo im XML ersichtlich
        self.is_logging = is_logging
        self.exception_counter = 0
        self.OpenCEM_id = OpenCEM_id

        # if smartgridready
        if self.is_smartgridready and XML_file != "":
            self.smartgridready = SmartGridreadyComponent(XML_file)  # add smartgridready component to sensor
            self.name, self.manufacturer, self.bus_type = self.smartgridready.read_device_information()  # gets the needed device information from the XML #TODO andere Informationen hinzufügen
            self.smartgridready.sgr_component.set_slave_id(id)
            self.id = id

        # if not smartgridready
        if not self.is_smartgridready:
            self.name = name
            self.manufacturer = manufacturer
            self.bus_type = bus_type
            self.id = id
            # create client for communication,possible values are RTU or REST
            if self.bus_type in ["SHELLY_LOCAL", "MODBUS_RTU", "MODBUS_TCP"] and client is not None:
                self.client = client
            elif self.bus_type in ["REST", "SHELLY_CLOUD"]:
                pass
                # Todo Überlegung was hier geschehen soll
            else:
                print("No client given or the given bus type does not exist in OpenCEM.")
                raise NotImplementedError
                # Todo Überlegung was hier geschehen soll

    def read(self):
        # --- add code for reading from hardware here
        raise NotImplementedError
        return [None, error_code]  # value = None

    def log_values(self):
        # abstract values
        raise NotImplementedError

    def get_pymodbus_client(self):
        """
        returns the pymodbus client, if the sensor is SmartGridReady
        """
        if self.is_smartgridready:
            return self.smartgridready.sgr_component.get_pymodbus_client()
        else:
            print("only available for SmartGridReady devices")


class PowerSensor(Sensor):
    # derived class for power sensor
    sleep_between_requests = 0.05  # Time the program will wait after a RTU request in seconds

    def __init__(self, *, is_smartgridready: bool, id, has_energy_import: bool, has_energy_export: bool,
                 name: str = "", manufacturer: str = "", bus_type: str = "", client=None, XML_file: str = "",
                 is_logging: bool = True, OpenCEM_id: str = ""):
        """
        :param is_smartgridready: set True if the device has an SmartGridReady XML_File
        :param id: the slave id of the sensor
        :param has_energy_import: set True if the sensor has energy_import information
        :param has_energy_export: set True if the sensor has energy_export information
        :param client: the client object which will handle the communication
        :param bus_type: possible bustypes are RTU or REST
        :param XML_file: path to the SmartGridReady XML_File
        """
        # initialize sensor
        super().__init__(is_smartgridready=is_smartgridready, id=id, name=name, manufacturer=manufacturer,
                         bus_type=bus_type, XML_file=XML_file, client=client, is_logging=is_logging,
                         OpenCEM_id=OpenCEM_id)

        self.has_energy_import = has_energy_import
        self.has_energy_export = has_energy_export
        self.sensor_type = 'power'
        self.power_value = 0
        self.energy_value_import = 0
        self.energy_value_export = 0
        # dicts are only used if not smartGridReady
        self.power_dict = None
        self.energy_import_dict = None
        self.energy_export_dict = None
        self.error_counter = 0

        # add modbus registers automatically for the devices ABB B23 112-100 and ABB B23 312-100
        if self.is_smartgridready is False and self.name == "ABB B23 112-100":
            self.add_RTU_Power_entry(23316, 2, "WATTS", "int32", 0.01)
            self.has_energy_import = True
            self.add_RTU_EnergyImport_entry(20480, 4, "KILOWATT_HOURS", "int64_u", 0.01)
            self.has_energy_export = False
        if self.is_smartgridready is False and self.name == "ABB B23 312-100":
            self.add_RTU_Power_entry(23316, 2, "WATTS", "int32", 0.01)
            self.has_energy_import = True
            self.add_RTU_EnergyImport_entry(20480, 4, "KILOWATT_HOURS", "int64_u", 0.01)
            self.has_energy_export = True
            self.add_RTU_EnergyExport_entry(20484, 4, "KILOWATT_HOURS", "int64_u", 0.01)

    async def read_power(self):
        """
        returns the total power of a powersensor in kW. For not SmartGridReady devices you need to add_RTU_Power_entry() first.
        :returns: the power value, the unit, and error code
        """
        if self.is_smartgridready:
            [value, unit, error_code] = await self.smartgridready.read_value_with_conversion('ActivePowerAC',
                                                                                             'ActivePowerACtot')

            await asyncio.sleep(PowerSensor.sleep_between_requests)

            if error_code == 0:  # todo errorhandling
                self.power_value = value
            else:
                raise NotImplementedError  # here code for error handling smartgridready

        elif not self.is_smartgridready and self.power_dict is not None:
            self.power_value = await self.get_decoded_modbus_value_with_conversion(
                self.power_dict.get("starting_address"),
                self.power_dict.get("length"),
                self.power_dict.get("datatype"),
                int(self.id),
                self.power_dict.get("multiplicator"),
                self.power_dict.get("unit"),
                self.power_dict.get("order"))
            unit = "KILOWATT"
            error_code = 0  # has to change later with error handling
            await asyncio.sleep(PowerSensor.sleep_between_requests)
        else:
            raise NotImplementedError
            # here code if power_dict is not initialized and not SmartGridready
        if self.is_logging:
            self.log_values("POWER")

        return self.power_value, unit, error_code

    async def read_energy_import(self):
        """
        returns the energy import of a powersensor in kW. For not SmartGridReady devices you need to add_RTU_EnergyImport_entry() first.
        :returns: the energy import value, the unit, and error code. Has_energy_import has to be set to True in the power_sensor init
        """
        if self.is_smartgridready and self.has_energy_import:
            [value, unit, error_code] = await self.smartgridready.read_value_with_conversion('ActiveEnerBalanceAC',
                                                                                             'ActiveImportAC')
            await asyncio.sleep(PowerSensor.sleep_between_requests)

            if error_code == 0:
                self.energy_value_import = value
            else:
                raise NotImplementedError  # here code for error handling smartgridready

        # if powersensor is not SmartGridready
        elif not self.is_smartgridready and self.has_energy_import and self.energy_import_dict is not None:
            self.energy_value_import = await self.get_decoded_modbus_value_with_conversion(
                self.energy_import_dict.get("starting_address"),
                self.energy_import_dict.get("length"),
                self.energy_import_dict.get("datatype"),
                int(self.id),
                self.energy_import_dict.get("multiplicator"),
                self.energy_import_dict.get("unit"),
                self.energy_import_dict.get("order"))
            unit = "KILOWATT_HOURS"
            error_code = 0  # has to change later with error handling
            await asyncio.sleep(PowerSensor.sleep_between_requests)

        else:
            raise NotImplementedError
            # here code if power_dict is not initialized and not SmartGridready
        if self.is_logging:
            self.log_values("ENERGY_IMPORT")

        return self.energy_value_import, unit, error_code

    async def read_energy_export(self):
        """
        returns the energy export of a powersensor in kW. For not SmartGridReady devices you need to add_RTU_EnergyExport_entry() first.
        :returns: the energy export value, the unit, and error code. Has_energy_export has to be set to True in the power_sensor init
        """
        if self.is_smartgridready and self.has_energy_export:
            [value, unit, error_code] = await self.smartgridready.read_value_with_conversion('ActiveEnerBalanceAC',
                                                                                             'ActiveExportAC')
            await asyncio.sleep(PowerSensor.sleep_between_requests)

            if error_code == 0:
                self.energy_value_export = value
            else:
                raise NotImplementedError  # here code for error handling smartgridready

        elif not self.is_smartgridready and self.has_energy_export and self.energy_export_dict is not None:
            self.energy_value_export = await self.get_decoded_modbus_value_with_conversion(
                self.energy_export_dict.get("starting_address"),
                self.energy_export_dict.get("length"),
                self.energy_export_dict.get("datatype"),
                int(self.id),
                self.energy_export_dict.get("multiplicator"),
                self.energy_export_dict.get("unit"),
                self.energy_export_dict.get("order"))
            unit = "KILOWATT_HOURS"
            error_code = 0  # has to change later with error handling
            await asyncio.sleep(PowerSensor.sleep_between_requests)
        elif not self.has_energy_export:
            # print(f"The power sensor ({self.name}) has no energy export.")
            return None
        else:
            raise NotImplementedError
            # here code if power_dict is not initialized and not SmartGridready
        if self.is_logging:
            self.log_values("ENERGY_EXPORT")

        return self.energy_value_export, unit, error_code

    async def read_all(self):
        power_value = await self.read_power()
        energy_value_import = await self.read_energy_import()
        energy_value_export = await self.read_energy_export()
        return power_value, energy_value_import, energy_value_export

    def add_RTU_Power_entry(self, starting_address: int, length: int, unit: str, datatype: str, multiplicator: float,
                            order: Endian = Endian.Big):
        """
        Adds information for the power value to not SmartGridReady devices. Has to be called before read_power().
        :param starting_address: the starting address where you want to read from
        :param length: number of register the value takes up
        :param unit: the unit of the Value, possible values WATTS or KILOWATTS. Important! choose the unit that is on the datasheet.
        Conversion will be done automatically.
        :param datatype: the datatype of the read value, possible datatypes: 'int8', 'int8_u', 'int16', 'int16_u',
        'int32', 'int32_u', 'int64', 'int64_u', 'float16', 'float32', 'float64', 'string'
        :param multiplicator: the read value will be multiplied with this.
        """
        self.power_dict = dict(starting_address=starting_address, length=length, unit=unit, datatype=datatype,
                               multiplicator=multiplicator, order=order)

    def add_RTU_EnergyImport_entry(self, starting_address: int, length: int, unit: str, datatype: str,
                                   multiplicator: float, order: Endian = Endian.Big):
        """
        Adds information for the energy import value to not SmartGridReady devices. Has to be called before read_energy_import().
        :param starting_address: the starting address where you want to read from
        :param length: number of register the value takes up
        :param unit: the unit of the Value, possible values WATT_HOURS or KILOWATT_HOURS. Important! choose the unit that is on the datasheet.
        Conversion will be done automatically.
        :param datatype: the datatype of the read value, possible datatypes: 'int8', 'int8_u', 'int16', 'int16_u',
        'int32', 'int32_u', 'int64', 'int64_u', 'float16', 'float32', 'float64', 'string'
        :param multiplicator: the read value will be multiplied with this.
        """
        self.energy_import_dict = dict(starting_address=starting_address, length=length, unit=unit, datatype=datatype,
                                       multiplicator=multiplicator, order=order)
        self.has_energy_import = True

    def add_RTU_EnergyExport_entry(self, starting_address: int, length: int, unit: str, datatype: str,
                                   multiplicator: float, order: Endian = Endian.Big):
        """
        Adds information for the energy export value to not SmartGridReady devices. Has to be called before read_energy_export().
        :param starting_address: the starting address where you want to read from
        :param length: number of register the value takes up
        :param unit: the unit of the Value, possible values WATT_HOURS or KILOWATT_HOURS. Important! choose the unit that is on the datasheet.
        Conversion will be done automatically.
        :param datatype: the datatype of the read value, possible datatypes: 'int8', 'int8_u', 'int16', 'int16_u',
        'int32', 'int32_u', 'int64', 'int64_u', 'float16', 'float32', 'float64', 'string'
        :param multiplicator: the read value will be multiplied with this.
        """
        self.energy_export_dict = dict(starting_address=starting_address, length=length, unit=unit, datatype=datatype,
                                       multiplicator=multiplicator, order=order)
        self.has_energy_export = True

    async def get_decoded_modbus_value_with_conversion(self, addr: int, size: int, data_type: str, slave_id: int,
                                                       multiplicator: float, unit: str,
                                                       order: Endian = Endian.Big) -> float:
        """
        Partially from von SGRPython Library
        Reads register, decodes the value and converts it to kWh or kW.
        possible Datatypes: 'int8', 'int8_u', 'int16', 'int16_u', 'int32', 'int32_u', 'int64', 'int64_u', 'float16', 'float32', 'float64', 'string'
        :param addr: The address to read from and decode
        :param size: The number of registers to read
        :param data_type: The modbus type to decode
        :param slave_id: The slave id of the device
        :param order: Byteorder for decoding, default Endian.Big
        :returns: Decoded float
        """

        reg = await self.client.read_holding_registers(address=addr, count=size, slave=slave_id)
        decoder = PayloadDecoder.fromRegisters(reg.registers, byteorder=order, wordorder=order)

        if not reg.isError():
            decoded_value = decoder.decode(data_type, 0)  # bytecount is only for strings, else 0
            if unit == "WATTS" or unit == "WATT_HOURS":
                decoded_value = decoded_value / 1000  # converts to kWh or kW if it's not already that unit

            return round(decoded_value * multiplicator, 4)  # value gets rounded

    def log_values(self, value_name: str):
        """
        :param value_name: POWER, ENERGY_IMPORT or ENERGY_EXPORT
        """
        if "OpenCEM_statistics" in logging.Logger.manager.loggerDict.keys():
            logger = logging.getLogger("OpenCEM_statistics")
            if value_name == "POWER":
                logger.info(
                    f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};{value_name};{self.power_value};KILOWATT")
            if self.has_energy_import and value_name == "ENERGY_IMPORT":
                logger.info(
                    f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};{value_name};{self.energy_value_import};KILOWATT_HOURS")
            if self.has_energy_export and value_name == "ENERGY_EXPORT":
                logger.info(
                    f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};{value_name};{self.energy_value_export};KILOWATT_HOURS")
            # sensor_type;sensor_name;id;value_name;value;unit;evtl. last_updated


class ShellyPowerSensor(PowerSensor):

    def __init__(self, device_ip: str, name: str = "Shelly 3EM Powermeter", is_logging: bool = True,
                 bus_type: str = "SHELLY_LOCAL", client=None, auth_key: str = None, shelly_server_http: str = None,
                 OpenCEM_id: str = ""):
        """
        creates a shelly power sensor object. Code tested with Shelly 3EM

        :param device_ip: If communication is over the cloud put the device id here, else use the local ip of the device.
        Device_ip / device_id will be stored in self.id
        :param n_channels: the amount of channels the relais has
        :param bus_type: SHELLY_LOCAL or SHELLY_CLOUD
        """
        super().__init__(is_smartgridready=False, id=device_ip, has_energy_import=True, has_energy_export=True,
                         name=name, is_logging=is_logging, bus_type=bus_type, manufacturer="Shelly", client=client,
                         OpenCEM_id=OpenCEM_id)

        if self.bus_type == "SHELLY_CLOUD":
            self.auth_key = auth_key
            self.shelly_server_http = shelly_server_http

    async def read_power(self):
        """
        returns the total power of a Shelly power meter.
        """
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/status"

            async with self.client.get(url) as response:
                status_code = response.status
                response_dict = await response.json()

            if status_code == 200:  # Request was successful
                self.power_value = round(response_dict["total_power"] / 1000, 4)  # power in kW rounded to 4 digits
                unit = "KILOWATT"
                error_code = 0

                if self.is_logging:
                    self.log_values("POWER")  # only logging if request was valid, maybe change later?

                return self.power_value, unit, error_code

        elif self.bus_type == "SHELLY_CLOUD":
            logging.warning("use <read_all()> for reading 3EM values over the Shelly cloud.")
            raise NotImplementedError
        else:
            raise NotImplementedError

    async def read_energy_import(self):
        """
        returns the total energy import of a Shelly power meter.
        """
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/status"
            async with self.client.get(url) as response:
                status_code = response.status
                response_dict = await response.json()

            if status_code == 200:  # Request was successful
                emeters = response_dict["emeters"]  # information of all three phases
                # calculate total
                energy_counter = 0  # in Wh
                for index in range(3):
                    energy_counter = energy_counter + emeters[index]["total"]

                self.energy_value_import = round(energy_counter / 1000, 4)  # Energy import in kWH rounded to 4 digtis
                unit = "KILOWATT_HOURS"
                error_code = 0

                if self.is_logging:
                    self.log_values("ENERGY_IMPORT")  # only logging if request was valid, maybe change later?

                return self.energy_value_import, unit, error_code

        elif self.bus_type == "SHELLY_CLOUD":
            logging.warning("use <read_all()> for reading 3EM values over the Shelly cloud.")
            raise NotImplementedError
        else:
            raise NotImplementedError

    async def read_energy_export(self):
        """
        returns the total energy export of a Shelly power meter.
        """
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/status"

            async with self.client.get(url) as response:
                status_code = response.status
                response_dict = await response.json()

            if status_code == 200:  # Request was successful
                emeters = response_dict["emeters"]  # information of all three phases
                # calculate total
                energy_counter = 0  # in Wh
                for index in range(3):
                    energy_counter = energy_counter + emeters[index]["total_returned"]

                self.energy_value_export = round(energy_counter / 1000, 4)  # Energy import in kWH rounded to 4 digits
                unit = "KILOWATT_HOURS"
                error_code = 0

                if self.is_logging:
                    self.log_values("ENERGY_EXPORT")  # only logging if request was valid, maybe change later?

                return self.energy_value_export, unit, error_code

        elif self.bus_type == "SHELLY_CLOUD":
            logging.warning("use <read_all()> for reading 3EM values over the Shelly cloud.")
            raise NotImplementedError
        else:
            raise NotImplementedError

    async def read_all(self):
        """
        Reads power, energy import and energy export. Cloud request only possible once a second.
        Use this methode if you are communication to the 3EM over the Shelly cloud.

        :returns: power_value, energy_import and energy_export, as well as the units and error code to the values
        """

        if self.bus_type == "SHELLY_LOCAL":
            power_value = await self.read_power()
            energy_value_import = await self.read_energy_import()
            energy_value_export = await self.read_energy_export()
            return power_value, energy_value_import, energy_value_export

        if self.bus_type == "SHELLY_CLOUD":
            url = f"{self.shelly_server_http}/device/status"
            data = {'id': self.id, 'auth_key': self.auth_key}

            async with aiohttp.request("POST", url, data=data) as response:
                status_code = response.status
                response_dict = await response.json()

            await asyncio.sleep(2)  # sleep 2 sec because api requests are restricted to 1 per second

            if status_code == 200:  # Request was successful
                self.power_value = round(response_dict["data"]["device_status"]["total_power"] / 1000,
                                         4)  # power in kW rounded to 4 digits
                power_value = (self.power_value, "KILOWATT", 0)  # value, unit, error code

                # calculate the energy total over the 3 phases
                energy_counter_import = 0  # in Wh
                energy_counter_export = 0  # in Wh
                for index in range(3):
                    energy_counter_import = energy_counter_import + \
                                            response_dict["data"]["device_status"]["emeters"][index]["total"]
                    energy_counter_export = energy_counter_export + \
                                            response_dict["data"]["device_status"]["emeters"][index]["total_returned"]

                self.energy_value_import = round(energy_counter_import / 1000, 4)
                self.energy_value_export = round(energy_counter_export / 1000, 4)
                energy_value_import = (self.energy_value_import, "KILOWATT_HOURS", 0)  # value, unit, error code
                energy_value_export = (self.energy_value_export, "KILOWATT_HOURS", 0)  # value, unit, error code
                return power_value, energy_value_import, energy_value_export


class TemperatureSensorRoom(Sensor):
    # derived class for temperature sensor

    def __init__(self, *, is_smartgridready: bool, id: str, name: str = "", manufacturer: str = "", bus_type: str = "",
                 client=None, XML_file: str = "", is_logging: bool = True, OpenCEM_id: str = ""):
        # initialize sensor
        super().__init__(is_smartgridready=is_smartgridready, id=id, name=name, manufacturer=manufacturer,
                         bus_type=bus_type, XML_file=XML_file, client=client, is_logging=is_logging,
                         OpenCEM_id=OpenCEM_id)
        self.sensor_type = 'temperature_room'
        self.temperature_value = 0 # in °C
        self.last_updated = ""
        self.error_counter = 0

    def read_temperature(self):
        # Hier abstraktes Read Temperature
        raise NotImplementedError

    def log_values(self):
        if "OpenCEM_statistics" in logging.Logger.manager.loggerDict.keys():
            logger = logging.getLogger("OpenCEM_statistics")
            logger.info(
                f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};TEMPERATURE;{self.temperature_value};CELSIUS;{self.last_updated}")
            # Format: sensor_type;sensor_name;id;value_name;value;unit;evtl. last_updated


# added 07.04.23 S.F.
class TemperatureSensorStorage(Sensor):
    # derived class for temperature sensor

    def __init__(self, *, is_smartgridready: bool, id: str, name: str = "", manufacturer: str = "", bus_type: str = "",
                 client=None, XML_file: str = "", is_logging: bool = True, OpenCEM_id: str = ""):
        # initialize sensor
        super().__init__(is_smartgridready=is_smartgridready, id=id, name=name, manufacturer=manufacturer,
                         bus_type=bus_type, XML_file=XML_file, client=client, is_logging=is_logging,
                         OpenCEM_id=OpenCEM_id)
        self.sensor_type = 'temperature_storage'
        self.temperature_value = 0 # in °C
        self.last_updated = ""
        self.error_counter = 0

    def read_temperature(self):
        # Hier abstraktes Read Temperature
        raise NotImplementedError

    def log_values(self):
        raise NotImplementedError


class ShellyTempSensor(TemperatureSensorRoom):
    """
     A class for the shelly H&T sensor that derives from temperature_sensor. It has Temperature and Humidity values.
     Internet connection is needed.
    """

    def __init__(self, *, device_id: str, name: str = "Shelly T&H", is_logging: bool = True, auth_key: str = None,
                 shelly_server_http: str = None,
                 OpenCEM_id: str = ""):
        super().__init__(is_smartgridready=False, id=device_id, name=name, manufacturer="Shelly",
                         bus_type="SHELLY_CLOUD", is_logging=is_logging, OpenCEM_id=OpenCEM_id)

        if self.bus_type == "SHELLY_CLOUD":
            self.auth_key = auth_key
            self.shelly_server_http = shelly_server_http

    async def read_temperature(self):
        """
        reads the last measured temperature with timestamp from the Shelly Cloud in Celsius.
         If the value read is not valid or the connection failed, the last values will be returned with is_valid = False
        """
        url = f"{self.shelly_server_http}/device/status"
        data = {'id': self.id, 'auth_key': self.auth_key}

        async with aiohttp.request('POST', url, data=data) as response:
            status_code = response.status
            response_dict = await response.json()

        await asyncio.sleep(2)  # sleep 2 sec because api requests are restricted to 1 per second

        if status_code == 200:  # Request was successful
            temperature = response_dict["data"]["device_status"]["tmp"]["value"]
            time_stamp = response_dict["data"]["device_status"]["_updated"]  # is in utc time
            is_valid = response_dict["data"]["device_status"]["tmp"]["is_valid"]
            if is_valid:
                self.temperature_value = temperature
                self.last_updated = time_stamp

                if self.is_logging:
                    self.log_values()  # only logging if request was valid, maybe change later?

                return self.temperature_value, self.last_updated, is_valid
            # is_valid from request response is False
            else:
                logging.info(f"Temperature request on {self.name} was not valid")
                return self.temperature_value, self.last_updated, False
        # Request failed
        else:
            logging.warning(f"Temperature request to {self.name} failed!")
            return self.temperature_value, self.last_updated, False


class ShellyTrvTempSensor(TemperatureSensorRoom):

    def __init__(self, *, device_id: str, name: str = "Shelly TRV temperature", is_logging: bool = True, client=None,
                 bus_type="SHELLY_LOCAL", auth_key: str = None, shelly_server_http: str = None, OpenCEM_id: str = ""):
        super().__init__(is_smartgridready=False, id=device_id, name=name, manufacturer="Shelly",
                         bus_type=bus_type, is_logging=is_logging, client=client, OpenCEM_id=OpenCEM_id)

        if self.bus_type == "SHELLY_CLOUD":
            self.auth_key = auth_key
            self.shelly_server_http = shelly_server_http

    async def read_temperature(self):
        # reads the temperature from a trv over cloud or local connection
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/thermostats/0"

            async with self.client.post(url) as response:
                status_code = response.status
                response_dict = await response.json()

            if status_code == 200:
                # parse response
                temperature = response_dict["tmp"]["value"]
                time_stamp = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                is_valid = response_dict["tmp"]["is_valid"]

                if is_valid:
                    self.temperature_value = temperature
                    self.last_updated = time_stamp

                    if self.is_logging:
                        self.log_values()  # only logging if request was valid, maybe change later?

                    return self.temperature_value, self.last_updated, is_valid

                # is_valid from request response is False
                else:
                    logging.info(f"Temperature request on {self.name} was not valid")
                    return self.temperature_value, self.last_updated, False
            # request failed
            else:
                print("error - return status code:" + str(status_code))
                return ["", status_code]

        if self.bus_type == "SHELLY_CLOUD":
            url = f"{self.shelly_server_http}/device/status"
            data = {'id': self.id, 'auth_key': self.auth_key}

            async with aiohttp.request('POST', url, data=data) as response:
                status_code = response.status
                response_dict = await response.json()

            await asyncio.sleep(2)  # sleep 2 sec because api requests are restricted to 1 per second

            if status_code == 200:  # Request was successful
                temperature = response_dict["data"]['device_status']['thermostats'][0]['tmp']['value']
                is_valid = response_dict["data"]['device_status']['thermostats'][0]['tmp']['is_valid']
                time_stamp = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                if is_valid:
                    self.temperature_value = temperature
                    self.last_updated = time_stamp

                    if self.is_logging:
                        self.log_values()  # only logging if request was valid, maybe change later?

                    return self.temperature_value, self.last_updated, is_valid
                # is_valid from request response is False
                else:
                    logging.info(f"Temperature request on {self.name} was not valid")
                    return self.temperature_value, self.last_updated, False
            # Request failed
            else:
                logging.warning(f"Temperature request to {self.name} failed!")
                return self.temperature_value, self.last_updated, False


class Actuator():
    # base class for any actuator (e.g. relais, switch box, drive, etc.)

    def __init__(self, *, is_smartgridready: bool, id: str, name: str = "", manufacturer: str = "", bus_type: str = "",
                 client=None,
                 XML_file: str = "",
                 is_logging: bool = True,
                 OpenCEM_id: str = ""):  # is_smartgridready und id wird in jedem Fall gebraucht, der Rest ist optional

        # initialize sensor
        self.is_smartgridready = is_smartgridready
        self.actuator_type = 'any'  # ist der Sensortype irgendwo im XML ersichtlich?
        self.is_logging = is_logging  # logging aktiviert
        self.exception_counter = 0
        self.OpenCEM_id = OpenCEM_id

        # if smartgridready
        if self.is_smartgridready and XML_file != "":
            self.smartgridready = SmartGridreadyComponent(XML_file)  # add smartgridready component to sensor
            self.name, self.manufacturer, self.bus_type = self.smartgridready.read_device_information()  # gets the needed device information from the XML #TODO andere Informationen hinzufügen
            self.smartgridready.sgr_component.set_slave_id(id)
            self.id = id

        # if not smartgridready
        if not self.is_smartgridready:
            self.name = name
            self.manufacturer = manufacturer
            self.bus_type = bus_type
            self.id = id
            # create client for communication,possible values are RTU or REST
            if self.bus_type in ["SHELLY_LOCAL", "MODBUS_RTU", "MODBUS_TCP"] and client is not None:
                self.client = client
            elif self.bus_type == "REST":
                raise NotImplementedError
            elif self.bus_type == "SHELLY_CLOUD":
                pass
            else:
                raise NotImplementedError

    # abstract methodes
    def write_channel(self, channel: int, state: str):
        """
        :param channel: Channel to manipulate
        :param state: "on" or "off"
        """
        pass

    def read_channel(self, channel):
        """
        :param channel: Relais channel to read from
        """

    def read_all_channels(self):
        """
        reads the values of all channels
        """

    def log_values(self):
        raise NotImplementedError


class RelaisActuator(Actuator):
    # base class for any actuator (e.g. relais, switch box, drive, etc.)

    def __init__(self, *, is_smartgridready: bool, id: str, n_channels: int, name: str = "", manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True, OpenCEM_id: str = ""):
        # initialize actuator
        super().__init__(is_smartgridready=is_smartgridready, id=id, name=name, manufacturer=manufacturer,
                         bus_type=bus_type, client=client, XML_file=XML_file, is_logging=is_logging,
                         OpenCEM_id=OpenCEM_id)
        self.actuator_type = 'relais'
        self.n_channels = n_channels

        self.channel_values = [0] * self.n_channels

        self.error_counter = 0

    def log_values(self):
        raise NotImplementedError


class ShellyRelais(RelaisActuator):

    def __init__(self, *, device_ip: str, n_channels: int, name: str = "Shelly Relais", is_logging: bool = True,
                 bus_type: str = "SHELLY_LOCAL", client=None, auth_key: str = None, shelly_server_http: str = None,
                 OpenCEM_id: str = ""):
        """
        creates a shelly Relais object.

        :param device_ip: If communication is over the cloud put the device id here, else use the local ip of the device.
        Device_ip / device_id will be stored in self.id
        :param n_channels: the amount of channels the relais has
        :param bus_type: SHELLY_LOCAL or SHELLY_CLOUD
        """
        super().__init__(is_smartgridready=False, id=device_ip, n_channels=n_channels, name=name, manufacturer="Shelly",
                         bus_type=bus_type, is_logging=is_logging, client=client, OpenCEM_id=OpenCEM_id)

        if self.bus_type == "SHELLY_CLOUD":
            self.auth_key = auth_key
            self.shelly_server_http = shelly_server_http



    async def write_channel(self, channel, state: str):
        """
        Will change the state of a given relay channel

        :param channel: Channel which will be changed
        :param state: on or off
        """
        if isinstance(channel, str):
            channel = int(channel)

        if channel > (self.n_channels - 1):
            raise ValueError("Given channel number is to big for this relais.")

        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/relay/{channel}"
            data = {'turn': state}

            async with self.client.post(url, data=data) as response:
                status_code = response.status
                response_dict = await response.json()

            if status_code == 200:
                return [response_dict, 200]  # Todo feedback auswerten
            else:
                print("error - return status code:" + str(status_code))
                return ["", status_code]

        if self.bus_type == "SHELLY_CLOUD":
            url = f"{self.shelly_server_http}/device/relay/control"
            data = {'id': self.id, 'auth_key': self.auth_key, 'channel': channel, 'turn': state}

            # Cloud request only once a second possible
            async with aiohttp.request("POST", url, data=data) as response:
                status_code = response.status
                response_dict = await response.json()

            await asyncio.sleep(2)  # sleep 2 sec because api requests are restricted to 1 per second

            if status_code == 200:
                return [response_dict, 200]
            else:
                print("error - return status code:" + str(response_dict))
                return ["", status_code]

    async def read_all_channels(self):
        """
        returns all the values of the channels of a relay
        """
        # if communication happens over the local ip
        if self.bus_type == "SHELLY_LOCAL":
            for channel in range(self.n_channels):
                url = f"http://{self.id}/relay/{channel}"

                async with self.client.get(url) as response:
                    status_code = response.status
                    response_dict = await response.json()

                # response successful
                if status_code == 200:
                    self.channel_values[channel] = response_dict['ison']

                    # log values
                    if self.is_logging:
                        self.log_values(channel)

                # response not successful
                else:
                    raise NotImplementedError

            return self.channel_values

        # if communication happens over the Shelly cloud
        if self.bus_type == "SHELLY_CLOUD":
            url = f"{self.shelly_server_http}/device/status"
            data = {'id': self.id, 'auth_key': self.auth_key}

            async with aiohttp.request("POST", url, data=data) as response:
                status_code = response.status
                response_dict = await response.json()

            await asyncio.sleep(2)  # sleep 2 sec because api requests are restricted to 1 per second

            # response successful
            if status_code == 200:
                # iterate through all channels
                for channel in range(self.n_channels):
                    self.channel_values[channel] = response_dict['data']['device_status'][f"switch:{channel}"]['output']
                    # log values
                    if self.is_logging:
                        self.log_values(channel)
                return self.channel_values

            else:
                NotImplementedError  # TODO Fall wenn Antwort nicht gültig war

    async def read_channel(self, channel):
        """This Method will return the state of the given Shelly relay channel. It only works over SHELLY_LOCAL communication.
         For communication over SHELLY_CLOUD please use read_all_channels()"""
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/relay/{channel}"

            async with self.client.get(url) as response:
                status_code = response.status
                response_dict = await response.json()

            # response successful
            if response.status_code == 200:
                self.channel_values[channel] = response_dict['ison']
                # log values
                if self.is_logging:
                    self.log_values(channel)

                return self.channel_values[channel]

            # response not successful
            else:
                raise NotImplementedError  # TODO Fall wenn Antwort nicht gültig war

        # Communication over cloud is not supported with reading only one channel
        if self.bus_type == "SHELLY_CLOUD":
            print("read_channel() only works with SHELLY_LOCAL communication.")
            raise NotImplementedError  # TODO warning einfügen

    def log_values(self, channel: int):
        if "OpenCEM_statistics" in logging.Logger.manager.loggerDict.keys():
            logger = logging.getLogger("OpenCEM_statistics")
            logger.info(
                f"{self.actuator_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{self.id};{channel};{self.channel_values[channel]}")
            # Format actuator: Timestamp;actuator_type;actuator_name;id;channel;value


class Device():
    # base class for any device (e.g. heat pump, solar plant, etc.)

    def __init__(self, *, is_smartgridready: bool, id: str, simulated: bool, name: str = "", manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True,
                 min_time_running: float = 0.0, min_time_off: float = 0.0, min_time_waiting: float = 0.0,
                 min_power_for_running=0.00, power_dict: dict = None, nominal_power: float = 0, OpenCEM_id: str = ""):

        self.room_temperature_sensor = None
        self.storage_temperature_sensor = None
        self.name = name  # name of the device
        self.device_type = 'none'  # device type not known yet (see derived classes)
        self.prosumer_type = 'none'  # prosumer type not known yet (later one of 'producer', 'consumer', etc.
        self.manufacturer = manufacturer  # manufacturer of the device
        self.actuator = None  # device has no actuator as default
        self.actuator_channel_values = []  # initialize actuator value
        self.actuator_channels = []  # id of the actuator channels linked to the device ([on/off channel,lvl2 channel, lvl3 channel,...]
        self.power_sensor = None  # device has no power sensor as default
        self.power_sensor_power = 0  # initialize power sensor value
        self.power_sensor_energy_import = 0  # initialize power sensor value
        self.power_sensor_energy_export = 0  # initialize power sensor value

        self.is_smartgridready = is_smartgridready  # check if device is SmartGridReady
        self.bus_type = bus_type  # bus type, e.g. 'modbus', 'modbus_tcp', 'modbus_rtu'
        self.id = id  # address, e.g. '192.168.0.8' for 'modbus_tcp, '1' for 'modbus_rtu'
        self.client = client
        self.OpenCEM_id = OpenCEM_id

        self.num_aux_sensors = 0  # number of auxiliary sensor is set to zero
        self.aux_sensors = []

        self.simulated = simulated  # true: device is simulated, false: device is connected to hardware
        self.simulation_task = None # task object whe simulated

        self.mode = 0  # mode of device (any device specific number, 0 = off, 1 = on, 2 = high, etc.)

        self.state = "OFF"  # state of device ('off', 'running', 'waiting') TODO: implement logic!
        self.time_of_last_change = datetime.now() - timedelta(
            minutes=min_time_running)  # time of last state change TODO: implement logic !
        self.min_time_running = min_time_running  # minimum time in running state [minutes]
        self.min_time_off = min_time_off  # minimum time in off state [minutes]
        self.min_time_waiting = min_time_waiting  # minimum time in waiting state [minutes]
        self.min_power_running = min_power_for_running  # minimum power limit (kW) for detecting a 'running' state

        self.nominal_power = nominal_power  # nominal power consumption of device
        self.controller = None
        self.control_type = None
        self.mode_config = {"0": "0", "1": "1"}  # default for on/off only one relais channel
        self.connected = True  # False when connection attempt failed

        if power_dict is None and nominal_power != 0:
            self.power_dict = {"0": 0, "1": self.nominal_power}
        else:
            self.power_dict = power_dict

        self.mean_buffer = [0] * 100  # initialize buffer with 100 zeros
        self.mean_buffer_index = 0  # current buffer index
        self.mean_buffer_num_readings = 0  # number of readings stored in buffer
        self.mean = 0

        if is_smartgridready:
            self.smartgridready = SmartGridreadyComponent(XML_file)
            [self.brand_name, self.nominal_power,
             self.level_of_operation] = self.smartgridready.read_device_profile()  # TODO check this

    def add_actuator(self, actuator: Actuator,
                     channels: list):  # add an actuator with channel that is linked to the device
        if self.actuator is None:
            self.actuator = actuator
            self.actuator_channels = channels
        else:
            raise Warning("This device already has an actuator.")  # only 1 actuator allowed
        return None

    # revised 19.3.23
    def add_power_sensor(self,
                         a_power_sensor: PowerSensor):  # add a power sensor to the device (only 1 power sensor allowed)
        if self.power_sensor is None:
            self.power_sensor = a_power_sensor
        else:
            raise Warning("This device already has a power_sensor.")
        return None

    async def read_power_sensor(self):  # read power value from sensor
        if self.simulated:
            return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import,
                    10]  # error_code 10 = simulated

        if self.power_sensor is not None:
            try:
                response = await self.power_sensor.read_all()
                self.power_sensor.error_counter = 0  # reset the error counter for the power sensor
            # if exception occurs
            except Exception as e:
                if self.power_sensor.error_counter >= 5:
                    logging.warning(f"Error on power sensor ({self.power_sensor.OpenCEM_id}). Check connection. Exception: {e}")
                else:
                    logging.warning(f"Exception occurred on {self.power_sensor.OpenCEM_id}; Exception: {e}")
                    self.power_sensor.error_counter += 1  # count the error counter up for the power sensor


                # last values get returned
                return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import,
                        20]  # error_code 10 = power sensor connection issue

            self.power_sensor_power = response[0][0]
            self.power_sensor_energy_import = response[1][0]
            if self.power_sensor.has_energy_export:
                self.power_sensor_energy_export = response[2][0]
            else:
                self.power_sensor_energy_export = 0
            error_code = 0

        else:
            raise ValueError(f"{self.name} has no power sensor to read from.")
            # if self.state == 'waiting' and self.power >= self.min_power_running:   #TODO check this
            # self.state = 'running'

        self.update_mean()  # calculates the new mean

        return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import, error_code]

    async def simulate_device(self):
        pass
        # abstract method


    def add_controller(self, controller_obj: controllers.Controller):
        # add a controller object to the device
        if not isinstance(controller_obj, controllers.Controller):
            raise ValueError("controller_obj is not a instance of Controller.")

        if self.controller is not None:
            print("device already has a controller")
            return

        self.controller = controller_obj
        self.control_type = self.controller.type
        self.controller.set_device(self)  # create connection that controller knows the device

    # revised 23.3.23
    async def calc_controller(self):
        # Will calculate the controller of the device and set the outputs accordingly
        old_mode = self.mode

        # Calculate the output of the controller. Distinction between PriceController and other controllers
        if isinstance(self.controller, controllers.PriceController):
            mode, output, signal = self.controller.calc_output(state=self.room_temperature)
        else:
            mode, output, signal = self.controller.calc_output()

        # check if device is already allowed to change. Dynamic ExcessController are allowed to change their output
        # value (power) as long as they don't change between on/off
        if self.check_min_time() or (isinstance(self.controller, controllers.DynamicExcessController) and mode >= 1):

            if self.actuator is not None:
                await self.mode_to_actuator(mode)  # set actuator channels

            # check if there was a change in the mode and change the state of the device
            if old_mode != mode:
                self.time_of_last_change = datetime.now()
                print(f"time of last change (device: {self.name}): {self.time_of_last_change}")
                if mode > 0:
                    self.state = "RUNNING"
                else:
                    self.state = "OFF"

            self.mode = mode

        else:
            # print("device can not yet change its mode")
            pass

    # TODO: CHECK THIS MECHANISM !!!
    def check_min_time(self):
        # check if any change in the state is allowed -
        if self.simulated and False:
            change_allowed = True  # no time checking in simulation mode

        else:
            # calculate elapsed time
            time_elapsed = datetime.now() - self.time_of_last_change
            change_allowed = False
            if self.state == 'RUNNING':
                # if device has a dynamic controller change is allways allowed when running
                if time_elapsed >= timedelta(minutes=self.min_time_running):
                    change_allowed = True
            if self.state == 'OFF':
                if time_elapsed >= timedelta(minutes=self.min_time_off):
                    change_allowed = True
            if self.state == 'WAITING':
                if time_elapsed >= timedelta(minutes=self.min_time_waiting):
                    change_allowed = True

        return change_allowed

    def set_mode_config(self, mode_config: list):
        """
        clears the old mode_config and sets the new one
        :param mode_config: list of strings. Format examples ["000","010","111"] or ["00","01","10","11"] length of
        the elements must match with number of actuator channnels
        """
        self.mode_config.clear()
        for index, element in enumerate(mode_config):
            self.mode_config[str(index)] = element

        # todo check that no value is in there twice

    async def mode_to_actuator(self, mode: int):
        """
        This function converts the mode from a controller to an output combination and sets the actuators accordingly
        to the given mode_config. The mode_config can be set with set_mode_config()
        :param mode: the mode that was returned by a controller
        """
        combination = self.mode_config.get(str(mode))
        if combination is not None:
            for index, char in enumerate(combination):
                if len(combination) != len(self.actuator_channels):
                    raise ValueError("Combination length does not match number of actuator channels of the device.")

                elif char == '1':
                    try:
                        await self.actuator.write_channel(self.actuator_channels[index], "on")
                        self.actuator.error_counter = 0
                    except:
                        self.actuator.error_counter += 1
                        logging.warning(f"Error occurred on actuator ({self.actuator.OpenCEM_id})")
                        if self.actuator.error_counter >= 5:
                            logging.warning(
                                f"Error occurred on actuator 5 times in a row ({self.actuator.OpenCEM_id}). Check connection!")
                elif char == '0':
                    try:
                        await self.actuator.write_channel(self.actuator_channels[index], "off")
                        self.actuator.error_counter = 0
                    except:
                        self.actuator.error_counter += 1
                        logging.warning(f"Error occurred on actuator ({self.actuator.OpenCEM_id})")
                        if self.actuator.error_counter >= 5:
                            logging.warning(
                                f"Error occurred on actuator 5 times in a row ({self.actuator.OpenCEM_id}). Check connection!")
                else:
                    raise ValueError("Char was invalid.")

        else:
            raise ValueError("combination for this mode is not configured")

        self.actuator_channel_values = combination  # safe the current channel combination

        # todo check if mode is the same as current mode

    def log_values(self):
        # logs the value of a device. Log depends on what device it is
        logger = logging.getLogger("device_logger")

        # power sensor
        # if the CentralPowerMeter is calculated with a production and a consumption meter.
        if isinstance(self,
                      CentralPowerMeter) and self.power_sensor_production is not None and self.power_sensor_total_consumption is not None:
            power, energy_import, energy_export = self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_export
        # device is a directly communicating EvCharger
        elif isinstance(self, EvCharger) and self.client is not None:
            power, energy_import, energy_export = self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_export
        # device has no power measurement
        elif self.power_sensor is None and not self.simulated:
            power, energy_import, energy_export = "", "", ""
        # device has a PowerSensor
        else:
            power, energy_import, energy_export = self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_export

        # actuators
        if self.actuator is None:
            channel_values = ""
        else:
            channel_values = self.actuator_channel_values

        # temperature
        # only for heat pumps or power to heat devices
        if isinstance(self, (HeatPump, PowerToHeat)):
            if (self.storage_temperature_sensor is None and not self.simulated) or isinstance(self, PowerToHeat):
                storage_temp = ""
            else:
                storage_temp = self.storage_temperature

            if self.room_temperature_sensor is None and not self.simulated:
                room_temp = ""
            else:
                room_temp = self.room_temperature

        else:
            room_temp = ""
            storage_temp = ""

        logger.info(
            f"{self.OpenCEM_id};{self.name};{self.connected};{power};{energy_import};{energy_export};{room_temp};{storage_temp};{self.mode};{channel_values}")
        # "timestamp;OpenCEM-id;name;connected;power;energy_import;energy_export;room_temp;storage_temp;mode;channel_values"
        # base device has no temperature sensors

    def update_mean(self):
        # updates the consumption mean of a devide
        if self.state == "RUNNING":
            self.mean_buffer[self.mean_buffer_index] = self.power_sensor_power

            # update the buffer index and number of readings
            self.mean_buffer_index = (self.mean_buffer_index + 1) % 100

            self.mean_buffer_num_readings = min(self.mean_buffer_num_readings + 1, 100)

            readings = self.mean_buffer[:self.mean_buffer_num_readings]
            # calculate mean from readings
            mean = sum(readings) / len(readings)
            self.mean = mean

    # revised 07.04.23 S.F.
    def add_room_temperature_sensor(self,
                                    sensor: TemperatureSensorRoom):  # add an auxiliary sensor to the device (only 1 power sensor allowed)
        if not isinstance(sensor, TemperatureSensorRoom):
            raise ValueError("Sensor is not a instance of TemperatureSensorRoom.")
        else:
            self.aux_sensors.append(sensor)
            self.room_temperature_sensor = sensor  # TODO David Fragen wie es sich das vorgestellt hat. Es gibt nur ein Raumtemp. Sensor für HeatPump, oder?

    # revised 07.04.23 S.F.
    def add_storage_temperature_sensor(self,
                                       sensor: TemperatureSensorStorage):  # add an auxiliary sensor to the device (only 1 power sensor allowed)
        if not isinstance(sensor, TemperatureSensorStorage):
            raise ValueError("Sensor is not a instance of TemperatureSensorStorage.")
        else:
            self.aux_sensors.append(sensor)
            self.storage_temperature_sensor = sensor


class PvPlant(Device):
    # class for photovoltaic production plant

    def __init__(self, *, is_smartgridready: bool, id: str, max_power: float, simulated: bool, name: str = "",
                 manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True, power_dict: dict = None,
                 nominal_power: float = 0, OpenCEM_id: str = ""):

        # initialize base class
        super().__init__(is_smartgridready=is_smartgridready, id=id, simulated=simulated, name=name,
                         manufacturer=manufacturer, bus_type=bus_type, client=client, XML_file=XML_file,
                         is_logging=is_logging, power_dict=power_dict, nominal_power=nominal_power,
                         OpenCEM_id=OpenCEM_id)

        self.device_type = 'pv_plant'  # set device type
        self.prosumer_type = 'producer'  # set prosumer type to 'producer'
        self.max_power = max_power  # maximal electrical power consumption (kW)

    # TODO In der Zukunft: kommunikation über wechselrichter (sunspec) einrichten

    async def simulate_device(self):

        if sim_start_time is None:  # check if there already exists a start_time
            t_loop_start = round(asyncio.get_running_loop().time(), 2)
        else:
            t_loop_start = sim_start_time

        print(f"Simulation of device {self.name} started.")
        while True:
            # power
            t = round(asyncio.get_running_loop().time() - t_loop_start, 2)
            t_shifted = t - (6 * 60 * 60 / OpenCEM_speed_up_factor)  # Subtracting 6 hours in seconds

            # power_max is amplitude of the sine function
            self.power_sensor_power = round(
                self.max_power * math.sin(OpenCEM_speed_up_factor * 2 * math.pi * (t_shifted / 86400)), 2)
            if self.power_sensor_power <= 0:
                self.power_sensor_power = 0
            # print(f"production {self.name} is: {self.power_sensor_power} kW")
            await asyncio.sleep(simulation_loop_time / OpenCEM_speed_up_factor)


# revised 19.3.23
class CentralPowerMeter(Device):
    # class for central power meter (bidirectional measurement at grid connection point)

    def __init__(self, *, is_smartgridready: bool, id: str, max_power: float, simulated: bool, name: str = "",
                 manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True, power_dict: dict = None,
                 OpenCEM_id: str = "", isBidirectional: bool = True):
        # initialize base class
        super().__init__(is_smartgridready=is_smartgridready, id=id, simulated=simulated, name=name,
                         manufacturer=manufacturer, bus_type=bus_type, client=client, XML_file=XML_file,
                         is_logging=is_logging, nominal_power=0, power_dict=power_dict, OpenCEM_id=OpenCEM_id)

        self.device_type = 'CENTRAL_POWER_METER'  # set device type
        self.prosumer_type = 'bidirectional'
        self.max_power = max_power  # maximal electrical power (positive or negative) (kW)
        self.isBidirectional = isBidirectional
        if not self.isBidirectional:
            self.power_sensor_production = None
            self.power_sensor_total_consumption = None

    def add_power_sensor_production(self, a_power_sensor: PowerSensor):
        if self.power_sensor_production is None:
            self.power_sensor_production = a_power_sensor
        else:
            raise Warning("This device already has a power_sensor_production.")
        return None

    def add_power_sensor_total_consumption(self, a_power_sensor: PowerSensor):
        if self.power_sensor_total_consumption is None:
            self.power_sensor_total_consumption = a_power_sensor
        else:
            raise Warning("This device already has a power_sensor_total_consumption.")
        return None

    async def read_power_sensor(self):
        # not bidirectional, needs to read consumption and production sensor
        if not self.isBidirectional:
            power_total_consumption = 0
            power_production = 0
            # consumption sensor
            if self.power_sensor_total_consumption is not None:
                try:
                    power_total_consumption, unit, errorcode = await self.power_sensor_total_consumption.read_power()
                    self.power_sensor_total_consumption.error_counter = 0  # reset the error counter for the power sensor
                # if exception occurs
                except Exception as e:
                    if self.power_sensor_total_consumption.error_counter >= 5:
                        logging.warning(f"Error on power sensor ({self.power_sensor_total_consumption.OpenCEM_id}). Check connection. Exception: {e}")
                    else:
                        logging.warning(f"Exception occurred on {self.power_sensor_total_consumption.OpenCEM_id}; Exception: {e}")
                        self.power_sensor_total_consumption.error_counter += 1  # count the error counter up for the power sensor

                    # last values get returned if error occurred while reading sensor
                    return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import,
                            20]  # error_code 10 = power sensor connection issue
            # production sensor
            if self.power_sensor_production is not None:
                try:
                    power_production, unit, errorcode = await self.power_sensor_production.read_power()
                    self.power_sensor_production.error_counter = 0  # reset the error counter for the power sensor
                # if exception occurs
                except Exception as e:
                    if self.power_sensor_production.error_counter >= 5:
                        logging.warning(f"Error on power sensor ({self.power_sensor_production.OpenCEM_id}). Check connection. Exception: {e}")
                    else:
                        logging.warning(f"Exception occurred on {self.power_sensor_production.OpenCEM_id}; Exception: {e}")
                        self.power_sensor_production.error_counter += 1  # count the error counter up for the power sensor

                    # last values get returned if error occurred while reading sensor
                    return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import,
                            20]  # error_code 10 = power sensor connection issue

            # calculate central power meter power from production and consumption
            # will give positive power if power from grid is consumed
            self.power_sensor_power = power_total_consumption - power_production
            return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import, 0]

        # if central power meter is bidirectional, read_power_sensor from parent class (Device) will be returned
        else:
            return super().read_power_sensor()


class HeatPump(Device):
    # class for heat pump devices

    def __init__(self, *, is_smartgridready: bool, id: str, simulated: bool, nominal_power: float = 0.0, name: str = "",
                 manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True, power_dict: dict = None,
                 simulation_mean_temp: float = 21,
                 simulation_temp_amplitude: float = 1.5, OpenCEM_id: str = ""):

        # initialize base class
        super().__init__(is_smartgridready=is_smartgridready, id=id, simulated=simulated, name=name,
                         manufacturer=manufacturer, bus_type=bus_type, client=client, XML_file=XML_file,
                         is_logging=is_logging, nominal_power=nominal_power, power_dict=power_dict,
                         OpenCEM_id=OpenCEM_id, min_time_running=30 / OpenCEM_speed_up_factor,
                         min_time_off=30 / OpenCEM_speed_up_factor, min_time_waiting=5 / OpenCEM_speed_up_factor,
                         min_power_for_running=0.5)

        # init parameters
        self.device_type = 'HeatPump'
        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'
        # init states
        self.room_temperature = 0  # initialize room temperature
        self.storage_temperature = 0  # initialize storage temperature
        # init temperature sensors
        self.room_temperature_sensor = None  # room temperature sensor
        self.storage_temperature_sensor = None  # storage temperature sensor

        # used for when simulated
        self.sim_mean_temp = simulation_mean_temp   # mean temp when simulated
        self.sim_amplitude_temp = simulation_temp_amplitude # amplitude of simulted temperature signal

    # revised 08.04.23
    async def read_aux_sensors(self):
        """
        Reads the room temperature and storage temperature sensors if they are declared.
        Reading temperature from a SGr Heatpump is not yet implemented.
        :return:
        """
        if self.is_smartgridready:
            raise NotImplementedError("SGr not yet implemented for heat pumps")
            # Has his own internal temp sensor

        if self.simulated:  # don't read sensors when device is simulated
            return
        # read room temperature sensor
        if self.room_temperature_sensor is not None:
            try:
                temp, last_updated, is_valid = await self.room_temperature_sensor.read_temperature()
                if is_valid:
                    self.room_temperature = temp
                self.room_temperature_sensor.error_counter = 0
            except:
                logging.warning(f"Exception occurred on {self.room_temperature_sensor.OpenCEM_id}")
                self.room_temperature_sensor.error_counter += 1  # count the error counter up for the power sensor
                if self.room_temperature_sensor.error_counter >= 5:
                    logging.warning(
                        f"Error on room temperature sensor ({self.room_temperature_sensor.OpenCEM_id}). Check connection.")

        # read storage temperature sensor
        if self.storage_temperature_sensor is not None:
            try:
                temp, last_updated, is_valid = await self.storage_temperature_sensor.read_temperature()
                if is_valid:
                    self.storage_temperature = temp
                self.storage_temperature_sensor.error_counter = 0
            except:
                logging.warning(f"Exception occurred on {self.storage_temperature_sensor.OpenCEM_id}")
                self.storage_temperature_sensor.error_counter += 1  # count the error counter up for the power sensor
                if self.storage_temperature_sensor.error_counter >= 5:
                    logging.warning(
                        f"Error on room temperature sensor ({self.storage_temperature_sensor.OpenCEM_id}). Check connection.")


    async def simulate_device(self):
        timeshift = 10 * 60 * 60
        if sim_start_time is None:  # check if there already exists a start_time
            t_loop_start = round(asyncio.get_running_loop().time(), 2)
        else:
            t_loop_start = sim_start_time

        print(f"Simulation of device {self.name} started.")

        while True:
            # temperature
            if self.room_temperature_sensor is None:
                t = round(asyncio.get_running_loop().time() - t_loop_start, 2)
                t_shifted = t - (timeshift / OpenCEM_speed_up_factor)  # shift to the left

                # sin function with period of a day. The highest temperature is at 4 PM
                self.room_temperature = round(
                    self.sim_mean_temp + self.sim_amplitude_temp * math.sin(
                        2 * math.pi * OpenCEM_speed_up_factor * (t_shifted / 86400)), 2)
                # print(f"Temp is: {self.room_temperature} °C")

            if self.storage_temperature_sensor is None:
                self.storage_temperature = round(
                    self.sim_mean_temp + self.sim_amplitude_temp * math.sin(
                        2 * math.pi * OpenCEM_speed_up_factor * (t_shifted / 86400)), 2)

            # power_consumption
            if self.power_sensor is None:
                self.power_sensor_power = self.power_dict[str(self.mode)]
                # print(f"Power consumption {self.name} is: {self.power_sensor_power} kW")

            await asyncio.sleep(simulation_loop_time / OpenCEM_speed_up_factor)  # gets calculated once a second

    async def calc_controller(self):
        # Will calculate the controller of the device and set the outputs accordingly
        if self.check_min_time():
            old_mode = self.mode

            if isinstance(self.controller, controllers.PriceController):
                mode, output, signal = self.controller.calc_output(state=self.room_temperature)
            else:
                mode, output, signal = self.controller.calc_output()

            if self.actuator is not None:
                await self.mode_to_actuator(mode)  # set actuator channels

            # check if there was a change in the mode and change the state of the device
            if self.mode != mode:
                self.time_of_last_change = datetime.now()
                print(f"time of last change (device: {self.name}): {self.time_of_last_change}")
                if mode > 0:
                    self.state = "RUNNING"
                else:
                    self.state = "OFF"

            self.mode = mode

        else:
            # print("device can not yet change its mode")
            pass


class EvCharger(Device):
    # class for electric vehicle charging stations

    def __init__(self, *, is_smartgridready: bool, id: str, simulated: bool, max_power: float = 0,
                 min_power: float = 0, nominal_power: float = 0, name: str = "", manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True, power_dict: dict = None,
                 OpenCEM_id: str = "", phases: str = "SINGLE_PHASE"):
        # initialize base class
        super().__init__(is_smartgridready=is_smartgridready, id=id, simulated=simulated, name=name,
                         manufacturer=manufacturer, bus_type=bus_type, client=client, XML_file=XML_file,
                         is_logging=is_logging, nominal_power=nominal_power, power_dict=power_dict,
                         OpenCEM_id=OpenCEM_id, min_time_running=20 / OpenCEM_speed_up_factor,
                         min_time_off=20 / OpenCEM_speed_up_factor, min_time_waiting=5 / OpenCEM_speed_up_factor,
                         min_power_for_running=0.5)

        self.plug_connected = False
        self.ev_state = ''
        self.device_type = 'EvCharger'  # set device type to 'ev_charger'
        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'
        self.min_power = min_power  # minimal electrical power consumption (kW)
        self.max_power = max_power  # maximal electrical power consumption (kW)
        if nominal_power == 0:
            self.nominal_power = 0.5 * (
                    min_power + max_power)  # nominal electrical power consumption (kW) #TODO stimmt das so, oder Vereinfachung?

        if phases == "SINGLE_PHASE":
            self.nr_of_phases = 1
        elif phases == "TRIPPLE_PHASES":
            self.nr_of_phases = 3
        else:
            raise ValueError(f"{phases} is not supported for Device EvCharger. Use SINGLE_PHASE or TRIPPLE_PHASES")

    async def get_ev_state(self):
        """
        This methode returns the letter in uppercase of the current state of the ev_charger. SGr is not implemented yet.
        Only works if the name of the charger is "WALLBE_ECO_S"
        :return: current state (A-F)
        """
        if self.name == "WALLBE_ECO_S":
            response = await self.client.read_input_registers(address=100, count=1, slave=int(self.id))
            response_reg = response.registers[0]  # Format will be the ASCII Code (example: 65 = A)
            self.ev_state = chr(response_reg)

            if self.ev_state == 'A':
                self.plug_connected = False
            else:
                self.plug_connected = True

            return self.ev_state  # returns the letter for the state in uppercase

        elif self.is_smartgridready:
            raise NotImplementedError
        else:
            raise ValueError("The name of the device is not known, neither is the device SmartGridready")

    async def enable_loading_clearance(self):
        await self.client.write_coil(400, value=True, slave=int(self.id))

    async def disable_loading_clearance(self):
        await self.client.write_coil(address=400, value=False, slave=int(self.id))

    async def read_loading_clearance(self):
        response = await self.client.read_coils(address=400, slave=int(self.id))
        return response.bits[0]  # return first bit from coil (loading clearance)

    async def set_loading_power(self, loading_power: float):
        """
        :param loading_power: desired loading power in kW
        :return: None
        """
        # TODO this calculation is different for an other type of loading connection
        amps = (loading_power * 1000) / (self.nr_of_phases * 230)
        amps_formatted = int(round(amps * 10))  # example 6.1 Amps = 61

        if self.name == "WALLBE_ECO_S":
            # set loading current
            await self.client.write_register(address=528, value=amps_formatted, slave=int(self.id))

        if self.is_smartgridready:
            raise NotImplementedError

    async def read_power_sensor(self):
        # calculate power directly from used current if no power sensor is installed
        if self.power_sensor is None and self.name == "WALLBE_ECO_S":
            # if EV is charging calculate power consumption
            if self.ev_state == "C":
                response = await self.client.read_holding_registers(address=300, count=1, slave=int(self.id))

                if not response.isError():
                    current = response.registers[0] / 10  # current in Amps
                    power = current * (self.nr_of_phases * 230 / 1000)  # power calculated from current in kW
                    self.power_sensor_power = round(power, 4)  # value gets rounded

                    error_code = 0

                    return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import,
                            error_code]
            # if EV is not charging power is = 0
            else:
                error_code = 0
                self.power_sensor_power = 0
                return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import,
                        error_code]


        # if device isnt WALLBE_ECO_S or has an additional power sensor
        else:
            response = await super().read_power_sensor()
            self.power_sensor_power = response[0]
            self.power_sensor_energy_import = response[1]
            self.power_sensor_energy_import = response[2]
            error_code = response[3]
            return [self.power_sensor_power, self.power_sensor_energy_import, self.power_sensor_energy_import,
                    error_code]

    async def calc_controller(self):
        # if device is simulated
        if self.simulated:
            mode, output, signal = self.controller.calc_output()
            if isinstance(self.controller, controllers.DynamicExcessController):
                self.power_sensor_power = output
            else:
                self.power_sensor_power = self.power_dict[str(self.mode)]

            self.mode = mode
            if self.mode >= 1:
                self.state = "RUNNING"
            else:
                self.state = "OFF"
            return
        try:
            # if device is not simulated
            old_ev_state = self.ev_state
            ev_state = await self.get_ev_state()  # update ev state

            if ev_state == 'A':  # vehicle not connected
                await self.disable_loading_clearance()

            if ev_state == 'B':  # vehicle connected, waiting for clearance from CEM
                mode, output, signal = self.controller.calc_output()

                # give loading clearance if enough excess
                if mode >= 1:
                    if self.check_min_time():
                        await self.enable_loading_clearance()

            if ev_state in ['C', 'D']:  # vehicle loading
                # changed from State B to C or D
                if old_ev_state == "B":
                    self.time_of_last_change = datetime.now()
                    print(f"time of last change (device: {self.name}): {self.time_of_last_change}. Turned EV charger on.")
                    self.state = "RUNNING"

                mode, output, signal = self.controller.calc_output()

                # dynamicExcessController
                if isinstance(self.controller, controllers.DynamicExcessController) and mode >= 1:
                    await self.set_loading_power(output)

                # regular Controller
                else:
                    if self.actuator is not None:
                        await self.mode_to_actuator(mode)  # set actuator channels

                # disable loading clearance if not enough excess_power
                if self.check_min_time() and mode == 0:
                    await self.disable_loading_clearance()
                    self.time_of_last_change = datetime.now()
                    print(f"time of last change (device: {self.name}): {self.time_of_last_change}. Turned EV charger off.")
                    self.state = "OFF"
        except Exception as e:
            logging.warning(f"An Exception occurred on {self.name}({self.OpenCEM_id}. Exception: {e}")


class PowerToHeat(Device):
    # class for power to heat applications, e.g. boilers with electric heaters

    def __init__(self, *, is_smartgridready: bool, id: str, simulated: bool, max_power: float = 0.0,
                 min_power: float = 0.0, nominal_power: float = 0, name: str = "", manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True, power_dict: dict = None,
                 OpenCEM_id: str = "",simulation_mean_temp: float = 22.5,
                 simulation_temp_amplitude: float = 3.5,):
        # initialize base class
        super().__init__(is_smartgridready=is_smartgridready, id=id, simulated=simulated, name=name,
                         manufacturer=manufacturer, bus_type=bus_type, client=client, XML_file=XML_file,
                         is_logging=is_logging, nominal_power=nominal_power, power_dict=power_dict,
                         OpenCEM_id=OpenCEM_id, min_time_running=10 / OpenCEM_speed_up_factor,
                         min_time_off=10 / OpenCEM_speed_up_factor, min_time_waiting=1 / OpenCEM_speed_up_factor,
                         min_power_for_running=0.1)

        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'
        self.level_of_operation = '4_dynamic_setpoint'  # set default SmartgridReady level
        self.device_type = "PowerToHeat"
        self.min_power = min_power  # minimal electrical power consumption (kW)
        self.max_power = max_power  # maximal electrical power consumption (kW)
        if nominal_power == 0:
            self.nominal_power = 0.5 * (
                    min_power + max_power)

        # init states
        self.room_temperature = 0  # initialize room temperature
        # init temperature sensors
        self.room_temperature_sensor = None  # room temperature sensor

        self.sim_amplitude_temp = simulation_temp_amplitude
        self.sim_mean_temp = simulation_mean_temp

    async def read_aux_sensors(self):
        """
        Reads the room temperature and storage temperature sensors if they are declared.
        Reading temperature from a SGr Heatpump is not yet implemented.
        :return:
        """
        if self.is_smartgridready:
            raise NotImplementedError("SGr not yet implemented for heat pumps")
            # Has his own internal temp sensor

        if self.simulated:  # don't read sensors when device is simulated
            return

        if self.room_temperature_sensor is not None:
            try:
                temp, last_updated, is_valid = await self.room_temperature_sensor.read_temperature()
                if is_valid:
                    self.room_temperature = temp
                self.room_temperature_sensor.error_counter = 0
            except:
                logging.warning(f"Exception occurred on {self.room_temperature_sensor.OpenCEM_id}")
                self.room_temperature_sensor.error_counter += 1  # count the error counter up for the power sensor
                if self.room_temperature_sensor.error_counter >= 5:
                    logging.warning(
                        f"Error on room temperature sensor ({self.room_temperature_sensor.OpenCEM_id}). Check connection.")


    async def simulate_device(self):
        timeshift = 10 * 60 * 60
        if sim_start_time is None:  # check if there already exists a start_time
            t_loop_start = round(asyncio.get_running_loop().time(), 2)
        else:
            t_loop_start = sim_start_time

        print(f"Simulation of device {self.name} started.")

        while True:
            # temperature
            if self.room_temperature_sensor is None:
                t = round(asyncio.get_running_loop().time() - t_loop_start, 2)
                t_shifted = t - (timeshift / OpenCEM_speed_up_factor)  # shift to the left

                # sin function with period of a day. The highest temperature is at 4 PM
                self.room_temperature = round(
                    self.sim_mean_temp + self.sim_amplitude_temp * math.sin(
                        2 * math.pi * OpenCEM_speed_up_factor * (t_shifted / 86400)), 2)
                # print(f"Temp is: {self.room_temperature} °C")

            # power_consumption
            if self.power_sensor is None:
                self.power_sensor_power = self.power_dict[str(self.mode)]
                # print(f"Power consumption {self.name} is: {self.power_sensor_power} kW")

            await asyncio.sleep(simulation_loop_time / OpenCEM_speed_up_factor)  # gets calculated once a second

class HouseholdAppliance(Device):
    # class for household appliances, e.g. dishwashers

    def __init__(self, *, is_smartgridready: bool, id: str, simulated: bool, nominal_power: float = 0.0, name: str = "",
                 manufacturer: str = "",
                 bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True, power_dict: dict = None,
                 OpenCEM_id: str = ""):
        # initialize base class
        super().__init__(is_smartgridready=is_smartgridready, id=id, simulated=simulated, name=name,
                         manufacturer=manufacturer, bus_type=bus_type, client=client, XML_file=XML_file,
                         is_logging=is_logging, nominal_power=nominal_power, power_dict=power_dict,
                         OpenCEM_id=OpenCEM_id, min_time_running=5 / OpenCEM_speed_up_factor,
                         min_time_off=5 / OpenCEM_speed_up_factor, min_time_waiting=1 / OpenCEM_speed_up_factor,
                         min_power_for_running=0.5)

        self.device_type = "HouseholdAppliance"
        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'

    async def simulate_device(self):
        print(f"Simulation of device {self.name} started.")
        while True:
            if self.power_sensor is None:
                if isinstance(self.controller, controllers.DynamicExcessController):
                    self.power_sensor_power = self.controller.output
                else:
                    self.power_sensor_power = self.power_dict[str(self.mode)]
                # print(f"Power consumption {self.name} is: {self.power_sensor_power} kW")

            await asyncio.sleep(simulation_loop_time / OpenCEM_speed_up_factor)  # gets calculated once a second


class RemainingConsumption(Device):

    def __init__(self, *, simulated: bool, is_logging: bool = True, OpenCEM_id: str = "", minPower: float = 0,
                 maxPower: float = 2, device_setting: str = "CALCULATED"):

        super().__init__(is_smartgridready=False, is_logging=is_logging, OpenCEM_id=OpenCEM_id, id="",
                         simulated=simulated)

        self.device_type = 'REMAINING_CONSUMPTION'
        self.name = self.device_type
        self.prosumer_type = 'consumer'
        self.device_setting = device_setting
        self.minPower = minPower
        self.maxPower = maxPower

    async def simulate_device(self):
        print(f"Simulation of device {self.name} started.")
        while True:
            # set random power between limits
            if self.power_sensor is None:
                self.power_sensor_power = round(random.uniform(self.minPower, self.maxPower), 2)
            else:
                logging.warning("Remaining consumption device cant' be simulated if it has a power sensor.")
            await asyncio.sleep(simulation_loop_time / OpenCEM_speed_up_factor)


class CommunicationChannel:
    # base class to describe a communication channel
    def __init__(self, name, OpenCEM_id, type, extra):
        self.name = name
        self.OpenCEM_id = OpenCEM_id
        self.type = type

        # decision tree for CommunicationChannel type
        match self.type:

            case "MODBUS_TCP":
                address = extra["address"]
                port = extra["port"]
                self.client = AsyncModbusTcpClient(host=address, port=port)

            case "MODBUS_RTU":
                port = extra["port"]
                baudrate = extra["baudrate"]
                match extra["parity"]:
                    case "EVEN":
                        parity = "E"
                    case "ODD":
                        parity = "O"
                    case "NONE":
                        parity = "N"
                    case _:
                        raise NotImplementedError("Parity must be NONE,ODD or EVEN")

                self.client = AsyncModbusSerialClient(method="rtu", port=port, baudrate=baudrate, parity=parity)
            case "SHELLY_LOCAL":
                self.client = None
            case "SHELLY_CLOUD":
                self.client = None
                self.shelly_auth_key = extra["authKey"]
                self.shelly_server_address = extra["serverAddress"]

            # general http client for the OpenCEM (for communication with GUI, etc.)
            case "HTTP_MAIN":
                self.client = aiohttp.ClientSession()
            case _:
                raise NotImplementedError("Communication Type not known.")
