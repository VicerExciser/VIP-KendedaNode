## util.py -- Configuration settings, constants, and singleton object instances

import os
import sys
import busio
import board
import subprocess as sp
from statistics import mean 
from datetime import datetime
try:
	from util.weather import OpenWeatherMap, network_connected
	from bme680.bme import BME680
	from sgp30.sgp import SGP30 
	import backend.influx_cloud as influx
except ImportError:
	# print("[util] Appending '{}' to PYTHONPATH".format(os.path.join(os.environ['HOME'], 'air')))
	# sys.path.append(os.path.join(os.environ['HOME'], 'air'))
	rootpath = '/'.join(os.getcwd().split('/')[:-1])
	print("[util] Appending '{}' to PYTHONPATH".format(rootpath))
	sys.path.append(rootpath)
	from util.weather import OpenWeatherMap, network_connected
	from bme680.bme import BME680
	from sgp30.sgp import SGP30 
	import backend.influx_cloud as influx

##------------------------------------------------------------------------------
## AIR NODE PROGRAM CONFIGURATIONS:
REQUIRE_INTERNET = True  ## Set to False if a connection to the backend is not required
DISPLAY_TEST_MENU = False #True  	 ## For enabling the user to select a test to be run
USE_TEMP_COEFFICIENT = True  ## Compensate for temperature skew to improve reading accuracies
HAVE_NO2_AND_OX = True  	 ## True if this circuit/node incorporates both a NO2-B43F & OX-B431
INCLUDE_VOC = True 
INCLUDE_ECO2 = True
SHOW_DATETIME = True #False
BME_USE_I2C = True 		## Else, will use SPI
STABILIZE_HUMIDITY = True

MEASUREMENT_INTERVAL = 5     ## Seconds
HEADER_PRINT_INTERVAL = 120	 ## Seconds (for tests -- will print column headers once every 2 minutes)
# MAX_RETRIES = 5

ERROR_LOGFILE = os.path.join(os.environ['HOME'], "node_errors.log")

##------------------------------------------------------------------------------

ADC_I2C_ADDR0 = 0x48 	## ADDR pin -> GND (Default ADS1x15 I2C address, can be overridden using ADDR pin)
ADC_I2C_ADDR1 = 0x49 	## ADDR pin -> VDD
ADC_I2C_ADDR2 = 0x4A 	## ADDR pin -> SDA
ADC_I2C_ADDR3 = 0x4B 	## ADDR pin -> SCL

ADC_PREC = 16	## Either 12-bit or 16-bit precision ADS1x15 ADC breakout

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

##------------------------------------------------------------------------------

owm = OpenWeatherMap()
i2c = board.I2C() 	## Singleton I2C interface
# i2c = busio.I2C(board.SCL, board.SDA)
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

sgp = None 
try:
	sgp = SGP30(i2c)
	sgp.iaq_init()
	sgp.set_iaq_baseline(0x8CC9, 0x8F12)
	if bme is not None:
		sgp.set_iaq_humidity(bme.get_absolute_humidity())
except ValueError:
	print("[util] No SGP30 sensor breakout detected")
	INCLUDE_VOC = False
	INCLUDE_ECO2 = False


##------------------------------------------------------------------------------
## UTILITY / HELPER FUNCTIONS:

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


##------------------------------------------------------------------------------

"""
Constant coefficient values specific to each ISB, values found on bags:
	- Serial:  unique indentifier
	- WEe:  read from the "WE Zero Electronic" column (units in mV) -- not the Total value
	- AEe:  read from the "Aux Zero Electronic" column (units in mV) -- not the Total value
	- Sens:  read from the "WE Sens Total" column (units in mV/ppb) -- not the Electronic value
"""

isb_serials = {
	'162030904' :	## CO-B4
	{
		'WEe'  : 344,
		'AEe'  : 345,
		'Sens' : 419
	},
	'162030905' :	## CO-B4
	{
		'WEe'  : 343,
		'AEe'  : 349,
		'Sens' : 422
	},
	'162030906' :	## CO-B4
	{
		'WEe'  : 343,
		'AEe'  : 355,
		'Sens' : 448
	},

	'204930753' :	## OX-B431
	{
		'WEe'  : 231,
		'AEe'  : 234,
		'Sens' : 321
	},
	'204930754' :	## OX-B431
	{
		'WEe'  : 234,
		'AEe'  : 230,
		'Sens' : 306
	},
	'204930755' :	## OX-B431
	{
		'WEe'  : 228,
		'AEe'  : 221,
		'Sens' : 288
	},
	'204930756' :	## OX-B431
	{
		'WEe'  : 235,
		'AEe'  : 234,
		'Sens' : 308
	},

	'202931852' :	## NO2-B43F
	{
		'WEe'  : 219,
		'AEe'  : 246,
		'Sens' : 230
	},
	'202931849' :	## NO2-B43F
	{
		'WEe'  : 225,
		'AEe'  : 232,
		'Sens' : 216
	},
	'202931851' :	## NO2-B43F
	{
		'WEe'  : 227,
		'AEe'  : 232,
		'Sens' : 212
	},
}

"""
Serials w/ unknown bag label constants:
	162030905 (CO-B4)
	162030907 (CO-B4)
"""

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
