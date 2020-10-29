import time
import statistics

from onewire.bus import OneWireBus
from ds18x20 import DS18X20
from tds_pynq import TDS

# Ask Austin about the import error handling he did in ds18x20_simpletest.py

class TDS_Node:
	"""
	A class which provides temperature and temperature-adjusted TDS readings.

	The DS18X20 temperature sensor must be wired to the IO0 digital input
	due to constraints in the IP used in the pynq's PL. tds_sensor_pin is the
	analog input pin connected to the TDS sensor.
	"""
	def __init__(self, tds_sensor_pin):
		# Get an instance of the 1-Wire bus
		self.bus = OneWireBus.get_instance()
		overlay = OneWireBus.OVERLAY    ## Reference to the custom Overlay object containing our 1-Wire controller IP

		# Get the TDS sensor
		self.tds_sensor = TDS(tds_sensor_pin, overlay)

		# How should I handle multiple sensors? How would we differentiate between a temp sensor and another 1-wire sensor?
		# Do we just assume none are connected?
		# For now, using first found
		# temp_sensor = DS18X20(bus, bus.search()[0])

		## Search the OneWire bus for all found temperature sensors 
		## (bus.search() returns a list of device addresses, represented as OneWireAddress objects)
		## (see: https://github.com/VicerExciser/PYNQ-OneWire/blob/master/onewire/bus.py#L22)
		self.temp_sensors = []
		for device_address in self.bus.search():
			found_device = DS18X20(self.bus, device_address)
			self.temp_sensors.append(found_device)

		if len(self.temp_sensors) == 0:
			print("[TDS_Node]  ERROR: No temperature sensors found on the 1-Wire bus!")
			## Should continue...? Or exit if temperature compensation is not possible?
		

	def get_temperature(self):
		# return temp_sensor.temperature
		temps = [sensor.temperature for sensor in self.temp_sensors]   ## List of all temperature readings
		avg_temp = statistics.mean(temps)
		return round(avg_temp, 4)   ## Return the average temperature read from all sensors, rounded to 4 decimals


	def get_raw_tds_voltage(self):
		return self.tds_sensor.read_vtg()


	def get_tds(self, temp=None, raw_voltage=None):
		"""
		Return TDS reading adjusted for temperature.
		"""
		# voltage = tds_sensor.read_vtg()/(1.0+(0.02*(temp_sensor.temperature-25.0)))
		# return (133.42*voltage*voltage*voltage - 255.86*voltage*voltage + 857.39*voltage)*0.5
		if temp is None:
			temp = self.get_temperature()
		if raw_voltage is None:
			raw_voltage = self.get_raw_tds_voltage()

		voltage = raw_voltage / (1.0 + (0.02 * (temp - 25.0)))
		tds = ((133.42 * (voltage**3)) - (255.86 * (voltage**2)) + (857.39 * voltage)) * 0.5
		return round(tds, 4)


def main():
	node = TDS_Node(1)
	while True:
		# print("Temperature: ", node.get_temperature())
		# print("Voltage: ", node.get_raw_tds_voltage())
		# print("TDS: ", node.get_tds())

		temperature = node.get_temperature()
		print(f"Temperature:  {temperature} C")

		voltage = node.get_raw_tds_voltage()
		print(f"Voltage:  {voltage} V")

		tds = node.get_tds(temp=temperature, raw_voltage=voltage)
		print(f"TDS:  {tds} PPM\n")

		time.sleep(2)


if __name__ == "__main__":
	main()
