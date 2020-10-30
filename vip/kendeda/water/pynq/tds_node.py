import sys
import time
import signal
import statistics

from onewire.bus import OneWireBus
from ds18x20 import DS18X20
from tds_pynq import TDS


class TDS_Node:
	"""
	A class which provides temperature and temperature-adjusted TDS readings.

	The DS18X20 temperature sensor must be wired to the IO0 digital input
	due to constraints in the IP used in the pynq's PL. tds_sensor_pin is the
	analog input pin connected to the TDS sensor.
	"""
	def __init__(self, tds_sensor_pin):
		## Get an instance of the 1-Wire bus
		self.bus = OneWireBus.get_instance()
		overlay = OneWireBus.OVERLAY    ## Reference to the custom Overlay object containing our 1-Wire controller IP

		## Get the TDS sensor
		self.tds_sensor = TDS(tds_sensor_pin, overlay)

		## Search the OneWire bus for all found temperature sensors (either DS18B20 or DS18S20 sensors)
		## (bus.search() returns a list of device addresses, represented as OneWireAddress objects)
		## (see: https://github.com/VicerExciser/PYNQ-OneWire/blob/master/onewire/bus.py#L22)
		self.temp_sensors = []
		for device_address in self.bus.search():
			found_device = DS18X20(self.bus, device_address)
			self.temp_sensors.append(found_device)

		if len(self.temp_sensors) == 0:
			print("[TDS_Node]  ERROR: No temperature sensors found on the 1-Wire bus!")
			## TODO: Should continue...? Or exit if temperature compensation is not possible?

		## Set handlers for asynchronous events (e.g., a KeyboardInterrupt)
		signal.signal(signal.SIGINT, self.handle_signal)
		signal.signal(signal.SIGTERM, self.handle_signal)
		

	def get_temperature(self):
		if len(self.temp_sensors) == 0:
			## TODO: Handle case where no temperature sensors were found
			EXAMPLE_DEFAULT_TEMP_FOR_TDS_COMPENSATION = 20.0
			return EXAMPLE_DEFAULT_TEMP_FOR_TDS_COMPENSATION

		temps = [sensor.temperature for sensor in self.temp_sensors]   ## List of all temperature readings
		avg_temp = statistics.mean(temps)
		return round(avg_temp, 4)   ## Return the average temperature read from all sensors, rounded to 4 decimals


	def get_raw_tds_voltage(self):
		return self.tds_sensor.read_vtg()


	def get_tds(self, temp=None, raw_voltage=None):
		"""
		Return TDS reading adjusted for temperature.
		"""
		if temp is None:
			temp = self.get_temperature()
		if raw_voltage is None:
			raw_voltage = self.get_raw_tds_voltage()

		voltage = raw_voltage / (1.0 + (0.02 * (temp - 25.0)))
		tds = ((133.42 * (voltage**3)) - (255.86 * (voltage**2)) + (857.39 * voltage)) * 0.5
		return round(tds, 4)


	def handle_signal(self, signum, stack):
		print(f"\n < signal received ({signum}) > \n")
		## TODO: Take care of / clean up anything necessary here before exiting program
		## ...
		sys.exit(0)


def main():
	node = TDS_Node(1)

	while True:
		temperature = node.get_temperature()
		print(f"Temperature:  {temperature} C")

		voltage = node.get_raw_tds_voltage()
		print(f"Voltage:  {voltage} V")

		tds = node.get_tds(temp=temperature, raw_voltage=voltage)
		print(f"TDS:  {tds} PPM\n")

		time.sleep(2)


if __name__ == "__main__":
	main()
