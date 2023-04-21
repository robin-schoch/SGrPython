from sgr_library.modbus_interface import SgrModbusInterface
from sgr_library.restapi_client_async import SgrRestInterface
from sgr_library.generic_interface import GenericInterface

import asyncio
from sgr_library.auxiliary_functions import get_protocol,get_modbusInterfaceSelection
from sgr_library.modbusRTU_interface_async import SgrModbusRtuInterface

if __name__ == "__main__":

  async def test_loop():
    print('start loop')

    # We instanciate a second interface object with a restapi xml.
    config_file_rest = 'lehmann.ini'
    interface_file_rest = 'SGr_04_XXXX_LEHMANN_SmartChargeControllerV0.2.0.xml'
    restapi_component = GenericInterface(interface_file_rest, config_file_rest)
    await restapi_component.authenticate()

    while True:
            
      value = await restapi_component.getval('ActivePowerAC', 'ActivePowerACtot')
      print(value)
      await asyncio.sleep(10)

  try:
      asyncio.run(test_loop())
  except KeyboardInterrupt:

      # Here we have to close all the sessions...
      # We have to think if we want to open a connection and close it for
      # every getval, or we just leave the user do this.
      print("done")