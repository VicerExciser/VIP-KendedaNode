## util.py -- Configuration settings, constants, and singleton object instances

import os
import sys
import math
# import busio
# import board
from urllib import request
import subprocess as sp
from statistics import mean 
from datetime import datetime
"""  **Removed the following to avoid coupling & cyclical imports:
try:
	# from util.weather import OpenWeatherMap, network_connected
	# from bme680.bme import BME680
	# from sgp30.sgp import SGP30 
	# import backend.influx_cloud as influx
except ImportError:
	# print("[util] Appending '{}' to PYTHONPATH".format(os.path.join(os.environ['HOME'], 'air')))
	# sys.path.append(os.path.join(os.environ['HOME'], 'air'))
	rootpath = '/'.join(os.getcwd().split('/')[:-1])
	print("[{}] Appending '{}' to PYTHONPATH".format(__file__, rootpath))
	sys.path.append(rootpath)
	# from util.weather import OpenWeatherMap, network_connected
	# from bme680.bme import BME680
	# from sgp30.sgp import SGP30 
	# import backend.influx_cloud as influx
"""

##------------------------------------------------------------------------------
## AIR NODE PROGRAM CONFIGURATIONS:
DRY_RUN = False #True  ## Data will only be published to InfluxDB if this is False
REQUIRE_INTERNET = True  ## Set to False if a connection to the backend is not required
DISPLAY_TEST_MENU = False #True  	 ## For enabling the user to select a test to be run
USE_TEMP_COEFFICIENT = True  ## Compensate for temperature skew to improve reading accuracies
HAVE_NO2_AND_OX = True  	 ## True if this circuit/node incorporates both a NO2-B43F & OX-B431
INCLUDE_VOC = True 
INCLUDE_ECO2 = True
SHOW_DATETIME = True #False
BME_USE_I2C = True 		## Else, will use SPI
STABILIZE_HUMIDITY = True   ## Initialization option for the BME680
INCLUDE_MQ7_CO = False
INCLUDE_AIR_PUMP = True   ## Only True if controlling an air pump with a relay (using Grove relay breakout for testing)

## TODO: Create map that describes what sensors to use in air_node.py

MEASUREMENT_INTERVAL  = 15  #5     ## Seconds
HEADER_PRINT_INTERVAL = 120	 ## Seconds (for tests -- will print column headers once every 2 minutes)
# MAX_RETRIES = 5
AIR_PUMP_PIN = 26  ## BCM pin number of the GPIO driving the air pump's relay

ERROR_LOGFILE = os.path.join(os.environ['HOME'], "node_errors.log")

##------------------------------------------------------------------------------

ADC_I2C_ADDR0 = 0x48 	## ADDR pin -> GND (Default ADS1x15 I2C address, can be overridden using ADDR pin)
ADC_I2C_ADDR1 = 0x49 	## ADDR pin -> VDD
ADC_I2C_ADDR2 = 0x4A 	## ADDR pin -> SDA
ADC_I2C_ADDR3 = 0x4B 	## ADDR pin -> SCL

ADC_PREC = 12	## Either 12-bit or 16-bit precision ADS1x15 ADC breakout

## Choose a gain of 1 for reading voltages from 0 to 4.09V
## Or pick a different gain to change the range of voltages that are read:
##  - 2/3 = +/-6.144V
##  -   1 = +/-4.096V
##  -   2 = +/-2.048V
##  -   4 = +/-1.024V
##  -   8 = +/-0.512V
##  -  16 = +/-0.256V
## See table 3 in the ADS1015/ADS1115 datasheet for more info on gain
ADC_GAIN = 1

A0 = 0
A1 = 1
A2 = 2
A3 = 3

##------------------------------------------------------------------------------
## Global singleton interface for writing data to the InfluxDB backend
"""
try:
	db = influx.DBCloud()
except ValueError as ve:
	print("[util] CRITICAL ERROR FROM influx_cloud.DBCloud instantiation!")
	print("\n{0}:\n\t({1})\n".format(type(ve).__name__, ve))

	## TODO: Decide, should the program terminate if the backend cannot be reached,
	## 	or should data still be collected locally while retrying for Influx Cloud connection...
	if REQUIRE_INTERNET:
		print("DEAD @ {}  (INTERNET CONNECTION IS REQUIRED)".format(get_datetime()))
		sys.exit(2)
	else:
		db = None
"""
##------------------------------------------------------------------------------
"""
# owm = OpenWeatherMap()
i2c = board.I2C() 	## Singleton I2C interface
# i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
"""

"""
bme = None
try:
	if BME_USE_I2C:
		bme = BME680(i2c, stabilize_humidity=STABILIZE_HUMIDITY)
	else:
		bme = BME680(board.SPI(), use_i2c=False, stabilize_humidity=STABILIZE_HUMIDITY)
except ValueError:
	print("[util] No BME680 sensor breakout detected")
	USE_TEMP_COEFFICIENT = False 	## Also indicates the global bme object is None
	bme = None 
else:
	bme.update_sea_level_pressure(owm.get_sea_level_pressure())
"""

"""
sgp = None 
try:
	sgp = SGP30(i2c)
	if bme is not None:
		sgp.set_iaq_humidity(bme.get_absolute_humidity())
except ValueError:
	print("[util] No SGP30 sensor breakout detected")
	INCLUDE_VOC = False
	INCLUDE_ECO2 = False
"""

##------------------------------------------------------------------------------
## UTILITY / HELPER FUNCTIONS:

def network_connected(url="http://www.google.com"):
	try:
		request.urlopen(url).close()
	except Exception as e:
		print("[network_connected] Exception:\n{}".format(e))
		return False
	else:
		return True


def c_to_f(celsius):
	"""
	( X degrees Celsius * 1.8 ) + 32 = Y degrees Fahrenheit
	"""
	return round(((celsius * 1.8) + 32), 2)


def map_voltage_to_percent(voltage, v_min=0, v_max=5, out_min=0, out_max=100):
    """ Map a voltage value (from 0-5V) to a corresponding CO gas concentration percentage (0-100%). """
    return (voltage - v_min) * (out_max - out_min) / (v_max - v_min) + out_min


def best_fit_slope_and_intercept(xs, ys):
	m = (float(((mean(xs)*mean(ys)) - mean(xs*ys))) / float(((mean(xs)*mean(xs)) - mean(xs*xs))))
	b = mean(ys) - m*mean(xs)
	return m, b


def get_datetime():
	dt = datetime.now()
	hr = dt.hour
	ampm = 'AM' if (hr < 12 or hr == 24) else 'PM'
	hr_str = str(hr % 12)
	if hr_str == '0':
		hr_str = '12'
	if len(hr_str) < 2:
		hr_str = '0' + hr_str
	min_str = str(dt.minute)
	if len(min_str) < 2:
		min_str = '0' + min_str
	sec_str = str(dt.second)
	if len(sec_str) < 2:
		sec_str = '0' + sec_str
	dt_str = '{}/{}/{} ({}:{}:{} {})'.format(dt.month, dt.day, dt.year, hr_str, min_str, sec_str, ampm)
	return dt_str 


def board_temperature():
	temp = sp.getoutput('/opt/vc/bin/vcgencmd measure_temp')
	temp = float(temp[temp.index('=')+1:-2])
	# print("{:4.2f} °C".format(temp))
	return temp


def rh_to_abs_humidity(rh, temp, press):
	""" Returns the current absolute humidity (in grams
	per cubic meter) based on the current relative 
	humidity, temperature, and barometric pressure.
	Source: https://planetcalc.com/2167/
	"""
	RV = 461.5  	## Specific gas constant for water vapor

	eW = saturation_vapor_pressure(press, temp)
	e = eW * (rh / 100.0)
	ah = ((e / (temp * RV)) * 10.0) * 1000 ## * 1000 to convert kg/m3 to g/m3
	return ah 		## Units: g/m3


def saturation_vapor_pressure(p, t):
		""" Source: https://planetcalc.com/2161/ """
		fp = 1.0016 + ((3.15 * 10**(-6)) * p) - (0.074 * (p**(-1)))
		ewt = 6.112 * (math.e ** ((17.62 * t) / (243.12 + t)))
		eW = fp * ewt
		return eW


##------------------------------------------------------------------------------

i2c_addresses = {
	0x48 : "ads1x15_0",
	0x49 : "ads1x15_1",
	0x4A : "ads1x15_2",
	0x4B : "ads1x15_3",
	0x58 : "sgp30",
	0x68 : "k33",
	0x77 : "bme680",
	
}

##------------------------------------------------------------------------------
