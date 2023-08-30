# Generative AI was used for some Code
"""
This file checks the connection to devices,sensors,actuators from the given YAML. Useful for installation of a new system.
"""
import asyncio

import aiohttp

from OpenCEM.cem_lib_auxiliary_functions import parse_yaml
import OpenCEM.cem_lib_components as cem_com

print("Connection Test Garage D.Zogg")
print("-----------------------------")


async def main():
    # parse yaml
    communication_channels_list, actuators_list, sensors_list, controllers_list, devices_list = parse_yaml(
        "yaml/Testaufbau_David_V2.yaml")

    # start pymodbus clients
    for channel in communication_channels_list:
        if channel.type in ["MODBUS_TCP", "MODBUS_RTU"]:
            print(channel.name)
            await channel.client.connect()


    # testing sensor connections
    print("Testing sensors:")
    for sensor in sensors_list:
        # test for power sensors
        if isinstance(sensor, cem_com.PowerSensor):
            try:
                response = await sensor.read_all()
                print(f"Connection on {sensor.name} was successful.\n\rResponse: {response}")
            except Exception as e:
                print(f"Connection on {sensor.name} failed.\n\rException: {e}")

        # test for temperature sensor room
        if isinstance(sensor, cem_com.TemperatureSensorRoom):
            try:
                response = await sensor.read_temperature()
                print(f"Connection on {sensor.name} was successful.\n\rResponse: {response}")
            except Exception as e:
                print(f"Connection on {sensor.name} failed.\n\rException: {e}")

    print("-----------------------------")

    # testing actuators connections
    print("Testing actuators:")
    for actuator in actuators_list:
        # test for relais
        if isinstance(actuator, cem_com.RelaisActuator):
            # write a channel and the read channel states
            try:
                response = await actuator.write_channel(0, "on")
                response = await actuator.read_all_channels()
                print(f"Connection on {actuator.name} was successful.\n\rChannel values: {response}")
            except Exception as e:
                print(f"Connection on {actuator.name} failed.\n\rException: {e}")

    print("-----------------------------")

    # testing device connections
    print("Testing device connections:")
    for device in devices_list:
        # for ev chargers
        if isinstance(device, cem_com.EvCharger):
            # try:
            # read ev charger state
            state = await device.get_ev_state()
            print(f"State ev charger: {state}")
            # enabling and reading loading clearance
            await device.enable_loading_clearance()
            loading_clearance = await device.read_loading_clearance()
            print(f"Loading clearance: {loading_clearance}")
            # reset loading clearance
            await device.disable_loading_clearance()
            # set loading power
            await device.set_loading_power(2)
            # read power usage of ev charger
            response = await device.read_power_sensor()
            print(f"Power: {response[0]} kW")
            print(f"Tests on {device.name} were successful.")
            Eingestellter_Ladestrom = await device.client.read_holding_registers(address=300, count=1, slave=255)
            Power = await device.client.read_input_registers(address=120, count=2, slave=255)
            print(f"Set loading current is: {Eingestellter_Ladestrom.registers[0]/10} A")
            print(f"Power measured (register 300): {Power.registers} ")
             #except Exception as e:
             #   print(f"A test on {device.name} failed. Exception: {e}")

        else:
            # other devices would get tested here...
            # for test installation the ev charger is the only device used with a communication
            pass

        # close running communication clients
    for obj in communication_channels_list:
        if obj.client is not None:
            if isinstance(obj.client, aiohttp.ClientSession):
                await obj.client.close()
            else:
                obj.client.close()


asyncio.run(main())
