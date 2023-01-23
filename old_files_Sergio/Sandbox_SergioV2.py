import time
from OpenCEM.cem_lib_components import power_sensor, OpenCEM_RTU_client

#first smart grid ready Components, then the other ones

AbbUni = power_sensor(is_smartgridready=True, id=1, has_energy_import=True, has_energy_export=False, XML_file="../xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_Uni.xml")
#AbbBi = power_sensor(is_smartgridready=True, id=2, has_energy=True, XML_file="xml_files/SGr_04_0016_xxxx_ABBMeterV0.2.1_BI.xml")

RTU_global_client = OpenCEM_RTU_client(global_client=AbbUni.get_pymodbus_client()).get_OpenCEM_global_RTU_client()
#RTU_global_client = OpenCEM_RTU_client().get_OpenCEM_global_RTU_client()

AbbBi = power_sensor(is_smartgridready=False, id=2, has_energy_import=True, has_energy_export=True, name="B23 312-100", manufacturer="ABB", bus_type="RTU", client=RTU_global_client)

AbbBi.add_RTU_Power_entry(23316, 2, "WATTS", "int32", 0.01)
AbbBi.add_RTU_EnergyImport_entry(20480, 4, "KILOWATT_HOURS", "int64_u", 0.01)
AbbBi.add_RTU_EnergyExport_entry(20484, 4, "KILOWATT_HOURS", "int64_u", 0.01)

time.sleep(1)

print(AbbUni.read_power())
print(AbbUni.read_energy_import())

print(AbbBi.read_power())
print(AbbBi.read_energy_import())
print(AbbBi.read_energy_export())





