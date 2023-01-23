import time
from pprint import pprint
from OpenCEM.cem_lib_components import shelly_temp_and_hum_sensor, shelly_power_sensor
from OpenCEM.cem_lib_components import shelly_relais_actuator
"""
V1.0 created and documented on 26.12.2022 by  S. Ferreira

This script shows the basic usage of the implementation of the the shelly devices. 
Communication via Shelly cloud is limited to one request per second. 
The authentication information is located in cem_lib_components.py under shelly_api_key and shelly_server_address
"""


# Temperature Sensor Test
mySensor = shelly_temp_and_hum_sensor("701f93")
temp, timeStamp, valid = mySensor.read_temperature()
print(f"Temperature is: {temp} C°")

# Relay 2PM over local ip
myRelais = shelly_relais_actuator("192.168.1.112", 2, is_logging=False)

# turn channel off
myRelais.write_channel(1, "off")
time.sleep(3)   # sleep is to check if the relay is really changing the state
# turn channel on
myRelais.write_channel(1, "on")
# read one channel state over local ip
response = myRelais.read_channel(0)
print(f"state of channel 0: {response}")
# read all channels over local ip
response = myRelais.read_all_channels()
print(f"state of all channels: {response}")

time.sleep(3)

# Relay 2PM Test over Shelly cloud (1 request per second possible)
myRelais_cloud = shelly_relais_actuator("ec62608219d4", 2, bus_type="SHELLY_CLOUD")
# turn channel on
myRelais_cloud.write_channel(1, "on")
time.sleep(3)
# turn channel off
myRelais_cloud.write_channel(1, "off")
time.sleep(1)
# read all channels over Shelly cloud. It is not possible to read single channel values over cloud.
response = myRelais.read_all_channels()
print(f"state of all channels: {response}")


# Shelly relay 4PM
myRelais = shelly_relais_actuator("192.168.1.114", 4)
myRelais.write_channel(0, "on")
print(f"state of all channels: {myRelais.read_all_channels()}")
print(f"state of channel 0: {myRelais.read_channel(0)}")

# Shelly 3EM
myPowerSensor = shelly_power_sensor("192.168.1.113")
print(f"Power: {myPowerSensor.read_power()}")
print(f"Import: {myPowerSensor.read_energy_import()}")
print(f"Export: {myPowerSensor.read_energy_export()}")

# Shelly 3EM over cloud (use read_all() for communication over cloud)
myPowerSensorCloud = shelly_power_sensor("349454756b89", bus_type="SHELLY_CLOUD")
(power, energy_import, energy_export) = myPowerSensorCloud.read_all()
print(f"Power: {power}")
print(f"Import: {energy_import}")
print(f"Export: {energy_export}")



