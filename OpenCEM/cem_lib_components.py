# evm_lib_components
# Energy Manager Component Classes
# D. Zogg, created 11.05.2022
# modification history:
# 19.05.2022, D. Zogg, sensor and actuator classes added, prepared for SmartGridReady
# 06.09.2022, D. Zogg, new SGrPython code implemented, SGr for all sensors and actuators
# 04.10.2022, D. Zogg, reading device profile for SmartGridReady components prepared, selection of controller_types for heat pump, tarif class added
# 08.10.2022, D. Zogg, automatic setting of default params for controllers, check_min time for all controllers

# TODO: test logic in real application!
import logging
import time
from audioop import mul
from operator import truediv
from pprint import pprint

from pymodbus.constants import Endian

import OpenCEM.cem_lib_controllers as controllers
import random
import sys, os
from datetime import datetime

# Smartgrid Ready Libraries
from sgr_library.generic_interface import GenericInterface

# pymodbus
from pymodbus.client.sync import ModbusSerialClient

from sgr_library.modbusRTU_interface import SgrModbusRtuInterface
from sgr_library.payload_decoder import PayloadDecoder

import requests

# Authentication Key and corresponding server for the Shelly Cloud
shelly_auth_key = "MTUyNjU5dWlk6D393AB193944CE2B1D84E0B573EAB1271DA6F2AF2BC54F67779F5BC27C31E90AD7C7075E0F813D8"
shelly_server_address = "https://shelly-54-eu.shelly.cloud/"


class tarif_info():
    # base class for grid tarif information with 2 tarifs (solar, grid)

    def __init__(self, solar_tarif, grid_tarif):
        # initialize tarifs
        self.solar_tarif = solar_tarif
        self.grid_tarif = grid_tarif

    def set(self, solar_tarif, grid_tarif):
        # update tarifs
        self.solar_tarif = solar_tarif
        self.grid_tarif = grid_tarif

    def get(self):
        # get tarifs
        return [self.solar_tarif, self.grid_tarif]


class OpenCEM_RTU_client:
    """
    creates a global RTU Client for OpenCEM. There can only be one client globally.
    If there already exist a smartGridready, put it as keyword argument global_client = client.
    """
    OpenCEM_global_RTU_client = None

    def __init__(self, port: str = "COM7", baudrate: int = 19200, parity: str = "E", client_timeout: int = 1, *,
                 global_client=None):  # global_client:if there already exist a smartGridready client it can be put here
        # if there does not exist a smartGridReady client
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


class smartgridready_component():
    # class for component with smartgridready compatibility

    def __init__(self, XML_file: str):

        interface_file = XML_file
        self.sgr_component = GenericInterface(interface_file)

    def read_value(self, functional_profile: str, data_point: str):
        # read one value from a given data point within a functional profile
        error_code = 0
        # Todo check if right find_dp from RTU gets used
        data_point = self.sgr_component.find_dp(functional_profile, data_point)
        value = self.sgr_component.getval(data_point)
        multiplicator = self.sgr_component.get_multiplicator(data_point)
        power_10 = self.sgr_component.get_power_10(data_point)
        unit = self.sgr_component.get_unit(data_point)

        if multiplicator > 0:
            return_value = value * 10 ** power_10 / multiplicator  # --- CHECK IF CORRECT ! ---
        else:
            return_value = value * 10 ** power_10

        return [return_value, unit, error_code]

    def read_value_with_conversion(self, functional_profile: str, data_point: str):
        # read a power or energy value with unit conversion to kW, kWh

        [value, unit, error_code] = self.read_value(functional_profile, data_point)
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


class sensor():
    # base class for any sensor (e.g. power, temperature, etc.)
    def __init__(self, *, is_smartgridready: bool, id: str, name: str = "", manufacturer: str = "", bus_type: str = "",
                 client=None,
                 XML_file: str = "",is_logging: bool = True):  # is_smartgridready und id wird in jedem Fall gebraucht, der Rest ist optional

        # initialize sensor
        self.is_smartgridready = is_smartgridready
        self.sensor_type = 'any'  # ist der Sensortype irgendwo im XML ersichtlich
        self.is_logging = is_logging
        self.exception_counter = 0

        # if smartgridready
        if self.is_smartgridready and XML_file != "":
            self.smartgridready = smartgridready_component(XML_file)  # add smartgridready component to sensor
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
            if self.bus_type == "RTU" and client is not None:
                self.client = client
            elif self.bus_type == "REST":
                pass
                #Todo Überlegung was hier geschehen soll
            else:
                pass
                #Todo Überlegung was hier geschehen soll

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

class power_sensor(sensor):
    # derived class for power sensor
    sleep_between_requests = 0.2  # Time the program will wait after a RTU request in seconds

    def __init__(self, *, is_smartgridready: bool, id: str, has_energy_import: bool, has_energy_export: bool,
                 name: str = "", manufacturer: str = "", bus_type: str = "", client=None, XML_file: str = "", is_logging: bool = True):
        """
        :param is_smartgridready: set True if the device has an SmartGridReady XML_File
        :param id: the slave id of the sensor
        :param has_energy_import: set True if the senor has energy_import information
        :param has_energy_export: set True if the senor has energy_export information
        :param client: the client object which will handle the communication
        :param bus_type: possible bustypes are RTU or REST
        :param XML_file: path to the SmartGridReady XML_File
        """
        # initialize sensor
        super().__init__(is_smartgridready=is_smartgridready, id=id, name=name, manufacturer=manufacturer,
                         bus_type=bus_type, XML_file=XML_file, client=client,is_logging=is_logging)

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


    def read_power(self):
        """
        returns the total power of a powersensor in kW. For not SmartGridReady devices you need to add_RTU_Power_entry() first.
        :returns: the power value, the unit, and error code
        """
        if self.is_smartgridready:
            [value, unit, error_code] = self.smartgridready.read_value_with_conversion('ActivePowerAC',
                                                                                       'ActivePowerACtot')
            time.sleep(power_sensor.sleep_between_requests)  # TODO check if sleep should be put in a different place

            if error_code == 0:
                self.power_value = value
            else:
                raise NotImplementedError  # here code for error handling smartgridready

        elif not self.is_smartgridready and self.power_dict is not None:
            self.power_value = self.get_decoded_modbus_value_with_conversion(self.power_dict.get("starting_address"),
                                                                             self.power_dict.get("length"),
                                                                             self.power_dict.get("datatype"),
                                                                             int(self.id),
                                                                             self.power_dict.get("multiplicator"),
                                                                             self.power_dict.get("unit"),
                                                                             self.power_dict.get("order"))
            unit = "KILOWATT"
            error_code = 0  # has to change later with error handling
            time.sleep(power_sensor.sleep_between_requests)
        else:
            raise NotImplementedError
            # here code if power_dict is not initialized and not SmartGridready
        if self.is_logging:
            self.log_values("POWER")

        return self.power_value, unit, error_code

    def read_energy_import(self):
        """
        returns the energy import of a powersensor in kW. For not SmartGridReady devices you need to add_RTU_EnergyImport_entry() first.
        :returns: the energy import value, the unit, and error code. Has_energy_import has to be set to True in the power_sensor init
        """
        if self.is_smartgridready and self.has_energy_import:
            [value, unit, error_code] = self.smartgridready.read_value_with_conversion('ActiveEnerBalanceAC',
                                                                                       'ActiveImportAC')
            time.sleep(power_sensor.sleep_between_requests)

            if error_code == 0:
                self.energy_value_import = value
            else:
                raise NotImplementedError  # here code for error handling smartgridready

        # if powersensor is not SmartGridready
        elif not self.is_smartgridready and self.has_energy_import and self.energy_import_dict is not None:
            self.energy_value_import = self.get_decoded_modbus_value_with_conversion(
                self.energy_import_dict.get("starting_address"),
                self.energy_import_dict.get("length"),
                self.energy_import_dict.get("datatype"),
                int(self.id),
                self.energy_import_dict.get("multiplicator"),
                self.energy_import_dict.get("unit"),
                self.energy_import_dict.get("order"))
            unit = "KILOWATT_HOURS"
            error_code = 0  # has to change later with error handling
            time.sleep(power_sensor.sleep_between_requests)

        else:
            raise NotImplementedError
            # here code if power_dict is not initialized and not SmartGridready
        if self.is_logging:
            self.log_values("ENERGY_IMPORT")

        return self.energy_value_import, unit, error_code

    def read_energy_export(self):
        """
        returns the energy export of a powersensor in kW. For not SmartGridReady devices you need to add_RTU_EnergyExport_entry() first.
        :returns: the energy export value, the unit, and error code. Has_energy_export has to be set to True in the power_sensor init
        """
        if self.is_smartgridready and self.has_energy_export:
            [value, unit, error_code] = self.smartgridready.read_value_with_conversion('ActiveEnerBalanceAC',
                                                                                       'ActiveExportAC')
            time.sleep(power_sensor.sleep_between_requests)

            if error_code == 0:
                self.energy_value_export = value
            else:
                raise NotImplementedError  # here code for error handling smartgridready

        elif not self.is_smartgridready and self.has_energy_export and self.energy_export_dict is not None:
            self.energy_value_export = self.get_decoded_modbus_value_with_conversion(
                self.energy_export_dict.get("starting_address"),
                self.energy_export_dict.get("length"),
                self.energy_export_dict.get("datatype"),
                int(self.id),
                self.energy_export_dict.get("multiplicator"),
                self.energy_export_dict.get("unit"),
                self.energy_export_dict.get("order"))
            unit = "KILOWATT_HOURS"
            error_code = 0  # has to change later with error handling
            time.sleep(power_sensor.sleep_between_requests)
        else:
            raise NotImplementedError
            # here code if power_dict is not initialized and not SmartGridready
        if self.is_logging:
            self.log_values("ENERGY_EXPORT")

        return self.energy_value_export, unit, error_code


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

    def get_decoded_modbus_value_with_conversion(self, addr: int, size: int, data_type: str, slave_id: int,
                                                 multiplicator: float, unit: str, order: Endian = Endian.Big) -> float:
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

        reg = self.client.read_holding_registers(address=addr, count=size, unit=slave_id)
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
        logger = logging.getLogger("OpenCEM_statistics")
        if value_name == "POWER":
            logger.info(f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};{value_name};{self.power_value};KILOWATT")
        if self.has_energy_import and value_name == "ENERGY_IMPORT":
            logger.info(f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};{value_name};{self.energy_value_import};KILOWATT_HOURS")
        if self.has_energy_export and value_name == "ENERGY_EXPORT":
            logger.info(f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};{value_name};{self.energy_value_export};KILOWATT_HOURS")
        # sensor_type;sensor_name;id;value_name;value;unit;evtl. last_updated


class shelly_power_sensor(power_sensor):

    def __init__(self, device_ip: str, name: str = "Shelly 3EM Powermeter", is_logging: bool = True, bus_type: str = "SHELLY_LOCAL"):
        """
        creates a shelly power sensor object. Code tested with Shelly 3EM

        :param device_ip: If communication is over the cloud put the device id here, else use the local ip of the device.
        Device_ip / device_id will be stored in self.id
        :param n_channels: the amount of channels the relais has
        :param bus_type: SHELLY_LOCAL or SHELLY_CLOUD
        """
        super().__init__(is_smartgridready=False, id=device_ip, has_energy_import=True, has_energy_export=True, name=name,is_logging=is_logging, bus_type=bus_type, manufacturer="Shelly")

    def read_power(self):
        """
        returns the total power of a Shelly power meter.
        """
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/status"
            response = requests.get(url)

            if response.status_code == 200:     # Request was successful
                response_dict = response.json()
                self.power_value = round(response_dict["total_power"] / 1000, 4)    # power in kW rounded to 4 digits
                unit = "KILOWATT"
                error_code = 0

                if self.is_logging:
                    self.log_values("POWER")   # only logging if request was valid, maybe change later?

                return self.power_value, unit, error_code

        elif self.bus_type == "SHELLY_CLOUD":
            logging.warning("use <read_all()> for reading 3EM values over the Shelly cloud.")
            raise NotImplementedError
        else:
            raise NotImplementedError

    def read_energy_import(self):
        """
        returns the total energy import of a Shelly power meter.
        """
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/status"
            response = requests.get(url)

            if response.status_code == 200:     # Request was successful
                response_dict = response.json()
                emeters = response_dict["emeters"]  # information of all three phases
                # calculate total
                energy_counter = 0  # in Wh
                for index in range(3):
                    energy_counter = energy_counter + emeters[index]["total"]

                self.energy_value_import = round(energy_counter / 1000, 4)    # Energy import in kWH rounded to 4 digtis
                unit = "KILOWATT_HOURS"
                error_code = 0

                if self.is_logging:
                    self.log_values("ENERGY_IMPORT")   # only logging if request was valid, maybe change later?

                return self.energy_value_import, unit, error_code

        elif self.bus_type == "SHELLY_CLOUD":
            logging.warning("use <read_all()> for reading 3EM values over the Shelly cloud.")
            raise NotImplementedError
        else:
            raise NotImplementedError

    def read_energy_export(self):
        """
        returns the total energy export of a Shelly power meter.
        """
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/status"
            response = requests.get(url)

            if response.status_code == 200:     # Request was successful
                response_dict = response.json()
                emeters = response_dict["emeters"]  # information of all three phases
                # calculate total
                energy_counter = 0 # in Wh
                for index in range(3):
                    energy_counter = energy_counter + emeters[index]["total_returned"]

                self.energy_value_export = round(energy_counter / 1000, 4)    # Energy import in kWH rounded to 4 digits
                unit = "KILOWATT_HOURS"
                error_code = 0

                if self.is_logging:
                    self.log_values("ENERGY_EXPORT")   # only logging if request was valid, maybe change later?


                return self.energy_value_export, unit, error_code

        elif self.bus_type == "SHELLY_CLOUD":
            logging.warning("use <read_all()> for reading 3EM values over the Shelly cloud.")
            raise NotImplementedError
        else:
            raise NotImplementedError

    def read_all(self):
        """
        Reads power, energy import and energy export. Cloud request only possible once a second.
        Use this methode if you are communication to the 3EM over the Shelly cloud.

        :returns: power_value, energy_import and energy_export, as well as the units and error code to the values
        """

        if self.bus_type == "SHELLY_LOCAL":
            power_value = self.read_power()
            energy_value_import = self.read_energy_import()
            energy_value_export = self.read_energy_export()
            return power_value, energy_value_import, energy_value_export

        if self.bus_type == "SHELLY_CLOUD":
            url = f"{shelly_server_address}/device/status"
            data = {'id': self.id, 'auth_key': shelly_auth_key}

            response = requests.post(url, data=data)
            if response.status_code == 200:     # Request was successful
                response_dict = response.json()
                self.power_value = round(response_dict["data"]["device_status"]["total_power"] / 1000, 4)  # power in kW rounded to 4 digits
                power_value = (self.power_value, "KILOWATT", 0) # value, unit, error code

                # calculate the energy total over the 3 phases
                energy_counter_import = 0   # in Wh
                energy_counter_export = 0   # in Wh
                for index in range(3):
                    energy_counter_import = energy_counter_import + response_dict["data"]["device_status"]["emeters"][index]["total"]
                    energy_counter_export = energy_counter_export + response_dict["data"]["device_status"]["emeters"][index]["total_returned"]

                self.energy_value_import = round(energy_counter_import / 1000, 4)
                self.energy_value_export = round(energy_counter_export / 1000, 4)
                energy_value_import = (self.energy_value_import, "KILOWATT_HOURS", 0)   # value, unit, error code
                energy_value_export = (self.energy_value_export, "KILOWATT_HOURS", 0)   # value, unit, error code
                return power_value, energy_value_import, energy_value_export


class temperature_sensor(sensor):
    # derived class for temperature sensor

    def __init__(self, *, is_smartgridready: bool, id: str, name: str = "", manufacturer: str = "", bus_type: str = "",
                 client=None, XML_file: str = "", is_logging: bool = True):
        # initialize sensor
        super().__init__(is_smartgridready=is_smartgridready, id=id, name=name, manufacturer=manufacturer,
                         bus_type=bus_type, XML_file=XML_file, client=client, is_logging=is_logging)
        self.sensor_type = 'temperature'
        self.temperature_value = 0
        self.last_updated = ""  #Todo curretly in UTC time, maybe better in local time

    def read_temperature(self):
        #Hier Abstraktes Read Temperature
        raise NotImplementedError

    def log_values(self):
        raise NotImplementedError

class shelly_temp_and_hum_sensor(temperature_sensor):
    """
     A class for the shelly H&T sensor that derives from temperature_sensor. It has Temperature and Humidity values.
     Internet connection is needed.
    """
    def __init__(self, device_id: str, name: str = "Shelly T&H", is_logging: bool = True):
        super().__init__(is_smartgridready=False, id=device_id, name=name, manufacturer="Shelly", bus_type="SHELLY_CLOUD",is_logging=is_logging)

    def read_temperature(self):
        """
        reads the last measured temperature with timestamp from the Shelly Cloud in Celsius.
         If the value read is not valid or the connection failed, the last values will be returned with is_valid = False
        """
        url= f"{shelly_server_address}/device/status"
        data = {'id': self.id, 'auth_key': shelly_auth_key}

        response = requests.post(url, data=data)

        if response.status_code == 200:     # Request was successful
            response_dict = response.json()
            temperature = response_dict["data"]["device_status"]["tmp"]["value"]
            time_stamp = response_dict ["data"]["device_status"]["_updated"] #is in utc time
            is_valid = response_dict["data"]["device_status"]["tmp"]["is_valid"]
            if is_valid:
                self.temperature_value = temperature
                self.last_updated = time_stamp

                if self.is_logging:
                    self.log_values()   # only logging if request was valid, maybe change later?

                return self.temperature_value, self.last_updated, is_valid
            # is_valid from request response is False
            else:
                logging.info(f"Temperature request on {self.name} was not valid")
                return self.temperature_value, self.last_updated, False
        # Request failed
        else:
            logging.warning(f"Temperature request to {self.name} failed!")
            return self.temperature_value, self.last_updated, False

    def log_values(self):
        logger = logging.getLogger("OpenCEM_statistics")
        logger.info(f"{self.sensor_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{str(self.id)};TEMPERATURE;{self.temperature_value};CELSIUS;{self.last_updated}")
        # Format: sensor_type;sensor_name;id;value_name;value;unit;evtl. last_updated

class actuator():
    # base class for any actuator (e.g. relais, switch box, drive, etc.)

    def __init__(self, *, is_smartgridready: bool, id: str, name: str = "", manufacturer: str = "", bus_type: str = "",
                 client=None,
                 XML_file: str = "",is_logging: bool = True):  # is_smartgridready und id wird in jedem Fall gebraucht, der Rest ist optional

        # initialize sensor
        self.is_smartgridready = is_smartgridready
        self.actuator_type = 'any'  # ist der Sensortype irgendwo im XML ersichtlich?
        self.is_logging = is_logging # logging akriviert
        self.exception_counter = 0

        # if smartgridready
        if self.is_smartgridready and XML_file != "":
            self.smartgridready = smartgridready_component(XML_file)  # add smartgridready component to sensor
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
            if self.bus_type == "RTU" and client is not None:
                self.client = client
            elif self.bus_type == "REST":
                raise NotImplementedError
            else:
                raise NotImplementedError


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

class relais_actuator(actuator):
    # base class for any actuator (e.g. relais, switch box, drive, etc.)

    def __init__(self, *, is_smartgridready: bool, id: str, n_channels: int, name: str = "", manufacturer: str = "", bus_type: str = "", client=None, XML_file: str = "",is_logging: bool = True):
        # initialize actuator
        super().__init__(is_smartgridready=is_smartgridready, id=id, name=name, manufacturer=manufacturer, bus_type=bus_type, client=client, XML_file=XML_file, is_logging=is_logging)
        self.actuator_type = 'relais'
        self.n_channels = n_channels

        self.channel_values = [0] * self.n_channels

    def log_values(self):
        raise NotImplementedError


class shelly_relais_actuator(relais_actuator):

    def __init__(self, device_ip: str, n_channels: int, name: str = "Shelly Relais", is_logging: bool = True, bus_type:str = "SHELLY_LOCAL"):
        """
        creates a shelly Relais object.

        :param device_ip: If communication is over the cloud put the device id here, else use the local ip of the device.
        Device_ip / device_id will be stored in self.id
        :param n_channels: the amount of channels the relais has
        :param bus_type: SHELLY_LOCAL or SHELLY_CLOUD
        """
        super().__init__(is_smartgridready=False, id=device_ip, n_channels=n_channels, name=name, manufacturer="Shelly", bus_type=bus_type, is_logging=is_logging)

    def write_channel(self, channel: int, state: str):
        """
        Will change the state of a given relay channel

        :param channel: Channel which will be changed
        :param state: on or off
        """
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/relay/{channel}"
            data = {'turn': state}

            res = requests.post(url, data=data)
            if res.status_code == 200:
                return [res.json(), 200]    #Todo feedback auswerten
            else:
                print("error - return status code:" + str(res.status_code))
                return ["", res.status_code]

        if self.bus_type == "SHELLY_CLOUD":
            url = f"{shelly_server_address}/device/relay/control"
            data = {'id': self.id, 'auth_key': shelly_auth_key, 'channel': channel, 'turn': state}

            # Cloud request only once a second possible
            res = requests.post(url, data=data)
            if res.status_code == 200:
                return [res.json(), 200]
            else:
                print(res.json())
                print("error - return status code:" + str(res.status_code))
            return ["", res.status_code]

    def read_all_channels(self):
        """
        returns all the values of the channels of a relay
        """
        # if communication happens over the local ip
        if self.bus_type == "SHELLY_LOCAL":
            for channel in range(self.n_channels):
                url = f"http://{self.id}/relay/{channel}"
                response = requests.post(url)

                # response successful
                if response.status_code == 200:
                    self.channel_values[channel] = response.json()['ison']

                    # log values
                    if self.is_logging:
                        self.log_values(channel)

                # response not successful
                else:
                    raise NotImplementedError

            return self.channel_values

        # if communication happens over the Shelly cloud
        if self.bus_type == "SHELLY_CLOUD":
            url = f"{shelly_server_address}/device/status"
            data = {'id': self.id, 'auth_key': shelly_auth_key}

            response = requests.post(url, data=data)
            response_dict = response.json()
            # response successful
            if response.status_code == 200:
                # iterate through all channels
                for channel in range(self.n_channels):
                    self.channel_values[channel] = response_dict['data']['device_status'][f"switch:{channel}"]['output']
                    # log values
                    if self.is_logging:
                        self.log_values(channel)
                return self.channel_values

            else:
                NotImplementedError #TODO Fall wenn Antwort nicht gültig war


    def read_channel(self, channel):
        """This Method will return the state of the given Shelly relay channel. It only works over SHELLY_LOCAL communication.
         For communication over SHELLY_CLOUD please use read_all_channels()"""
        if self.bus_type == "SHELLY_LOCAL":
            url = f"http://{self.id}/relay/{channel}"
            response = requests.post(url)

            #response successful
            if response.status_code == 200:
                self.channel_values[channel] = response.json()['ison']
                # log values
                if self.is_logging:
                    self.log_values(channel)

                return self.channel_values[channel]

            #response not successful
            else:
                raise NotImplementedError   # TODO Fall wenn Antwort nicht gültig war

        # Communication over cloud is not supported with reading only one channel
        if self.bus_type == "SHELLY_LOCAL":
            print("read_channel() only works with SHELLY_LOCAL communication.")
            raise NotImplementedError   # TODO warning einfügen

    def log_values(self, channel: int):
        logger = logging.getLogger("OpenCEM_statistics")
        logger.info(f"{self.actuator_type};{self.name};{self.bus_type};{str(self.is_smartgridready)};{self.id};{channel};{self.channel_values[channel]}")
        # Format actuator: Timestamp;actuator_type;actuator_name;id;channel;value




class device():
    # base class for any device (e.g. heat pump, solar plant, etc.)

    def __init__(self, name: str, manufacturer: str, simulated: bool, is_smartgridready: bool, bus_type: str, id: str,
                 XML_file: str):
        self.name = name  # name of the device
        self.device_type = 'none'  # device type not known yet (see derived classes)
        self.prosumer_type = 'none'  # prosumer type not known yet (later one of 'producer', 'consumer', etc.
        self.manufacturer = manufacturer  # manufacturer of the device
        self.actuator = None  # device has no actuator as default
        self.actuator_value = 0  # initialize actuator value
        self.power_sensor = None  # device has no power sensor as default
        self.power_sensor_value = 0  # initialize power sensor value
        self.is_smartgridready = is_smartgridready  # check if device is SmartGridReady
        self.bus_type = bus_type  # bus type, e.g. 'modbus', 'modbus_tcp', 'modbus_rtu'
        self.id = id  # address, e.g. '192.168.0.8' for 'modbus_tcp, '1' for 'modbus_rtu'

        self.num_aux_sensors = 0  # number of auxiliary sensor is set to zero
        self.aux_sensors = []

        self.simulated = simulated  # true: device is simulated, false: device is connected to hardware
        self.simulation_time = 0  # simulation time (seconds, faster than real time)
        self.mode = 0  # mode of device (any device specific number, 0 = off, 1 = on, 2 = high, etc.)

        self.state = 'none'  # state of device ('none', 'off', 'running', 'waiting') TODO: implement logic!
        self.time_of_last_change = 0  # time of last state change TODO: implement logic !
        self.min_time_running = 10  # minimum time in running state [minutes]
        self.min_time_off = 5  # minimum time in off state [minutes]
        self.min_time_waiting = 5  # minimum time in waiting state [minutes]
        self.min_power_running = 0.1  # minimum power limit (kW) for detecting a 'running' state

        self.nominal_power = 0  # nominal power consumption of device
        self.controller = controllers.controller(name)  # add a generic controller object

        if is_smartgridready:
            self.smartgridready = smartgridready_component(XML_file)
            [self.brand_name, self.nominal_power, self.level_of_operation] = self.smartgridready.read_device_profile()

    def add_actuator(self, name: str, manufacturer: str, bus_type: str, id: str, is_smartgridready: bool,
                     XML_file: str):  # add an actuator to the device (only 1 actuator allowed)
        self.actuator = actuator(name, manufacturer, bus_type, id, is_smartgridready, XML_file)
        self.actuator_value = 0

    def add_power_sensor(self, name: str, manufacturer: str, bus_type: str, id: str, has_energy: bool,
                         is_smartgridready: bool,
                         XML_file: str):  # add a power sensor to the device (only 1 power sensor allowed)
        self.power_sensor = power_sensor(name, manufacturer, bus_type, id, has_energy, is_smartgridready, XML_file)
        return self.power_sensor

    def add_aux_sensor(self, name: str, manufacturer: str, sensor_type: str, bus_type: str, id: str,
                       is_smartgridready: bool,
                       XML_file: str):  # add an auxiliary sensor to the device (only 1 power sensor allowed)
        aux_sensor = sensor(name, manufacturer, bus_type, id, is_smartgridready, XML_file)
        self.aux_sensors.append(aux_sensor)
        self.num_aux_sensors += 1  # add number of auxiliary sensors
        return aux_sensor

    def read_power_sensor(self):  # read power value from sensor
        energy_value_import = 0
        energy_value_export = 0
        error_code = 0
        if self.simulated:  # simulation
            if self.mode > 0:
                self.power_sensor_value = self.nominal_power
            else:
                self.power_sensor_value = 0
        else:  # hardware
            if self.power_sensor != None:
                # read from external power sensor
                [self.power_sensor_value, energy_value_import, energy_value_export, error_code] = power_sensor.read()
            else:
                # read from device via smartgridready interface
                [self.power, unit, error_code1] = self.smartgridready.read_value('Actual_Power', 'Actual_Power_AC')
                [energy_value_import, unit, error_code2] = self.smartgridready.read_value('Actual_Power',
                                                                                          'Actual_Energy_AC')
                error_code = error_code1 or error_code2
            if self.state == 'waiting' and self.power >= self.min_power_running:
                self.state = 'running'
        return [self.power_sensor_value, energy_value_import, energy_value_export, error_code]

    def read_aux_sensors(self):
        values = []
        error_code = 0
        for aux_sensor in self.aux_sensors:
            [value, error_code1] = aux_sensor.read()
            values.append(value)
            error_code = error_code or error_code1
        return values

    def write_actuator(self):  # write output value to actuator
        if self.simulated:  # simulation
            None
        else:  # hardware
            if self.actuator != None:
                actuator.write(self.actuator_value)
                if self.actuator_value > 0:
                    self.state = 'waiting'
                else:
                    self.state = 'off'

    def read_actuator_acknowledge(self):  # read actuator acknowledge (e.g. for EnOcean relays)
        if self.simulated:  # simulation
            None
        else:  # hardware
            if self.actuator != None:
                # TODO --- add code here to read acknowledge data from actuator ---
                actuator_acknowledge = 'none'
                if actuator_acknowledge == 'off':
                    self.state = 'off'
                if actuator_acknowledge == 'on':
                    self.state = 'waiting'

    def add_controller(self, name: str):
        self.controller = controllers.controller(name)  # add a generic controller object

    def calc_controller(self, total_production: float, total_consumption: float, max_production: float,
                        mean_consumption: float):
        # calculate controller output
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output()  # call controller if allowed for change
            self.mode = mode
            self.actuator_value = output
            self.time_of_last_change = datetime.now().time()
            return [mode, output, signal]
        else:
            return [self.mode, self.actuator_value, 0]

    def check_min_time(self):
        # check if any change in the state is allowed --- TODO: CHECK THIS MECHANISM !!!
        if self.simulated:
            change_allowed = True  # no time checking in simulation mode
        else:
            now = datetime.now()
            timestamp = datetime.timestamp(now)
            time_now = timestamp / 60  # get current time, seconds to minutes
            time_elapsed = time_now - self.time_of_last_change
            change_allowed = False
            if self.state == 'running':
                if time_elapsed > self.min_time_running:
                    change_allowed = True
            if self.state == 'off':
                if time_elapsed > self.min_time_off:
                    change_allowed = True
            if self.state == 'waiting':
                if time_elapsed > self.min_time_waiting:
                    change_allowed = True

        return change_allowed


class pv_plant(device):
    # class for photovoltaic production plant

    def __init__(self, name: str, manufacturer: str, max_power: float, simulated: bool, is_smartgridready: bool,
                 bus_type: str, id: str, XML_file: str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id,
                         XML_file)  # initialize base class
        self.device_type = 'pv_plant'  # set device type
        self.prosumer_type = 'production'  # set prosumer type to 'consumer'
        self.max_power = max_power  # maximal electrical power consumption (kW)

    def read_power_sensor(self):
        energy_value_import = 0
        energy_value_export = 0
        error_code = 0
        self.power_sensor_value = 0
        if self.simulated:
            # simulation
            # self.power_sensor_value = random.uniform(0,1)*self.max_power       # change this code to a zero limited sine wave for a day simulation
            self.power_sensor_value = self.max_power
        else:
            # hardware
            if self.power_sensor != None:
                [self.power_sensor_value, energy_value_import, energy_value_export,
                 error_code] = self.power_sensor.read()
            else:
                None  # --- read from inverter interface (e.g. modbus sunspec)
        return [self.power_sensor_value, energy_value_import, energy_value_export, error_code]


class central_power_meter(device):
    # class for central power meter (bidirectional measurement at grid connnection point)

    def __init__(self, name: str, manufacturer: str, max_power: float, simulated: bool, is_smartgridready: bool,
                 bus_type: str, id: str, XML_file: str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id,
                         XML_file)  # initialize base class
        self.device_type = 'central_power_meter'  # set device type
        self.prosumer_type = 'bidirectional'  # set prosumer type to 'consumer'
        self.max_power = max_power  # maximal electrical power (poitive oder negative) (kW)

    def read_power_sensor(self):
        energy_value_import = 0
        energy_value_export = 0
        error_code = 0
        if self.simulated:
            # simulation
            self.power_sensor_value = random.uniform(0,
                                                     1) * self.max_power  # change this code to a typical signal for a day simulation
        else:
            # hardware
            [self.power_sensor_value, energy_value_import, energy_value_export,
             error_code] = self.power_sensor.read()  # positive: from grid, negative: to grid

        return [self.power_sensor_value, energy_value_import, energy_value_export, error_code]


class heat_pump(device):
    # class for heat pump devices

    def __init__(self, name: str, manufacturer: str, nominal_power: float, simulated: bool, is_smartgridready: bool,
                 bus_type: str, id: str, XML_file: str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id,
                         XML_file)  # initialize base class
        # init parameters
        self.device_type = 'heat_pump'  # set device type to 'heatpump'
        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'
        self.control_type = 'temperature_control'  # set default control type
        self.level_of_operation = '4_dynamic_setpoint'  # set default SmartgridReady level
        if nominal_power > 0:
            self.nominal_power = nominal_power  # typical electrical power consumption (kW)
        # init states
        self.mode = 0  # initialize mode to 0 (off)
        self.room_temperature = 0  # initialize room temperature
        self.storage_temperature = 0  # initalize storage temperature
        # init temperature sensors
        self.room_temperature_sensor = None  # room temperature sensor
        self.storage_temperature_sensor = None  # storage temperature sensor

    def add_room_temperature_sensor(self, name: str, manufacturer: str, bus_type: str, id: str, is_smartgridready: bool,
                                    XML_file: str):  # add an auxiliary sensor to the device (only 1 power sensor allowed)
        sensor_type = 'room_temperature'
        self.room_temperature_sensor = super().add_aux_sensor(name, manufacturer, sensor_type, bus_type, id,
                                                              is_smartgridready, XML_file)
        self.room_temperature = 0

    def add_storage_temperature_sensor(self, name: str, manufacturer: str, bus_type: str, id: str,
                                       is_smartgridready: bool,
                                       XML_file: str):  # add an auxiliary sensor to the device (only 1 power sensor allowed)
        sensor_type = 'storage_temperature'
        self.storage_temperature_sensor = super().add_aux_sensor(name, manufacturer, sensor_type, bus_type, id,
                                                                 is_smartgridready, XML_file)
        self.storage_temperature = 0

    def read_aux_sensors(self):
        if self.simulated:
            # simulation
            self.room_temperature = random.uniform(0,
                                                   1) * 7 + 19  # --- random room temperature 19..26 °C --- optimize this code !
            self.storage_temperature = random.uniform(0,
                                                      1) * 25 + 40  # --- random storage temperature 40..65 °C --- optimize this code !
            error_code = 0
        else:
            # hardware
            if self.room_temperature_sensor != None:  # external room temperature sensor
                [self.room_temperature, error_code1] = self.room_temperature_sensor.read()
            else:  # internal room temperature sensor
                [self.room_temperature, unit, error_code1] = self.smartgridready.read_value('RoomTempCtrl',
                                                                                            'RoomZoneTemp')
            if self.storage_temperature_sensor != None:  # external storage temperature sensor
                [self.storage_temperature, error_code2] = self.storage_temperature_sensor.read()
            else:  # internal storage temperature sensor
                [self.storage_temperature, unit, error_code2] = self.smartgridready.read_value('DomHotwaterCtrl',
                                                                                               'ActDomHotWaterTemp')
            error_code = error_code1 or error_code2
        return [self.room_temperature, self.storage_temperature, error_code]

    def write_actuator(self):
        super().write_actuator()

        # --- add aditional code here, e.g. for different control_types ---

    def add_controller(self, name: str, control_type: str):
        # add a controller object corresponding to the control_type and smartgridready level

        self.control_type = control_type
        if self.control_type == 'temperature_control':
            if (self.level_of_operation == '1_on_off') or (self.level_of_operation == '4_dynamic_setpoint'):
                self.controller = controllers.price_controller(name)
                self.controller.set_params(20, 25, 10, 20)  # set default min/max temp and tarifs
            else:
                print("level of operation not defined for heat pump with temperature control: " + str(
                    self.level_of_operation))
        elif self.control_type == 'power_control':
            if (self.level_of_operation == '1_on_off') or (self.level_of_operation == '4_dynamic_setpoint'):
                self.controller = controllers.excess_controller(name)
                self.controller.set_limit(self.nominal_power)
            elif (self.level_of_operation == '2_sg_ready'):
                self.controller = controllers.stepwise_excess_controller(name)
                self.controller.set_limits([self.nominal_power, self.nominal_power * 1.5, self.nominal_power * 2])
            else:
                print(
                    "level of operation not defined for heat pump with power_control: " + str(self.level_of_operation))
        elif self.control_type == 'coverage_control':
            if (self.level_of_operation == '1_on_off'):
                self.controller = controllers.adaptive_coverage_controller(name)
            else:
                print("level of operation not defined for heat pump with coverage control: " + str(
                    self.level_of_operation))
        else:
            print("control type not defined for heat pump: " + str(self.control_type))

    def calc_controller(self, total_production: float, total_consumption: float, max_production: float,
                        mean_consumption: float):
        if self.check_min_time():
            if self.control_type == 'temperature_control':  # price controller
                [mode, output, signal] = self.controller.calc_output(self.room_temperature, total_production,
                                                                     max_production, total_consumption,
                                                                     mean_consumption, self.power_sensor_value,
                                                                     self.nominal_power, True)
            elif self.control_type == 'power_control':
                [mode, output, signal] = self.controller.calc_output(total_production, total_consumption,
                                                                     mean_consumption)
            elif self.control_type == 'coverage_control':
                self.controller.calc_limit(max_production, mean_consumption, None)  # adaptive limit
                [mode, output, signal] = self.controller.calc_output(total_production, total_consumption,
                                                                     mean_consumption)
        else:
            mode = self.mode  # take old values
            output = self.actuator_value
            signal = 0

        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]


class ev_charger(device):
    # class for elektric vehicle charging stations

    def __init__(self, name: str, manufacturer: str, min_power: float, max_power: float, simulated: bool,
                 is_smartgridready: bool, bus_type: str, id: str, XML_file: str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id,
                         XML_file)  # initialize base class
        self.device_type = 'ev_charger'  # set device type to 'ev_charger'
        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'
        self.control_type = 'power_control'  # set default control type
        self.level_of_operation = '4_dynamic_setpoint'  # set default SmartgridReady level
        self.min_power = min_power  # minimal electrical power consumption (kW)
        self.max_power = max_power  # maximal electrical power consumption (kW)
        self.nominal_power = 0.5 * (min_power + max_power)  # nominal electrical power consumption (kW)

    def add_controller(self, name: str, control_type: str):
        # add a controller object corresponding to the control_type and smartgridready level

        self.control_type = control_type
        if (self.control_type == 'power_control'):
            if (self.level_of_operation == '4_dynamic_setpoint') or (self.level_of_operation == '1_on_off'):
                self.controller = controllers.excess_controller(name)
                self.controller.set_limit(self.min_power)
            elif (self.level_of_operation == '2_sg_ready'):
                self.controller = controllers.stepwise_excess_controller(name)
                self.controller.set_limits([self.min_power, self.nominal_power, self.max_power])
            else:
                print("level of operation not defined for ev charger: " + str(self.level_of_operation))
        else:
            print("control type not defined for ev charger: " + str(self.control_type))

    def calc_controller(self, total_production: float, total_consumption: float, max_production: float,
                        mean_consumption: float):
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output(total_production, total_consumption,
                                                                 self.power_sensor_value)
        else:
            mode = self.mode
            output = self.actuator_value
            signal = 0

        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]


class power_to_heat(device):
    # class for power to heat applications, e.g. boilers with electric heaters

    def __init__(self, name: str, manufacturer: str, min_power: float, max_power: float, simulated: bool,
                 is_smartgridready: bool, bus_type: str, id: str, XML_file: str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id,
                         XML_file)  # initialize base class
        self.device_type = 'power_to_heat'  # set device type to 'power_to_heat'
        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'
        self.control_type = 'power_control'  # set default control type
        self.level_of_operation = '4_dynamic_setpoint'  # set default SmartgridReady level
        self.min_power = min_power  # minimal electrical power consumption (kW)
        self.max_power = max_power  # maximal electrical power consumption (kW)
        self.nominal_power = 0.5 * (min_power + max_power)  # set nominal power to max power

    def add_controller(self, name: str, control_type: str):
        # add a controller object corresponding to the control_type and smartgridready level

        self.control_type = control_type
        if (self.control_type == 'power_control'):
            if (self.level_of_operation == '4_dynamic_setpoint') or (self.level_of_operation == '1_on_off'):
                self.controller = controllers.excess_controller(name)
                self.controller.set_limit(self.min_power)
            elif (self.level_of_operation == '2_sg_ready'):
                self.controller = controllers.stepwise_excess_controller(name)
                self.controller.set_limits([self.min_power, self.nominal_power, self.max_power])
            else:
                print("level of operation not defined for power to heat: " + str(self.level_of_operation))
        else:
            print("control type not defined for power to heat: " + str(self.control_type))

    def calc_controller(self, total_production: float, total_consumption: float, max_production: float,
                        mean_consumption: float):
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output(total_production, total_consumption,
                                                                 self.power_sensor_value)
        else:
            mode = self.mode
            output = self.actuator_value
            signal = 0

        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]


class household_appliance(device):
    # class for household appliances, e.g. dish washers

    def __init__(self, name: str, manufacturer: str, nominal_power: float, simulated: bool, is_smartgridready: bool,
                 bus_type: str, id: str, XML_file: str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id,
                         XML_file)  # initialize base class
        self.device_type = 'household_appliance'  # set device type
        self.prosumer_type = 'consumer'  # set prosumer type to 'consumer'
        self.control_type = 'coverage_control'  # default control type (e.g.'coverage_control', 'power_control')
        self.level_of_operation = '1_on_off'
        if nominal_power > 0:
            self.nominal_power = nominal_power  # set nominal power

    def add_controller(self, name: str, control_type: str):
        # add a controller object corresponding to the control_type and smartgridready level

        self.control_type = control_type
        if self.control_type == 'coverage_control':
            if self.level_of_operation == '1_on_off':
                self.controller = controllers.coverage_controller(name)  # add a coverage controller object
                self.controller.set_limit(1)  # set limit to 100% solar coverage as default
            else:
                print("level of operation not defined for household applicance: " + str(self.level_of_operation))
        else:
            print("control type not defined for household appliance: " + str(self.control_type))

    def calc_controller(self, total_production: float, total_consumption: float, max_production: float,
                        mean_consumption: float):
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output(total_production, total_consumption,
                                                                 self.power_sensor_value)
        else:
            mode = self.mode
            output = self.actuator_value
            signal = 0

        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]
