# Generative AI was used for some Code

import asyncio
import datetime
import logging
import os
import socket
import urllib
import aiohttp.client
import yaml
from OpenCEM.cem_lib_components import CommunicationChannel, ShellyRelais, ShellyPowerSensor, PowerSensor, \
    ShellyTempSensor, ShellyTrvTempSensor, CentralPowerMeter, HeatPump, HouseholdAppliance, \
    PowerToHeat, PvPlant, EvCharger, TemperatureSensorStorage, TemperatureSensorRoom, RelaisActuator, \
    RemainingConsumption
from OpenCEM.cem_lib_controllers import ExcessController, StepwiseExcessController, DynamicExcessController, \
    coverage_controller, PriceController
from sgr_library.modbusRTU_interface_async import SgrModbusRtuInterface
from sgr_library.modbusRTU_client_async import SGrModbusRTUClient


def get_local_ip():
    # gets the own ip-address and returns it
    try:
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Use a dummy address to get the local IP address
        s.connect(("8.8.8.8", 80))

        # Get the local IP address
        local_ip = s.getsockname()[0]

        return local_ip
    except Exception as e:
        print("Error:", e)
        return None


IP_address = get_local_ip()     # get the local ip


def create_webpage_dict(devices_list: list) -> dict:
    """
    This function will create a dict with the important information of the devices. Used for the GUI.
    :param devices_list:
    :return: dict with device information. Will be sent later tothe GUI
    """
    return_dict = {}
    devices_dict_list = []
    return_dict["timestamp"] = datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")

    for device in devices_list:
        device_dict = {}
        try:
            device_dict["name"] = device.name
            device_dict["power"] = device.power_sensor_power
            device_dict["type"] = device.device_type
            device_dict["status"] = device.state
            if device.room_temperature_sensor is not None:
                device_dict["room_temperature"] = device.room_temperature
            if device.storage_temperature_sensor is not None:
                device_dict["storage_temperature"] = device.storage_temperature
            devices_dict_list.append(device_dict)
            if isinstance(device, EvCharger):
                device_dict["ev_state"] = device.ev_state
        except Exception:
            raise NotImplementedError("Error building the dictionary")

    return_dict["devices_list"] = devices_dict_list

    return return_dict


async def send_data_to_webpage(data_dict: dict, session):
    """
    Sends a dict to the /update Endpoint of the Webserver. Used to update the data displayed on the GUI
    :param data_dict: dict created with create_webpage_dict()
    :param session:
    :return:
    """

    url = f'http://{IP_address}:8000/update'

    try:
        max_time_out = aiohttp.client.ClientTimeout(total=3)  # max allowed timeout for a request
        async with session.post(url, json=data_dict, timeout=max_time_out) as response:
            status_code = response.status
        if status_code == 200:
            print('Message sent successfully')
        else:
            print('Failed to send message')
    except asyncio.TimeoutError:
        logging.error("System was not able to send data to the GUI.")


async def check_OpenCEM_shutdown(session):
    """
    Will check if a shutdown of the OpenCEM was requested on the GUI
    :param session: aiohttp session
    :return: True for shutdown, False for no shutdown
    """
    url = f'http://{IP_address}:8000/shutdown_requested'

    try:
        max_time_out = aiohttp.client.ClientTimeout(total=2)  # max allowed timeout for a request
        async with session.get(url, timeout=max_time_out) as response:
            status_code = response.status
            restart_text = await response.text()

        if status_code == 200:
            if restart_text == "True":
                return True
            else:
                return False
        else:
            print('Failed to request "restart_requested" from endpoint')
    except asyncio.TimeoutError:
        logging.error("No response from GUI in time.")
    # return false when request failed
    return False


def search_object_by_id(object_list, search_id):
    # returns the object of a list, that matches the id
    for obj in object_list:
        if obj.OpenCEM_id == search_id:
            return obj
    return None  # Return None if the object is not found


def add_sensor_actuator_controller_by_id(device, sensor_id_list=None, actuator_id=None, controller_id=None,
                                         sensors_list=None, actuators_list=None, controllers_list=None,
                                         actuator_channels=None, channel_config=None):
    """
    This function adds sensors, actuators or a controller to device
    :param actuator_channels: the channel numbers of the actuator that the device uses
    :param channel_config: the configuration of the actuator channels to get a certain mode
    :return:
    """

    # add all the sensors
    for sensor_id in sensor_id_list:

        if sensor_id is not None and sensors_list is not None:
            sensor = search_object_by_id(sensors_list, sensor_id)
            if isinstance(sensor, PowerSensor):
                device.add_power_sensor(sensor)
            if isinstance(sensor, TemperatureSensorRoom):
                device.add_room_temperature_sensor(sensor)
            if isinstance(sensor, TemperatureSensorStorage):
                device.add_storage_temperature_sensor(sensor)

    # add an actuator
    if actuator_id is not None and actuators_list is not None and actuator_channels is not None:
        actuator = search_object_by_id(actuators_list, actuator_id)
        if isinstance(actuator, RelaisActuator):
            device.add_actuator(actuator, actuator_channels)
            if channel_config is not None:
                device.set_mode_config(channel_config)

    # add a controller
    if controller_id is not None and controllers_list is not None:
        controller = search_object_by_id(controllers_list, controller_id)
        device.add_controller(controller)


async def download_xml(uuid):
    """
    This function will download the XML for a SGr Device from the CEM-Cloud and save it as uuid.xml
    :param uuid: the uuid of the SGr-File (given by CEM-Cloud)
    :return:
    """
    url = f"https://cem-cloud-p5.ch/api/smartgridready/{uuid}"
    async with aiohttp.request('GET', url) as response:
        status_code = response.status
        xml_file = await response.read()  # response is xml in bytes

    # request successful
    if status_code == 200:
        try:
            # save file
            with open(f"xml_files/{uuid}.xml", "wb") as f:  # write it as bytes
                f.write(xml_file)
                logging.info(f"Downloaded SGr File with uuid:{uuid} successfully.")
                return True
        except EnvironmentError:
            logging.error(f"Error with writing downloaded XML (uuid: {uuid}) to disk")
    else:
        logging.warning(
            f"Download of SGr File failed. Check connection and uuid ({uuid}) of the devices in the field smartGridreadyFileId.")
    return False


async def parse_yaml(path2configurationYaml: str):
    """
    This function reads a configuration yaml, creates instances of devices, sensors, etc. and connects them.
    :param path2configurationYaml: The YAML configuration that should get parsed
    :return: lists for devices, communicationChannels, sensors, actuators, controllers
    """
    with open(path2configurationYaml, "r") as f:
        data = yaml.safe_load(f)

        #vdefine empty lists
        communication_channels_list = []
        actuators_list = []
        sensors_list = []
        controllers_list = []
        devices_list = []

        # parse communication channels
        if data.get("communicationChannels") is not None:

            # parse every communicationChannel from the list
            for communication_channel in data.get("communicationChannels"):
                name = communication_channel["name"]
                type = communication_channel["type"]
                OpenCEM_id = communication_channel["id"]
                extra = communication_channel["extra"]
                communication_channels_list.append(CommunicationChannel(name, OpenCEM_id, type, extra))

        # create Client for HTTP Communication. OpenCEM_id is 1 for this Client
        http_main_client = CommunicationChannel("OpenCEM_HTTP_Client", "1", "HTTP_MAIN", None)
        communication_channels_list.append(http_main_client)

        # hotfix for SGr Library creating multiple clients. now only one global client exists for RTU
        sgr_rtu_client = http_main_channel = next(
            (obj for obj in communication_channels_list if obj.type == "MODBUS_RTU"),
            None)  # returns the MODBUS_RTU communication channel
        if sgr_rtu_client is not None:
            SgrModbusRtuInterface.globalModbusRTUClient = SGrModbusRTUClient("", "", "",
                                                                             client=sgr_rtu_client.client)  # set the global client for SGr RTU Devices

        # parse actuators
        if data.get("actuators") is not None:
            data_actuators = data["actuators"]

            # parse every actuator from the list
            for actuator in data_actuators:
                OpenCEM_id = actuator["id"]
                type = actuator["type"]
                name = actuator["name"]
                manufacturer = actuator["manufacturer"]
                model = actuator["model"]
                smartgridready_XML = actuator.get("smartGridreadyFileId")
                if smartgridready_XML is None:
                    is_smartgridready = False
                else:
                    is_smartgridready = True
                is_logging = actuator["isLogging"]
                communication_id = actuator["communicationId"]
                extra = actuator["extra"]

                # find communication channel
                communication_channel_temp = search_object_by_id(communication_channels_list, communication_id)

                if type == "RELAIS":

                    match model:
                        case "PRO_2PM" | "PRO_4PM":
                            ip_address = extra["address"]
                            n_channels = extra["nChannels"]
                            if communication_channel_temp is not None:
                                comm_type = communication_channel_temp.type
                            if comm_type == "SHELLY_LOCAL":
                                relais = ShellyRelais(device_ip=ip_address, n_channels=n_channels, name=name,
                                                      is_logging=is_logging, client=http_main_client.client,
                                                      OpenCEM_id=OpenCEM_id, bus_type="SHELLY_LOCAL")
                            elif comm_type == "SHELLY_CLOUD":
                                auth_key = communication_channel_temp.shelly_auth_key
                                shelly_server_http = communication_channel_temp.shelly_server_address
                                relais = ShellyRelais(device_ip=ip_address, n_channels=n_channels, name=name,
                                                      is_logging=is_logging, auth_key=auth_key,
                                                      shelly_server_http=shelly_server_http, OpenCEM_id=OpenCEM_id,
                                                      bus_type="SHELLY_CLOUD")
                            else:
                                raise NotImplementedError("Communication type not known.")

                            actuators_list.append(relais)
                        case _:
                            raise NotImplementedError("Relais model not known.")

        # create Sensors
        if data.get("sensors") is not None:
            data_sensors = data["sensors"]

            # parse every sensor from the list
            for sensor in data_sensors:
                OpenCEM_id = sensor.get("id")
                type = sensor.get("type")
                name = sensor.get("name")
                manufacturer = sensor.get("manufacturer")
                model = sensor.get("model")
                smartgridready_XML = sensor.get("smartGridreadyFileId")
                if smartgridready_XML is None:
                    is_smartgridready = False
                else:
                    is_smartgridready = True
                    # check it the field is a local file
                    if os.path.isfile(smartgridready_XML):
                        pass
                    # is uuid
                    else:
                        # check if xml file with this uuid already exists
                        if os.path.exists(f"xml_files/{smartgridready_XML}.xml"):
                            smartgridready_XML = f"xml_files/{smartgridready_XML}.xml"
                        # sgr file with this url doesn't exist yet, so download from cloud will be initiated
                        else:
                            # download sgr file from CEM cloud
                            download_successful = await download_xml(uuid=smartgridready_XML)
                            if download_successful:  # returns true when download was successful
                                smartgridready_XML = f"xml_files/{smartgridready_XML}.xml"
                            # download failed
                            else:
                                logging.warning("OpenCEM was not able to download XML from CEM cloud.")
                                smartgridready_XML = None

                is_logging = sensor.get("isLogging")
                communication_id = sensor.get("communicationId")
                extra = sensor.get("extra")

                # find communication channel
                communication_channel_temp = search_object_by_id(communication_channels_list, communication_id)
                if communication_channel_temp is not None:
                    comm_type = communication_channel_temp.type
                else:
                    raise NotImplementedError

                # decision tree for sensor type
                match type:
                    case "POWER_SENSOR":
                        address = extra["address"]
                        hasEnergyExport = extra["hasEnergyExport"]
                        maxPower = extra["maxPower"]

                        match model:
                            case "ABB B23 312-100" | "ABB B23 112-100":
                                if is_smartgridready:
                                    sensor_temporary = PowerSensor(is_smartgridready=is_smartgridready, id=int(address),
                                                                   has_energy_export=hasEnergyExport,
                                                                   has_energy_import=True, name=name,
                                                                   manufacturer=manufacturer, bus_type=comm_type,
                                                                   is_logging=is_logging, OpenCEM_id=OpenCEM_id,
                                                                   XML_file=smartgridready_XML)
                                else:
                                    sensor_temporary = PowerSensor(is_smartgridready=is_smartgridready, id=address,
                                                                   has_energy_export=hasEnergyExport,
                                                                   has_energy_import=True, name=model,
                                                                   manufacturer=manufacturer, bus_type=comm_type,
                                                                   client=communication_channel_temp.client,
                                                                   is_logging=is_logging, OpenCEM_id=OpenCEM_id)

                            case "3EM":
                                if comm_type == "SHELLY_LOCAL":
                                    sensor_temporary = ShellyPowerSensor(device_ip=address, name=name,
                                                                         is_logging=is_logging,
                                                                         bus_type=comm_type,
                                                                         client=http_main_client.client,
                                                                         OpenCEM_id=OpenCEM_id)
                                elif comm_type == "SHELLY_CLOUD":
                                    auth_key = communication_channel_temp.shelly_auth_key
                                    shelly_server_http = communication_channel_temp.shelly_server_address
                                    sensor_temporary = ShellyPowerSensor(device_ip=address, name=name,
                                                                         is_logging=is_logging,
                                                                         bus_type=comm_type, OpenCEM_id=OpenCEM_id,
                                                                         auth_key=auth_key,
                                                                         shelly_server_http=shelly_server_http)
                                else:
                                    raise NotImplementedError("Communication Type not known.")
                            case _:
                                if is_smartgridready:
                                    sensor_temporary = PowerSensor(is_smartgridready=is_smartgridready, id=int(address),
                                                                   has_energy_export=hasEnergyExport,
                                                                   has_energy_import=True, name=name,
                                                                   manufacturer=manufacturer, bus_type=comm_type,
                                                                   is_logging=is_logging, OpenCEM_id=OpenCEM_id,
                                                                   XML_file=smartgridready_XML)
                                else:
                                    raise NotImplementedError("Power sensor model not known an not SmartGridready.")

                    case "TEMPERATURE_SENSOR_ROOM":
                        address = extra["address"]
                        maxTemp = extra["maxTemp"]
                        minTemp = extra["minTemp"]

                        match model:

                            case "HT":
                                auth_key = communication_channel_temp.shelly_auth_key
                                shelly_server_http = communication_channel_temp.shelly_server_address
                                sensor_temporary = ShellyTempSensor(device_id=address, name=name,
                                                                    is_logging=is_logging,
                                                                    auth_key=auth_key,
                                                                    shelly_server_http=shelly_server_http,
                                                                    OpenCEM_id=OpenCEM_id)

                            case "TRV":
                                if comm_type == "SHELLY_LOCAL":
                                    sensor_temporary = ShellyTrvTempSensor(device_id=address, name=name,
                                                                           is_logging=is_logging,
                                                                           client=http_main_client.client,
                                                                           bus_type="SHELLY_LOCAL",
                                                                           OpenCEM_id=OpenCEM_id)
                                elif comm_type == "SHELLY_CLOUD":
                                    auth_key = communication_channel_temp.shelly_auth_key
                                    shelly_server_http = communication_channel_temp.shelly_server_address
                                    sensor_temporary = ShellyTrvTempSensor(device_id=address, name=name,
                                                                           is_logging=is_logging,
                                                                           auth_key=auth_key,
                                                                           bus_type="SHELLY_CLOUD",
                                                                           shelly_server_http=shelly_server_http,
                                                                           OpenCEM_id=OpenCEM_id)
                                else:
                                    raise NotImplementedError("Communication Type not known.")
                            case _:
                                raise NotImplementedError("Temperature sensor model not known.")

                    case "TEMPERATURE_SENSOR_STORAGE":
                        raise NotImplementedError

                    case _:
                        raise NotImplementedError("Sensor type not known.")

                sensors_list.append(sensor_temporary)

        # parse controllers

        if data.get("controllers") is not None:
            controllers_data = data["controllers"]

            for controller in controllers_data:
                OpenCEM_id = controller["id"]
                type = controller["type"]
                extra = controller["extra"]

                # decision tree for controller type
                match type:
                    case "EXCESS_CONTROLLER":
                        limit = int(extra["limit"])
                        controller_temporary = ExcessController(limit=limit, OpenCEM_id=OpenCEM_id)
                    case "STEPWISE_EXCESS_CONTROLLER":
                        limits = extra["limits"]
                        controller_temporary = StepwiseExcessController(limits=limits, OpenCEM_id=OpenCEM_id)
                    case "DYNAMIC_EXCESS_CONTROLLER":
                        min_limit = extra["limitMin"]
                        max_limit = extra["limitMax"]
                        controller_temporary = DynamicExcessController(min_limit=min_limit, max_limit=max_limit,
                                                                       OpenCEM_id=OpenCEM_id)
                    case "COVERAGE_CONTROLLER":
                        limit = int(extra["limit"])
                        controller_temporary = coverage_controller(limit=limit, OpenCEM_id=OpenCEM_id)
                    case "PRICE_CONTROLLER":
                        gridTarif = extra["gridTarif"]
                        solarTarif = extra["solarTarif"]
                        minState = extra["minState"]
                        maxState = extra["maxState"]
                        controller_temporary = PriceController(min_state=minState, max_state=maxState,
                                                               solar_tarif=solarTarif, grid_tarif=gridTarif,
                                                               OpenCEM_id=OpenCEM_id)
                    case _:
                        raise NotImplementedError("Controller type not known.")

                controllers_list.append(controller_temporary)

        if data.get("devices") is not None:
            devices_data = data["devices"]

            for device in devices_data:
                OpenCEM_id = device.get("id")
                type = device.get("type")
                name = device.get("name")
                manufacturer = device.get("manufacturer")
                model = device.get("model")
                smartgridready_XML = device.get("smartGridreadyFileId")
                if smartgridready_XML is None:
                    is_smartgridready = False
                else:
                    is_smartgridready = True
                is_logging = device.get("isLogging")
                communication_id = device.get("communicationId")
                extra = device.get("extra")

                if communication_id is not None:
                    canCommunicate = True   # True if device can communicate directly for example over Modbus TCP
                    communication_channel_device = search_object_by_id(communication_channels_list, communication_id)   # find the communicationChannel object
                    communication_type_device = communication_channel_device.type
                    client_device = communication_channel_device.client # the client over which the device would communicate
                else:
                    canCommunicate = False

                # decision tree for device types
                match type:
                    case "PV_PLANT":
                        maxPower = extra.get("maxPower")
                        isSimulated = extra["isSimulated"]
                        idPowerSensor = extra.get("idPowerSensor")
                        address = extra.get("address")
                        if canCommunicate:
                            device_temporary = PvPlant(is_smartgridready=is_smartgridready, id=address,
                                                       max_power=maxPower,
                                                       simulated=isSimulated, name=name, manufacturer=manufacturer,
                                                       bus_type=communication_type_device, client=client_device,
                                                       is_logging=is_logging, OpenCEM_id=OpenCEM_id)
                            add_sensor_actuator_controller_by_id(device_temporary, sensors_list=sensors_list,
                                                                 sensor_id_list=[idPowerSensor])

                        else:
                            device_temporary = PvPlant(is_smartgridready=is_smartgridready, id="",
                                                       max_power=maxPower,
                                                       simulated=isSimulated, name=name, manufacturer=manufacturer,
                                                       is_logging=is_logging, OpenCEM_id=OpenCEM_id)
                            add_sensor_actuator_controller_by_id(device_temporary, sensors_list=sensors_list,
                                                                 sensor_id_list=[idPowerSensor])
                    case "CENTRAL_POWER_METER":
                        maxPower = extra.get("maxPower")
                        idPowerSensor = extra.get("idPowerSensor")
                        isSimulated = extra.get("isSimulated")
                        isBidirectional = extra.get("isBidirectional")
                        idPowerSensorTotalConsumption = extra.get("idPowerSensorTotalConsumption")
                        idPowerSensorProduction = extra.get("idPowerSensorProduction")

                        # if device is not bidirectional one sensor for production and one for consumption is needed
                        if not isBidirectional:
                            # generate CentralPowerMeter instance
                            device_temporary = CentralPowerMeter(is_smartgridready=is_smartgridready, id="",
                                                                 max_power=maxPower, simulated=isSimulated, name=name,
                                                                 manufacturer=manufacturer, is_logging=is_logging,
                                                                 OpenCEM_id=OpenCEM_id, isBidirectional=False)

                            # add power sensors (production and total consumption) to the device
                            device_temporary.add_power_sensor_total_consumption(
                                search_object_by_id(sensors_list, idPowerSensorTotalConsumption))
                            device_temporary.add_power_sensor_production(
                                search_object_by_id(sensors_list, idPowerSensorProduction))
                        # bidirectional
                        else:
                            device_temporary = CentralPowerMeter(is_smartgridready=is_smartgridready, id="",
                                                                 max_power=maxPower, simulated=isSimulated, name=name,
                                                                 manufacturer=manufacturer, is_logging=is_logging,
                                                                 OpenCEM_id=OpenCEM_id)
                            add_sensor_actuator_controller_by_id(device_temporary, sensors_list=sensors_list,
                                                                 sensor_id_list=[idPowerSensor])

                    case "HEAT_PUMP":
                        maxPower = extra.get("maxPower")
                        isSimulated = extra.get("isSimulated")
                        idPowerSensor = extra.get("idPowerSensor")
                        address = extra.get(address)
                        idRelais = extra.get("idRelais")
                        nominalPower = extra.get("nominalPower")
                        actuator_channels = extra.get("channels")
                        channelConfig = extra.get("channelConfig")
                        idController = extra.get("idController")
                        idRoomTempSensor = extra.get("idRoomTempSensor")
                        idStorageTempSensor = extra.get("idStorageTempSensor")
                        sensors_ids = [idPowerSensor, idRoomTempSensor, idStorageTempSensor]
                        powerDict = extra.get("powerDict")
                        if canCommunicate:
                            raise NotImplementedError

                        else:
                            device_temporary = HeatPump(is_smartgridready=is_smartgridready, id="",
                                                        simulated=isSimulated,
                                                        nominal_power=nominalPower, name=name,
                                                        manufacturer=manufacturer,
                                                        is_logging=is_logging, OpenCEM_id=OpenCEM_id,
                                                        power_dict=powerDict)
                            add_sensor_actuator_controller_by_id(device=device_temporary, sensor_id_list=sensors_ids,
                                                                 actuator_id=idRelais, controller_id=idController,
                                                                 sensors_list=sensors_list,
                                                                 actuators_list=actuators_list,
                                                                 controllers_list=controllers_list,
                                                                 actuator_channels=actuator_channels,
                                                                 channel_config=channelConfig)

                    case "EV_CHARGER":
                        idPowerSensor = extra.get("idPowerSensor")
                        nominalPower = extra.get("nominalPower")
                        isSimulated = extra.get("isSimulated")
                        address = extra.get("address")
                        idController = extra.get("idController")
                        powerDict = extra.get("powerDict")
                        phases = extra.get("phases")
                        if canCommunicate:

                            if model == "WALLBE_ECO_S":
                                device_temporary = EvCharger(is_smartgridready=is_smartgridready, id=address,
                                                             simulated=isSimulated, nominal_power=nominalPower,
                                                             name=model, manufacturer=manufacturer,
                                                             bus_type=communication_type_device, client=client_device,
                                                             is_logging=is_logging, OpenCEM_id=OpenCEM_id,
                                                             power_dict=powerDict, phases=phases)

                        else:

                            device_temporary = EvCharger(is_smartgridready=is_smartgridready, id="",
                                                         simulated=isSimulated, nominal_power=nominalPower,
                                                         name=name, manufacturer=manufacturer,
                                                         is_logging=is_logging, OpenCEM_id=OpenCEM_id,
                                                         power_dict=powerDict, phases=phases)

                        add_sensor_actuator_controller_by_id(device=device_temporary,
                                                             sensor_id_list=[idPowerSensor],
                                                             actuator_id=None,
                                                             controller_id=idController,
                                                             sensors_list=sensors_list,
                                                             actuators_list=None,
                                                             controllers_list=controllers_list,
                                                             channel_config=None,
                                                             actuator_channels=None)

                    case "POWER_TO_HEAT":
                        idPowerSensor = extra.get("idPowerSensor")
                        nominalPower = extra.get("nominalPower")
                        isSimulated = extra.get("isSimulated")
                        address = extra.get(address)
                        idController = extra.get("idController")
                        idRelais = extra.get("idRelais")
                        actuator_channels = extra.get("channels")
                        channelConfig = extra.get("channelConfig")
                        powerDict = extra.get("powerDict")
                        idRoomTempSensor = extra.get("idTempSensorRoom")
                        if canCommunicate:
                            raise NotImplementedError
                        else:
                            device_temporary = PowerToHeat(is_smartgridready=is_smartgridready, id="",
                                                           simulated=isSimulated, nominal_power=nominalPower,
                                                           name=name, manufacturer=manufacturer,
                                                           is_logging=is_logging, OpenCEM_id=OpenCEM_id,
                                                           power_dict=powerDict)

                        add_sensor_actuator_controller_by_id(device=device_temporary,
                                                             sensor_id_list=[idPowerSensor, idRoomTempSensor],
                                                             actuator_id=idRelais,
                                                             controller_id=idController,
                                                             sensors_list=sensors_list,
                                                             actuators_list=actuators_list,
                                                             controllers_list=controllers_list,
                                                             channel_config=channelConfig,
                                                             actuator_channels=actuator_channels)

                    case "HOUSEHOLD_APPLIANCES":
                        idPowerSensor = extra.get("idPowerSensor")
                        nominalPower = extra.get("nominalPower")
                        isSimulated = extra.get("isSimulated")
                        address = extra.get(address)
                        idController = extra.get("idController")
                        idRelais = extra.get("idRelais")
                        actuator_channels = extra.get("channels")
                        channelConfig = extra.get("channelConfig")
                        powerDict = extra.get("powerDict")
                        if canCommunicate:
                            raise NotImplementedError
                        else:
                            device_temporary = HouseholdAppliance(is_smartgridready=is_smartgridready, id="",
                                                                  simulated=isSimulated, nominal_power=nominalPower,
                                                                  name=name, manufacturer=manufacturer,
                                                                  is_logging=is_logging, OpenCEM_id=OpenCEM_id,
                                                                  power_dict=powerDict)

                        add_sensor_actuator_controller_by_id(device=device_temporary,
                                                             sensor_id_list=[idPowerSensor],
                                                             actuator_id=idRelais,
                                                             controller_id=idController,
                                                             sensors_list=sensors_list,
                                                             actuators_list=actuators_list,
                                                             controllers_list=controllers_list,
                                                             channel_config=channelConfig,
                                                             actuator_channels=actuator_channels)

                    case "REMAINING_CONSUMPTION":
                        deviceSetting = extra.get("deviceSetting")
                        minPower = extra.get("minPower")
                        maxPower = extra.get("maxPower")
                        idPowerSensor = extra.get("idPowerSensor")

                        match deviceSetting:
                            case "SIMULATED":
                                device_temporary = RemainingConsumption(simulated=True, is_logging=is_logging,
                                                                        OpenCEM_id=OpenCEM_id, minPower=minPower,
                                                                        maxPower=maxPower, device_setting=deviceSetting)
                            case "CALCULATED":
                                device_temporary = RemainingConsumption(simulated=False, is_logging=is_logging,
                                                                        OpenCEM_id=OpenCEM_id, minPower=minPower,
                                                                        maxPower=maxPower, device_setting=deviceSetting)
                            case "MEASURED":
                                device_temporary = RemainingConsumption(simulated=False, is_logging=is_logging,
                                                                        OpenCEM_id=OpenCEM_id, minPower=minPower,
                                                                        maxPower=maxPower, device_setting=deviceSetting)
                                add_sensor_actuator_controller_by_id(device_temporary, sensors_list=sensors_list,
                                                                     sensor_id_list=[idPowerSensor])
                            case _:
                                raise ValueError("The given deviceSetting for REMAINING_CONSUMPTION doesn't exit")

                devices_list.append(device_temporary)   # add the device to the list and continue for loop with the next device

        # return all the lists
        return communication_channels_list, actuators_list, sensors_list, controllers_list, devices_list
