# evm_lib_components
# Energy Manager Component Classes
# D. Zogg, created 11.05.2022
# modification history:
# 19.05.2022, D. Zogg, sensor and actuator classes added, prepared for SmartGridReady
# 06.09.2022, D. Zogg, new SGrPython code implemented, SGr for all sensors and actuators
# 04.10.2022, D. Zogg, reading device profile for SmartGridReady components prepared, selection of controller_types for heat pump, tarif class added
# 08.10.2022, D. Zogg, automatic setting of default params for controllers, check_min time for all controllers

# TODO: test logic in real application!

from audioop import mul
from operator import truediv
import OpenCEM.cem_lib_controllers as controllers
import random
import sys, os
from datetime import datetime

# Smartgrid Ready Libraries
from sgr_library.generic_interface import GenericInterface

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
        return[self.solar_tarif, self.grid_tarif]


class smartgridready_component():
    # class for component with smartgridready compatibility

    def __init__(self, XML_file:str):
        
        interface_file = XML_file
        self.sgr_component = GenericInterface(interface_file) 

    def read_value(self, functional_profile:str, data_point:str):
        # read one value from a given data point within a functional profile
        error_code = 0

        data_point = self.sgr_component.find_dp(functional_profile, data_point)
        value = self.sgr_component.getval(data_point)
        multiplicator = self.sgr_component.get_multiplicator(data_point)
        power_10 = self.sgr_component.get_power_10(data_point)
        unit = self.sgr_component.get_unit(data_point)
        
        if multiplicator > 0:
            return_value = value*10**power_10/multiplicator   # --- CHECK IF CORRECT ! --- 
        else:
            return_value = value*10**power_10                                                       
                                                                                    
        return [return_value, unit, error_code]

    def read_power_value(self, functional_profile:str, data_point:str):
        # read a power or energy value with unit conversion to kW, kWh

        [value, unit, error_code] = self.read_value(functional_profile, data_point)
        if unit.upper() == 'W' or unit.upper() == 'Watt' or unit.upper() == 'Watts':
            value = value/1000          # convert W to kW
        if unit.upper() == 'Wh' or unit.upper() == 'Watt Hours' or unit.upper() == 'Watthours':
            value = value/1000          # convert Wh to kWh

        return [value, unit, error_code]
                
    def write_value(self, functional_profile:str, data_point:str, value):
        # write one value to a given data point within a functional profile

        error_code = 0

        self.sgr_component.setval(functional_profile, data_point, value) 
        
        return error_code

    def read_device_profile(self):
        # get basic info from device profile such as name, nominal power consumption, level of operation, etc.

        device_profile = self.sgr_component.get_device_profile()
        return [device_profile.brand_name, device_profile.nominal_power, device_profile.dev_levelof_operation]


class sensor():
    # base class for any sensor (e.g. power, temperature, etc.)
    
    def __init__(self, name:str, manufacturer:str, bus_type:str, id:str, is_smartgridready:bool, XML_file:str):
        # initialize sensor
        self.name = name
        self.manufacturer = manufacturer
        self.sensor_type = 'any'
        self.bus_type = bus_type
        self.id = id
        self.is_smartgridready = is_smartgridready
        if is_smartgridready:
            self.smartgridready = smartgridready_component(bus_type, XML_file)
            [self.brand_name] = self.smartgridready.read_device_profile()

    def read():
        # --- add code for reading from hardware here
        error_code = 0
        return [None, error_code]       # value = None

class power_sensor(sensor):
    # derived class for power sensor
    
    def __init__(self, name:str, manufacturer:str, bus_type:str, id:str, has_energy:bool, is_smartgridready:bool, XML_file:str):
        # initialize sensor
        super().__init__(name, manufacturer, bus_type, id, is_smartgridready, XML_file)
        self.sensor_type = 'power'
        self.value = 0
        self.has_energy = has_energy
        self.energy_value_import = 0  
        self.energy_value_export = 0       

    def read():
        # read data from sensor
        
        # --- add code for reading from hardware here
        if self.is_smartgridready:
            [value, unit, error_code] = self.smartgridready.read_power_value('ActivePowerAC','ActivePowerACtot','float32')
            if error_code == 0:
                self.value = value
            if self.has_energy:
                [energy_value_import, unit, error_code] = self.smartgridready.read_power_value('ActiveEnerBalanceAC','ActiveImportAC','float32')
                [energy_value_export, unit, error_code] = self.smartgridready.read_power_value('ActiveEnerBalanceAC','ActiveExportAC','float32')
                if error_code == 0:
                    self.energy_value_import = energy_value_import
                    self.energy_value_export = energy_value_export
        else:
            error_code = 100        # no sensor connected

        return [self.value, self.energy_value_import, self.energy_value_export, error_code]

class temperature_sensor(sensor):
    # derived class for temperature sensor
    
    def __init__(self, name:str, manufacturer:str, bus_type:str, id:str, has_energy:bool, is_smartgridready:bool, XML_file:str):
        # initialize sensor
        super().__init__(name, manufacturer, bus_type, id, is_smartgridready, XML_file)
        self.sensor_type = 'temperature'
        self.value = 0    

    def read():
        # read data from sensor
        self.value = 0
        # --- add code for reading from hardware here
        error_code = 100            # no sensor connected
        return [self.value, error_code]

class actuator():
    # base class for any actuator (e.g. relais, switch box, drive, etc.)
    
    def __init__(self, name:str, manufacturer:str, bus_type:str, id:str, is_smartgridready:bool, XML_file:str):
        # initialize actuator
        self.name = name
        self.manufacturer = manufacturer
        self.actuator_type = 'any'
        self.bus_type = bus_type
        self.id = id
        self.is_smartgridread = is_smartgridready
        if is_smartgridready:
            self.smartgridready = smartgridready_component(bus_type, XML_file)
            [self.brand_name] = self.smartgridready.read_device_profile()

    def write(value:float):
        # read data from sensor
        # --- add code for writing to hardware here
        error_code = 100        # no actuator connected
        return error_code

class relais_actuator(actuator):
    # base class for any actuator (e.g. relais, switch box, drive, etc.)
    
    def __init__(self, name:str, manufacturer:str, bus_type:str, id:str, is_smartgridready:bool, XML_file:str):
        # initialize actuator
        super().__init__(name, manufacturer, bus_type, id, is_smartgridready, XML_file)
        self.actuator_type = 'relais'
        self.value = False

    def write(value:bool):
        # read data from sensor
        self.value = value
        # --- add code for writing to hardware here
        error_code = 100    # no actuator connected
        return error_code

class device():
    # base class for any device (e.g. heat pump, solar plant, etc.)

    def __init__(self, name:str, manufacturer:str, simulated:bool, is_smartgridready:bool, bus_type:str, id:str, XML_file:str):
        self.name = name                    # name of the device
        self.device_type = 'none'           # device type not known yet (see derived classes)
        self.prosumer_type = 'none'         # prosumer type not known yet (later one of 'producer', 'consumer', etc.
        self.manufacturer = manufacturer    # manufacturer of the device
        self.actuator = None                # device has no actuator as default
        self.actuator_value = 0             # initialize actuator value
        self.power_sensor = None            # device has no power sensor as default
        self.power_sensor_value = 0         # initialize power sensor value
        self.is_smartgridready = is_smartgridready  # check if device is SmartGridReady
        self.bus_type = bus_type            # bus type, e.g. 'modbus', 'modbus_tcp', 'modbus_rtu'
        self.id = id                        # address, e.g. '192.168.0.8' for 'modbus_tcp, '1' for 'modbus_rtu'
        
        self.num_aux_sensors = 0            # number of auxiliary sensor is set to zero
        self.aux_sensors = []
        
        self.simulated = simulated            # true: device is simulated, false: device is connected to hardware
        self.simulation_time = 0              # simulation time (seconds, faster than real time)
        self.mode = 0                         # mode of device (any device specific number, 0 = off, 1 = on, 2 = high, etc.)
        
        self.state = 'none'                   # state of device ('none', 'off', 'running', 'waiting') TODO: implement logic!
        self.time_of_last_change = 0          # time of last state change TODO: implement logic !
        self.min_time_running = 10            # minimum time in running state [minutes]
        self.min_time_off = 5                # minimum time in off state [minutes]
        self.min_time_waiting = 5            # minimum time in waiting state [minutes] 
        self.min_power_running = 0.1          # minimum power limit (kW) for detecting a 'running' state

        self.nominal_power = 0                    # nominal power consumption of device
        self.controller = controllers.controller(name)            # add a generic controller object

        if is_smartgridready:
            self.smartgridready = smartgridready_component(XML_file)
            [self.brand_name, self.nominal_power, self.level_of_operation] = self.smartgridready.read_device_profile()

    def add_actuator(self, name:str, manufacturer:str, bus_type:str, id:str, is_smartgridready:bool, XML_file:str):        # add an actuator to the device (only 1 actuator allowed)
        self.actuator = actuator(name, manufacturer, bus_type, id, is_smartgridready, XML_file)
        self.actuator_value = 0
        
    def add_power_sensor(self, name:str, manufacturer:str, bus_type:str, id:str, has_energy:bool, is_smartgridready:bool, XML_file:str):    # add a power sensor to the device (only 1 power sensor allowed)
        self.power_sensor = power_sensor(name, manufacturer, bus_type, id, has_energy, is_smartgridready, XML_file)
        return self.power_sensor

    def add_aux_sensor(self, name:str, manufacturer:str, sensor_type:str, bus_type:str, id:str, is_smartgridready:bool, XML_file:str):    # add an auxiliary sensor to the device (only 1 power sensor allowed)
        aux_sensor = sensor(name, manufacturer, bus_type, id, is_smartgridready, XML_file)
        self.aux_sensors.append(aux_sensor)     
        self.num_aux_sensors += 1              # add number of auxiliary sensors
        return aux_sensor

    def read_power_sensor(self):            # read power value from sensor
        energy_value_import = 0
        energy_value_export = 0
        error_code = 0
        if self.simulated:                  # simulation        
            if self.mode > 0:
                self.power_sensor_value = self.nominal_power
            else:
                self.power_sensor_value = 0
        else:                               # hardware
            if self.power_sensor != None:
                # read from external power sensor
                [self.power_sensor_value, energy_value_import, energy_value_export, error_code] = power_sensor.read()
            else:
                # read from device via smartgridready interface
                [self.power, unit, error_code1] = self.smartgridready.read_value('Actual_Power', 'Actual_Power_AC')
                [energy_value_import, unit, error_code2] = self.smartgridready.read_value('Actual_Power', 'Actual_Energy_AC')
                error_code = error_code1 or error_code2
            if self.state == 'waiting' and self.power >=  self.min_power_running:
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
    
    def write_actuator(self):                   # write output value to actuator
        if self.simulated:          # simulation
            None
        else:                       # hardware
            if self.actuator != None:
                actuator.write(self.actuator_value)
                if self.actuator_value > 0: 
                    self.state = 'waiting'
                else:
                    self.state = 'off'

    def read_actuator_acknowledge(self):        # read actuator acknowledge (e.g. for EnOcean relays)
        if self.simulated:          # simulation
            None
        else:                       # hardware
            if self.actuator != None:
                # TODO --- add code here to read acknowledge data from actuator ---
                actuator_acknowledge = 'none'
                if actuator_acknowledge == 'off': 
                    self.state = 'off'
                if actuator_acknowledge == 'on':
                    self.state = 'waiting'           
                     
    def add_controller(self, name:str):
        self.controller = controllers.controller(name)            # add a generic controller object

    def calc_controller(self, total_production:float, total_consumption:float, max_production:float, mean_consumption:float): 
        # calculate controller output
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output()      # call controller if allowed for change
            self.mode = mode
            self.actuator_value = output
            self.time_of_last_change = datetime.now().time()
            return [mode, output, signal]
        else:
            return [self.mode, self.actuator_value, 0]

    def check_min_time(self):
        # check if any change in the state is allowed --- TODO: CHECK THIS MECHANISM !!!
        if self.simulated:
            change_allowed = True           # no time checking in simulation mode
        else:
            now = datetime.now()
            timestamp = datetime.timestamp(now)
            time_now = timestamp/60                        # get current time, seconds to minutes
            time_elapsed = time_now-self.time_of_last_change
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

    def __init__(self, name:str, manufacturer:str, max_power:float, simulated:bool, is_smartgridready:bool, bus_type:str, id:str, XML_file:str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id, XML_file)        # initialize base class
        self.device_type = 'pv_plant'               # set device type
        self.prosumer_type = 'production'             # set prosumer type to 'consumer'
        self.max_power = max_power                # maximal electrical power consumption (kW)

    def read_power_sensor(self):
        energy_value_import = 0
        energy_value_export = 0
        error_code = 0
        self.power_sensor_value = 0
        if self.simulated:
            # simulation
            #self.power_sensor_value = random.uniform(0,1)*self.max_power       # change this code to a zero limited sine wave for a day simulation
            self.power_sensor_value = self.max_power
        else:
            # hardware
            if self.power_sensor != None:
                [self.power_sensor_value, energy_value_import, energy_value_export, error_code] = self.power_sensor.read()
            else:
                None        # --- read from inverter interface (e.g. modbus sunspec)             
        return [self.power_sensor_value, energy_value_import, energy_value_export, error_code]       

class central_power_meter(device):
    # class for central power meter (bidirectional measurement at grid connnection point)

    def __init__(self, name:str, manufacturer:str, max_power:float, simulated:bool, is_smartgridready:bool, bus_type:str, id:str, XML_file:str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id, XML_file)        # initialize base class
        self.device_type = 'central_power_meter'               # set device type
        self.prosumer_type = 'bidirectional'             # set prosumer type to 'consumer'
        self.max_power = max_power                # maximal electrical power (poitive oder negative) (kW)

    def read_power_sensor(self):
        energy_value_import = 0
        energy_value_export = 0
        error_code = 0
        if self.simulated:
            # simulation
            self.power_sensor_value = random.uniform(0,1)*self.max_power       # change this code to a typical signal for a day simulation  
        else:
            # hardware
            [self.power_sensor_value, energy_value_import, energy_value_export, error_code] = self.power_sensor.read()                             # positive: from grid, negative: to grid
        
        return [self.power_sensor_value, energy_value_import, energy_value_export, error_code]      


class heat_pump(device):
    # class for heat pump devices

    def __init__(self, name:str, manufacturer:str, nominal_power:float, simulated:bool, is_smartgridready:bool, bus_type:str, id:str, XML_file:str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id, XML_file)        # initialize base class
        # init parameters
        self.device_type = 'heat_pump'              # set device type to 'heatpump'
        self.prosumer_type = 'consumer'             # set prosumer type to 'consumer'
        self.control_type = 'temperature_control'   # set default control type
        self.level_of_operation = '4_dynamic_setpoint'     # set default SmartgridReady level
        if nominal_power > 0:                 
            self.nominal_power = nominal_power                # typical electrical power consumption (kW)
        # init states
        self.mode = 0                              # initialize mode to 0 (off)
        self.room_temperature = 0                   # initialize room temperature
        self.storage_temperature = 0                # initalize storage temperature
        # init temperature sensors
        self.room_temperature_sensor = None         # room temperature sensor
        self.storage_temperature_sensor = None      # storage temperature sensor


    def add_room_temperature_sensor(self, name:str, manufacturer:str, bus_type:str, id:str, is_smartgridready:bool, XML_file:str):    # add an auxiliary sensor to the device (only 1 power sensor allowed)
        sensor_type = 'room_temperature'
        self.room_temperature_sensor = super().add_aux_sensor(name, manufacturer, sensor_type, bus_type, id, is_smartgridready, XML_file)
        self.room_temperature = 0

    def add_storage_temperature_sensor(self, name:str, manufacturer:str, bus_type:str, id:str, is_smartgridready:bool, XML_file:str):    # add an auxiliary sensor to the device (only 1 power sensor allowed)
        sensor_type = 'storage_temperature'
        self.storage_temperature_sensor = super().add_aux_sensor(name, manufacturer, sensor_type, bus_type, id, is_smartgridready, XML_file)
        self.storage_temperature = 0

    def read_aux_sensors(self):             
        if self.simulated:
            # simulation
            self.room_temperature = random.uniform(0,1)*7+19             # --- random room temperature 19..26 °C --- optimize this code !
            self.storage_temperature = random.uniform(0,1)*25+40         # --- random storage temperature 40..65 °C --- optimize this code !            
            error_code = 0
        else:
            # hardware
            if self.room_temperature_sensor != None:    # external room temperature sensor
                [self.room_temperature, error_code1] = self.room_temperature_sensor.read()
            else:                                       # internal room temperature sensor
                [self.room_temperature, unit, error_code1] = self.smartgridready.read_value('RoomTempCtrl', 'RoomZoneTemp')                                           
            if self.storage_temperature_sensor != None: # external storage temperature sensor
                [self.storage_temperature, error_code2] = self.storage_temperature_sensor.read()
            else:                                       # internal storage temperature sensor
                [self.storage_temperature, unit, error_code2] = self.smartgridready.read_value('DomHotwaterCtrl', 'ActDomHotWaterTemp')
            error_code = error_code1 or error_code2                                             
        return [self.room_temperature, self.storage_temperature, error_code]

    def write_actuator(self):
        super().write_actuator()
        
        # --- add aditional code here, e.g. for different control_types ---

    def add_controller(self, name:str, control_type:str):
        # add a controller object corresponding to the control_type and smartgridready level
        
        self.control_type = control_type    
        if self.control_type == 'temperature_control':
            if (self.level_of_operation == '1_on_off') or (self.level_of_operation == '4_dynamic_setpoint'):
                self.controller = controllers.price_controller(name)
                self.controller.set_params(20, 25, 10, 20)      # set default min/max temp and tarifs
            else:
                print("level of operation not defined for heat pump with temperature control: " + str(self.level_of_operation))        
        elif self.control_type == 'power_control':
            if (self.level_of_operation == '1_on_off') or (self.level_of_operation == '4_dynamic_setpoint'):                     
                self.controller = controllers.excess_controller(name)
                self.controller.set_limit(self.nominal_power)
            elif (self.level_of_operation == '2_sg_ready'):       
                self.controller = controllers.stepwise_excess_controller(name)
                self.controller.set_limits([self.nominal_power, self.nominal_power*1.5, self.nominal_power*2])
            else:
                print("level of operation not defined for heat pump with power_control: " + str(self.level_of_operation))        
        elif self.control_type == 'coverage_control':
            if (self.level_of_operation == '1_on_off'):            
                self.controller = controllers.adaptive_coverage_controller(name)
            else:
                 print("level of operation not defined for heat pump with coverage control: " + str(self.level_of_operation))
        else:
            print("control type not defined for heat pump: " + str(self.control_type))
        
    def calc_controller(self, total_production:float, total_consumption:float, max_production:float, mean_consumption:float):                  
        if self.check_min_time():
            if self.control_type == 'temperature_control':  # price controller
                [mode, output, signal] = self.controller.calc_output(self.room_temperature, total_production, max_production, total_consumption, mean_consumption, self.power_sensor_value, self.nominal_power, True)
            elif self.control_type == 'power_control':  
                [mode, output, signal] = self.controller.calc_output(total_production, total_consumption, mean_consumption)
            elif self.control_type == 'coverage_control':
                self.controller.calc_limit(max_production, mean_consumption, None)  # adaptive limit
                [mode, output, signal] = self.controller.calc_output(total_production, total_consumption, mean_consumption)
        else:
            mode = self.mode                # take old values
            output = self.actuator_value
            signal = 0

        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]

class ev_charger(device):
    # class for elektric vehicle charging stations

    def __init__(self, name:str, manufacturer:str, min_power:float, max_power:float, simulated:bool, is_smartgridready:bool, bus_type:str, id:str, XML_file:str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id, XML_file)        # initialize base class
        self.device_type = 'ev_charger'               # set device type to 'ev_charger'
        self.prosumer_type = 'consumer'             # set prosumer type to 'consumer'
        self.control_type = 'power_control'            # set default control type
        self.level_of_operation = '4_dynamic_setpoint'  # set default SmartgridReady level
        self.min_power = min_power                # minimal electrical power consumption (kW)
        self.max_power = max_power                # maximal electrical power consumption (kW)
        self.nominal_power = 0.5*(min_power+max_power)     # nominal electrical power consumption (kW)
    
    def add_controller(self, name:str, control_type:str):
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
     
    def calc_controller(self, total_production:float, total_consumption:float, max_production:float, mean_consumption:float):
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output(total_production, total_consumption, self.power_sensor_value)
        else:
            mode = self.mode
            output = self.actuator_value
            signal = 0

        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]


class power_to_heat(device):
    # class for power to heat applications, e.g. boilers with electric heaters

    def __init__(self, name:str, manufacturer:str, min_power:float, max_power:float, simulated:bool, is_smartgridready:bool, bus_type:str, id:str, XML_file:str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id, XML_file)        # initialize base class
        self.device_type = 'power_to_heat'               # set device type to 'power_to_heat'
        self.prosumer_type = 'consumer'             # set prosumer type to 'consumer'
        self.control_type = 'power_control'            # set default control type
        self.level_of_operation = '4_dynamic_setpoint'  # set default SmartgridReady level
        self.min_power = min_power                # minimal electrical power consumption (kW)
        self.max_power = max_power                # maximal electrical power consumption (kW)
        self.nominal_power = 0.5*(min_power+max_power)               # set nominal power to max power

    def add_controller(self, name:str, control_type:str):
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
        
    def calc_controller(self, total_production:float, total_consumption:float, max_production:float, mean_consumption:float):
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output(total_production, total_consumption, self.power_sensor_value)
        else:
            mode = self.mode
            output = self.actuator_value
            signal = 0
        
        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]

class household_appliance(device):
    # class for household appliances, e.g. dish washers

    def __init__(self, name:str, manufacturer:str, nominal_power:float, simulated:bool, is_smartgridready:bool, bus_type:str, id:str, XML_file:str):
        super().__init__(name, manufacturer, simulated, is_smartgridready, bus_type, id, XML_file)        # initialize base class
        self.device_type = 'household_appliance'               # set device type
        self.prosumer_type = 'consumer'             # set prosumer type to 'consumer'
        self.control_type = 'coverage_control'            # default control type (e.g.'coverage_control', 'power_control')
        self.level_of_operation = '1_on_off'
        if nominal_power > 0:
            self.nominal_power = nominal_power               # set nominal power 

    def add_controller(self, name:str, control_type:str):
        # add a controller object corresponding to the control_type and smartgridready level
        
        self.control_type = control_type
        if self.control_type == 'coverage_control':
            if self.level_of_operation == '1_on_off':
                self.controller = controllers.coverage_controller(name)            # add a coverage controller object
                self.controller.set_limit(1)        # set limit to 100% solar coverage as default
            else:
                print("level of operation not defined for household applicance: " + str(self.level_of_operation))
        else:
            print("control type not defined for household appliance: " + str(self.control_type))   
        
    def calc_controller(self, total_production:float, total_consumption:float, max_production:float, mean_consumption:float):
        if self.check_min_time():
            [mode, output, signal] = self.controller.calc_output(total_production, total_consumption, self.power_sensor_value)
        else:
            mode = self.mode
            output = self.actuator_value
            signal = 0

        self.mode = mode
        self.actuator_value = output
        return [mode, output, signal]

