import adafruit_bme680
import math
from util.util import rh_to_abs_humidity 

# RV = 461.5  ## specific gas constant for water vapor

class BME680():
	""" Wrapper class for an Adafruit BME680 sensor breakout. """
	I2C_ADDR = 0x77

	def __init__(self, bus, use_i2c=True, stabilize_humidity=False):
		""" Can use I2C or SPI to communicate with a Raspberry Pi.

		Note that the internally created Adafruit_BME680 object requires that 
		its `sea_level_pressure` attribute be set after instantiation to match
		the sensor location's barometric pressure (hPa) at sea level.
		This hPa value for Atlanta can be found here: 
			https://w1.weather.gov/data/obhistory/KATL.html
			[ Subnote: 1 millibar (mb) == 1 hectoPascal (hPa) ]

		Args:
			bus (busio.I2C or busio.SPI): Either an I2C connection if the 
				`use_i2c` flag is set to True, else an SPI connection.
			use_i2c: Boolean, defaults True for an I2C connection between the 
				board and the BME680 sensor breakout. If False and SPI is 
				preferred, the CS0 chip select pin is assumed, as well as a
				default baudrate of 100000.
			stabilize_humidity: Boolean, set to True to have the sensor 
				continuously poll its relative humidity upon initialization
				until the readings stabilize/converge

		Raises:
			ValueError: If no connected BME680 sensor is found
		"""
		if use_i2c:
			self.bme = adafruit_bme680.Adafruit_BME680_I2C(bus)
		else:
			self.bme = adafruit_bme680.Adafruit_BME680_SPI(spi, cs=0)

		## Default: A rough average of previous month's recorded air 
		## pressure measurements in Atlanta (as of March, 2020)
		self.bme.sea_level_pressure = 1029.9

		if stabilize_humidity:
			self._stabilize()

	def _stabilize(self):
		from time import sleep 
		print("[BME680] Stabilizing humidity ...")
		prev = 100.1
		hum = self.get_humidity()
		while hum < prev:
			prev = hum 
			sleep(0.5)
			hum = self.get_humidity()
		print("[BME680] Humidity stabilized at {:4.2f}%".format(hum))

	def get_temperature(self):
		""" Returns the compensated temperature in degrees celsius. """
		return round(self.bme.temperature, 2) 	## Units: °C

	def get_pressure(self):
		""" Returns the barometric pressure in hectoPascals. """
		return round(self.bme.pressure, 2) 		## Units: hPa

	def get_humidity(self):
		""" Returns the current relative humidity in RH %. """
		return round(self.bme.humidity, 2) 		## Units: %

	def get_absolute_humidity(self):
		""" Returns the current absolute humidity (in grams
		per cubic meter) based on the current relative 
		humidity, temperature, and barometric pressure.
		Source: https://planetcalc.com/2167/
		"""
		rh = self.get_humidity()
		t = self.get_temperature()
		p = self.get_pressure()
		# eW = self._saturation_vapor_pressure(p, t)
		# e = eW * (rh / 100.0)
		# ah = ((e / (t * RV)) * 10.0) * 1000 ## * 1000 to convert kg/m3 to g/m3
		# return self.bme.abs_humidity 		## Units: g/m3
		return rh_to_abs_humidity(rh, t, p)

	# def _saturation_vapor_pressure(self, p, t):
	# 	""" Source: https://planetcalc.com/2161/ """
	# 	fp = 1.0016 + ((3.15 * 10**(-6)) * p) - (0.074 * (p**(-1)))
	# 	ewt = 6.112 * (math.e ** ((17.62 * t) / (243.12 + t)))
	# 	eW = fp * ewt
	# 	return eW
	
	def get_altitude(self):
		""" Returns the altitude based on current pressure vs. the sea level 
		pressure (sea_level_pressure) which must be configured ahead of time 
		(handled here by the class constructor).
		"""
		return round(self.bme.altitude, 2) 		## Units: meters

	def get_voc(self):
		""" Returns the Volatile Organic Compounds concentration measurement.

		The gas resistance in ohms for the sensor reading is proportional to 
		the amount of VOC particles detected in the air.
		"""
		return round(self.bme.gas, 2) 			## Units: ohms	

	def update_sea_level_pressure(self, val):
		if val > 0:
			self.bme.sea_level_pressure = val
