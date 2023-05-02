from sgr_library.generic_interface import GenericInterface

import asyncio

if __name__ == "__main__":

  async def test_loop():
    print('start loop')

    # We instanciate a second interface object with a restapi xml.
    config_file_rest = 'lehmann.ini'
    interface_file_rest = 'xml_files/SGr_04_XXXX_LEHMANN_SmartChargeControllerV0.2.0.xml'
    restapi_component = GenericInterface(interface_file_rest, config_file_rest)
    await restapi_component.authenticate()

    # We create a loop where we request a datapoint with a getval of our restapi 
    # component and a datapoint with a getval of our modbus component.
    while True:
        value = await restapi_component.getval('ActivePowerAC', 'ActivePowerACtot')
        print(value)
        await asyncio.sleep(10)

        #you could do the same funciton with a asyncio gather functions if you 
        #want to get the variables "concurrently".

  try:
      asyncio.run(test_loop())
  except KeyboardInterrupt:

      # Here we have to close all the sessions...
      # We have to think if we want to open a connection and close it for
      # every getval, or we just leave the user do this.
      print("done")