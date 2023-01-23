from xml.dom.minidom import Element

from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser

from sgr_library.data_classes.ei_modbus import SgrModbusDeviceFrame, SgrModbusDataPointType
from sgr_library.modbus_interface import SgrModbusInterface
from sgr_library.restapi_interface import RestapiInterface
from sgr_library.modbusRTU_interface import SgrModbusRtuInterface
import os
import configparser
import xml.etree.ElementTree as ET


def get_protocol(xml_file: str) -> str:
    """
    Searches for protocol type in xml file
    :return: 
    """
    root = ET.parse(xml_file).getroot()
    element = root.tag
    protocol_type = element.split('}')[1]
    return protocol_type


def get_modbusInterfaceSelection(xml_file: str) -> str:
    """
    Searches for selected Modbus Interface in XML file
    """
    parser = XmlParser(context=XmlContext())
    root = parser.parse(xml_file, SgrModbusDeviceFrame)

    return (root.modbus_interface_desc.modbus_interface_selection.value)


class GenericInterface(SgrModbusInterface, RestapiInterface, SgrModbusRtuInterface):

    def __init__(self, xml_file: str, config=None) -> None:
        """
        Chooses which interface to use from xml file data.
        :param xml_file: Name of the xml file to parse in chosen interface
        """
        self.protocol_type = get_protocol(xml_file)
        self.modbus_protocol = ['SGrModbusDeviceFrame', 'SGrModbusDeviceDescriptionType']
        self.restapi_protocol = ['SGrRESTAPIDeviceDescriptionType']
        self.interface_type = ""  # The type of the Interface used

        if self.protocol_type in self.modbus_protocol:
            if get_modbusInterfaceSelection(xml_file) == "RTU":  # Todo if RTU choose modbusRTU_interface?
                SgrModbusRtuInterface.__init__(self, xml_file)
                self.interface_type = "RTU"
            else:
                SgrModbusInterface.__init__(self,
                                            xml_file)  # Todo maybe smarter to have a parameter for tcp/rtu? or parse the XML before and get value <sgr:modbusInterfaceSelection> = RTU
                self.interface_type = "TCP"
        elif self.protocol_type in self.restapi_protocol:
            RestapiInterface.__init__(self, xml_file, config_file)
            self.interface_type = "REST"

    def getval(self, *parameter) -> tuple:
        if self.protocol_type in self.modbus_protocol:
            return (SgrModbusInterface.getval(self, *parameter))
        elif self.protocol_type in self.restapi_protocol:
            return (RestapiInterface.getval(self, *parameter))

    def get_multiplicator(self, dp: SgrModbusDataPointType) -> int:
        match self.interface_type:
            case "RTU":
                return SgrModbusRtuInterface.get_multiplicator(self, dp)
            case "TCP":
                return SgrModbusInterface.get_multiplicator(self, dp)
            case "REST:":
                raise NotImplementedError

    def get_power_10(self, dp: SgrModbusDataPointType)->int:
        match self.interface_type:
            case "RTU":
                return SgrModbusRtuInterface.get_power_10(self, dp)
            case "TCP":
                return SgrModbusInterface.get_power_10(self, dp)
            case "REST:":
                raise NotImplementedError

    def get_unit(self, dp: SgrModbusDataPointType):
        match self.interface_type:
            case "RTU":
                return SgrModbusRtuInterface.get_unit(self, dp)
            case "TCP":
                return SgrModbusInterface.get_unit(self, dp)
            case "REST:":
                raise NotImplementedError

    def get_pymodbus_client(self):
        match self.interface_type:
            case "RTU":
                return SgrModbusRtuInterface.get_pymodbus_client(self)
            case "TCP":
                raise NotImplementedError
            case "REST:":
                raise NotImplementedError

if __name__ == "__main__":
    energy_monitor_config_file_path_default = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'config_CLEMAPEnMon_ressource_default.ini'
    )
    config_file = configparser.ConfigParser()
    config_file.read(energy_monitor_config_file_path_default)

    interface_file = 'SGr_04_0018_CLEMAP_EIcloudEnergyMonitorV0.2.1.xml'
    sgr_component = GenericInterface(interface_file, config_file)
    value = sgr_component.getval('ActivePowerAC', 'ActivePowerACtot')
    print(value)

    interface_file2 = 'SGr_HeatPump_Test.xml'
    sgr_component2 = GenericInterface(interface_file2)
    dp = sgr_component2.find_dp('HeatPumpBase', 'HPOpState')
    sgr_component2.get_device_profile()

    value2 = sgr_component2.getval('HeatPumpBase', 'HPOpState')
    print(value2)
