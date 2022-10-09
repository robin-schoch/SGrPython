# test program for sgr_library
# 09.10.2022, D. Zogg    

import os
from sgr_library.generic_interface import GenericInterface

interface_file2 = os.path.join('xml_files', 'SGr_HeatPump_Test.xml')
sgr_component2 = GenericInterface(interface_file2)
dp = sgr_component2.find_dp('HeatPumpBase', 'HPOpState')
sgr_component2.get_device_profile()