# OpenCEM main test program
# UNDER CONSTRUCTION...

# Change history:
# 11.05.2022, D. Zogg: project created
# 04.10.2022, D. Zogg: controller types and tarif object added

from operator import truediv
import OpenCEM.cem_lib_components as components
import OpenCEM.cem_lib_controllers as controllers
import os
import pymodbus

print(pymodbus.__version__)

# ----------- initialize system ------------ #

print("initializing...")

# define components
heat_pump = components.heat_pump('heatpump', 'CTA', 3, True, True, 'modbus_tcp', '192.168.0.10', os.path.join('xml_files', 'SGr_HeatPump_Test.xml')) 
ev_charger = components.ev_charger('evcharger', 'Wallbe', 4, 11, True, False, 'modbus_tcp', '192.168.0.11', None)
dishwasher = components.household_appliance('dishwasher','Miele', 2, True, False, None, None, None)
central_meter = components.central_power_meter('meter', 'ABB', 30, True, False, None, None, None)
pv_plant = components.pv_plant('pvplant','SolarEdge',30, True, False, None, None, None)

# define sensors and actuators
heat_pump.add_power_sensor('heat_pump_power', 'ABB', 'modbus_rtu', '1', True, False, None)
heat_pump.add_room_temperature_sensor('heat_pump_room_temperature', 'Thermokon', 'modbus_rtu', '2', False, None)         
heat_pump.add_storage_temperature_sensor('heat_pump_storage_temperature', 'Thermokon', 'modbus_rtu', '3', False, None)      
heat_pump.add_actuator('heat_pump_actuator', 'Eltako', 'single_relais', '3', False, None)

ev_charger.add_power_sensor('ev_charging_power', 'ABB', 'modbus_rtu', '10', True, False, None)

dishwasher.add_power_sensor('dishwasher_power', 'ABB', 'modbus_rtu', '11', True, False, None)
dishwasher.add_actuator('dishwasher_actuator', 'Eltako', 'single_relais', '12', False, None)

central_meter.add_power_sensor('central_power', 'ABB', 'modbus_rtu', '20', True, False, None)

pv_plant.add_power_sensor('pv_power', 'ABB', 'modbus_rtu', '21', True, False, None)

# define tarif info
tarif = components.tarif_info(10, 20)   

# define controllers
heat_pump.add_controller('heat_pump_controller', 'temperature_control')
heat_pump.controller.set_params(20, 25, tarif.solar_tarif, tarif.grid_tarif)     # optional: set min/max room temperature and tarifs

ev_charger.add_controller('ev_charge_controller', 'power_control')
#ev_charger.controller.set_limit(4)    # optional: set power limit in kW to switch on

dishwasher.add_controller('dishwasher_controller', 'coverage_control')
#dishwasher.controller.set_limit(1)      # optional: set absolute limit for solar coverage to switch on (1 = 100%)
      
# store components in list
cmp_list = (central_meter, pv_plant, heat_pump, ev_charger, dishwasher)

# main loop
# TODO: replace with threading scheme

i = 0                   # set comp idx to 0
max_production = 0      # reset max production
total_mean_consumption = 0 # reset total mean consumption
forgetting_factor = 0.1     # forgetting factor for recursive calculation total mean consumption
print("starting main loop...")
running = True
while running:
    i += 1            # increase comp idx TODO: replace with random sequence
    if i >= len(cmp_list): i = 0
    component = cmp_list[i]
    print("--- cycle component index = " + str(i) + " name = " + component.name + " ---")

    # read power sensor values from pv plants and calculate total production
    total_production = 0
    for cmp in cmp_list:
        [power_sensor_value, energy_value_import, energy_value_export, error_code] = cmp.read_power_sensor()
        if isinstance(cmp,components.pv_plant):
            total_production = total_production + power_sensor_value
    txt = "total production (kW) = {:.2f}"
    print(txt.format(total_production))
    if total_production > max_production: max_production = total_production     # --- optimize this code for 24h maximum with reset ---
    
    # read power sensor value from central power meter and calculate total consumption
    total_consumption = 0
    for cmp in cmp_list:
        [power_sensor_value, energy_value_import, energy_value_export, error_code] = cmp.read_power_sensor()   
        if isinstance(cmp,components.central_power_meter):
            total_consumption = total_production + power_sensor_value
    txt = "total consumption (kW) = {:.2f}"
    print(txt.format(total_consumption))
    total_mean_consumption = forgetting_factor*total_mean_consumption + (1-forgetting_factor)*total_consumption         # recursive calc of total mean consumption

    # read sensor values from actual device
    component = cmp_list[i]
    [own_power, energy_value_import, energy_value_export, error_code] = component.read_power_sensor()
    txt = "own power (kW) = {:.2f}"
    print(txt.format(own_power))
    aux_sensors = component.read_aux_sensors()
    print("aux sensors = " + str(aux_sensors))

    # correct total consumption by nominal power of waiting components in order to avoid simultaneous switching
    corrected_consumption = total_consumption
    for cmp in cmp_list:
        if cmp.state == 'waiting':
            corrected_consumption = corrected_consumption + cmp.nominal_power

    # calculate controller output for actual device
    [mode, output, signal] = component.calc_controller(total_production, corrected_consumption, max_production, total_mean_consumption)
    print("controller mode = " + str(mode) + " output = " + str(output) + " signal = " + str(signal))

    # write actuator values for actual device
    component.write_actuator()

    # --- for testing only ---
    ans = input("next cycle (<y>/n)? ")
    running = (ans == 'y') or (ans == '')
        
        
    
    



