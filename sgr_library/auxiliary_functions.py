import configparser
import re
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, Dict, Any, Iterable
from .data_classes.ei_modbus.sgr_modbus_eidevice_frame import SgrModbusDataPointType, SgrModbusDeviceFrame
from .exceptions import DataPointException, FunctionalProfileException

from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser


# Read XML file, replace variables form config file and return xml as string
def xml_to_string(xml_file:str, config_file:str):
    xml_string = ""
    with open(xml_file, 'r') as file:
        xml_string = file.read()

    parser = configparser.ConfigParser()
    parser.read(config_file)
    for section in parser.sections():
        for(key, val) in parser.items(section):
            pattern = re.compile(r'\{\{\s*' + re.escape(key) + r'\s*\}\}', re.IGNORECASE)
            xml_string = re.sub(pattern, val, xml_string)

    return xml_string

def get_protocol(xml_string:str) -> str:
    """
    Searches for protocol type in xml file
    :return: protocol type string
    """
    root = ET.fromstring(xml_string)
    element = root.tag
    protocol_type = element.split('}')[1]
    return protocol_type


def find_dp(root, fp_name: str, dp_name: str) -> Optional[SgrModbusDataPointType]:
    """
    Searches the datapoint in the root element.
    :param root: The root element created with the xsdata parser
    :param fp_name: The name of the funcitonal profile in which the datapoint resides
    :param dp_name: The name of the datapoint
    :returns: The datapoint element found in root, if not, returns None.
    """
    fp = next(filter(lambda x: x.functional_profile.profile_name == fp_name, root.fp_list_element), None)
    if fp:
        dp = next(filter(lambda x: x.data_point.datapoint_name == dp_name, fp.dp_list_element), None)
        if dp:
            return dp
        raise DataPointException(f"Datapoint {dp_name} not found in functional profile {fp_name}.")
    raise FunctionalProfileException(f"Functional profile {fp_name} not found in XML file.")

def get_modbusInterfaceSelection(xml_file: str) -> str:
    """
    Searches for selected Modbus Interface in XML file and returns it
    return: possible values :
      RTU,
      TCP/IP,
      UDP/IP,
      RTU-ASCII,
      TCP/IP-ASCII,
      UDP/IP-ASCII
    """
    parser = XmlParser(context=XmlContext())
    root = parser.parse(xml_file, SgrModbusDeviceFrame)

    return (root.modbus_interface_desc.modbus_interface_selection.value)
