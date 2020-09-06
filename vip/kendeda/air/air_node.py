#!/usr/local/bin/python3.6

""" NOTE/TODO: Only Full_Test_OPC_GPIO() && CO_Test() currently utilize DBCloud interface! """

""" TODO: Enhance logging -- using logging module to commit errors & milestones/heartbeats to local files """

import os
import sys
import time
import busio
import board
import RPi.GPIO as GPIO
from adafruit_ads1x15 import ads1115, ads1015, analog_in

try:
	from util import util, weather, comports, pump
	import alphasense.isb as isb
	from opcn2 import opcn2
	from k33 import k33_uart as k33
	from mq7 import mq 
	from bme680 import bme
	from sgp30 import sgp 
	# import backend.dbutil as influx
	import backend.influx_cloud as influx
except ImportError:
	print("[air_node] ImportError caught")
	# sys.path.append(os.path.join(os.environ['HOME'], 'air'))
	sys.path.append(os.getcwd())
	from util import util, weather, comports, pump
	import alphasense.isb as isb
	from opcn2 import opcn2
	from k33 import k33_uart as k33
	from mq7 import mq 
	from bme680 import bme
	from sgp30 import sgp 
	# import backend.dbutil as influx
	import backend.influx_cloud as influx
	

#------------------------------------------------------------------------------
## Global instances

## Global singleton interface for writing data to the InfluxDB backend
# db = influx.DB()
# db.create_database(DB_NAME)

# db = influx.DBCloud() 		## UPDATE: Global db instance moved to util.py (4/21/20)
if util.DRY_RUN:
	db = None 
else:
	try:
		db = influx.DBCloud()
		print(f"[{__file__}] InfluxDB Cloud backend enabled.")
	except ValueError as ve:
		print(f"[{__file__}] CRITICAL ERROR FROM influx_cloud.DBCloud instantiation!")
		print("\n{0}:\n\t({1})\n".format(type(ve).__name__, ve))

		## TODO: Decide, should the program terminate if the backend cannot be reached,
		## 	or should data still be collected locally while retrying for Influx Cloud connection...
		if util.REQUIRE_INTERNET:
			print("DEAD @ {}  (INTERNET CONNECTION IS REQUIRED)".format(util.get_datetime()))
			sys.exit(2)
		else:
			db = None


i2c = board.I2C() 	## Singleton I2C interface
# i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
spi = board.SPI()

owm = weather.OpenWeatherMap(city="Atlanta", state="ga", country="us", location_id=4180439)

bme_sensor = None 
try:
	if util.BME_USE_I2C:
		bme_sensor = bme.BME680(i2c, stabilize_humidity=util.STABILIZE_HUMIDITY)
	else:
		bme_sensor = bme.BME680(spi, use_i2c=False, stabilize_humidity=util.STABILIZE_HUMIDITY)
except ValueError:
	print(f"[{__file__}] No BME680 sensor breakout detected")
	util.USE_TEMP_COEFFICIENT = False 	## Also indicates the global bme object is None
	bme_sensor = None 
else:
	bme_sensor.update_sea_level_pressure(owm.get_sea_level_pressure())
	print(f"[{__file__}] BME680 enabled.")


sgp_sensor = None
try:
	sgp_sensor = sgp.SGP30(i2c)
	if bme_sensor is not None:
		sgp_sensor.set_iaq_humidity(bme_sensor.get_absolute_humidity())
	print(f"[{__file__}] SGP30 enabled.")
except ValueError:
	print(f"[{__file__}] No SGP30 sensor breakout detected")
	util.INCLUDE_VOC = False
	util.INCLUDE_ECO2 = False

#------------------------------------------------------------------------------

def CO_Test():
	## Create an ADS1115 ADC (16-bit) instance or an ADS1015 ADC (12-bit) instance
	adc = None
	if util.ADC_PREC == 12:
		adc = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
	elif util.ADC_PREC == 16:
		adc = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
	if adc is None:
		print(f"[ERROR] Invalid ADC precision specified (only 12 or 16 supported):  ADC_PREC = {util.ADC_PREC}")
		sys.exit(2)

	co_serial = '162030904'  ## Found on sticker on side of sensor
	co_op1_pin = 0 	## WE: Orange wire from Molex connector --> channel A0 of the ADC breakout
	co_op1 = analog_in.AnalogIn(adc, co_op1_pin)
	co_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of the ADC breakout
	co_op2 = analog_in.AnalogIn(adc, co_op2_pin)

	## Can specify WE/Aux Zero Offset values & Sensitivity constant provided on the ISB bag label
	## Else, not specifying args (or passing None) will default to the standard/typical values 
	## for the sensor type (provided in Table 2 of the ISB user manual)
	co_sensor = isb.CO(co_op1, co_op2, serial=co_serial) #, we_offset=449, ae_offset=316, sensitivty=419)

	while True:
		try:
			co_ppm = co_sensor.ppm 
			print("CO concentration = {:04.2f} ppm".format(co_ppm))

			if db is not None:
				db.queue_measurement(influx.MeasurementTypes.co, co_ppm)
				success = db.write()
				# print("[CO_Test] Write to backend success: {}".format(success))
				if not success:
					print("[CO_Test] Write to InfluxDB failed!")

			time.sleep(util.MEASUREMENT_INTERVAL)
		# except KeyboardInterrupt:
		# 	db.kill()
		# 	break
		except Exception as e:  #KeyboardInterrupt:
			print(f"\n[{__file__}] Program termination triggered by {type(e).__name__}:\n\t({e})\n")
			# db.kill()
			# break
			die()



def NO2_OX_Test():
	""" Assuming an NO2-B43F ISB & an OX-B431 ISB are present in circuit, both connected to a single I2C ADC breakout
	ADS1x15 pin A0 --> NO2 OP1 (WE: Orange wire from Molex connector)
	ADS1x15 pin A1 --> NO2 OP2 (AE: Yellow wire from Molex connector)
	ADS1x15 pin A2 --> OX OP1 (WE: Orange wire from Molex connector)
	ADS1x15 pin A3 --> OX OP2 (AE: Yellow wire from Molex connector)
	"""
	if not util.HAVE_NO2_AND_OX:
		print("[NO2_OX_Test] This test requires connected ISBs for both one NO2-B43F and one OX-B431 sensor  (HAVE_NO2_AND_OX == False)")
		sys.exit()
	adc = None
	if util.ADC_PREC == 12:
		adc = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
	elif util.ADC_PREC == 16:
		adc = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
	if adc is None:
		print(f"[ERROR] Invalid ADC precision specified (only 12 or 16 supported):  ADC_PREC = {util.ADC_PREC}")
		sys.exit(2)

	## Instantiate NO2-B43F sensor:
	no2_serial = '202931852'  ## Found on sticker on side of sensor
	no2_op1 = analog_in.AnalogIn(adc, A0)
	no2_op2 = analog_in.AnalogIn(adc, A1)
	no2_sensor = isb.NO2(no2_op1, no2_op2, serial=no2_serial)

	## Instantiate OX-B431 sensor:
	ox_serial = '204930754'  ## Found on sticker on side of sensor
	ox_op1 = analog_in.AnalogIn(adc, A2)
	ox_op2 = analog_in.AnalogIn(adc, A3)
	ox_sensor = isb.OX(ox_op1, ox_op2, serial=ox_serial)

	banner = '-' * 63
	print('{0}\n| {1:^10} | {2:^10} | {3:^10} | {4:^10} |\n{0}'.format(banner, 'Temp (°C)', 'Humid (%)', 'NO2 (ppm)', 'O3 (ppm)'))
	while True:
		try:
			if bme_sensor is None:
				try:
					temp = util.board_temperature() # if bme is None else bme.get_temperature()
				except:
					temp = 0.0
			else:
				temp = bme_sensor.get_temperature()
			humid = 0.0 if bme_sensor is None else bme_sensor.get_humidity()
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if util.HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
				ox_ppm = ox_sensor.get_oxide_ppm_only(no2_ppm)
			else:
				ox_ppm = ox_sensor.ppm

			print('| {0:^10.4f} | {1:^10.4f} | {2:^10.4f} | {3:^10.4f} |'.format(temp, humid, no2_ppm, ox_ppm))
			time.sleep(util.MEASUREMENT_INTERVAL)
		# except KeyboardInterrupt:
		# 	db.kill()
		# 	break
		except Exception as e:  #KeyboardInterrupt:
			print(f"\n[{__file__}] Program termination triggered by {type(e).__name__}:\n\t({e})\n")
			# db.kill()
			# break
			die()


def Full_ISB_Test():
	""" Test circuit: 2 ADS1x15 ADC breakouts + 1 CO-B4 + 1 NO2-B43F + 1 OX-B431
	"""

	## Create two ADS1115 ADC (16-bit) instances or an ADS1015 ADC (12-bit) instances
	adc0 = None
	adc1 = None
	if util.ADC_PREC == 12:
		adc0 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
	elif util.ADC_PREC == 16:
		adc0 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
	if adc0 is None or adc1 is None:
		print(f"[ERROR] Invalid ADC precision specified (only 12 or 16 supported):  ADC_PREC = {util.ADC_PREC}")
		sys.exit(2)

	## Instantiate CO-B4 sensor:
	co_serial = '162030904'  ## Found on sticker on side of sensor
	co_op1_pin = 0 	## WE: Orange wire from Molex connector --> channel A0 of first ADC breakout
	co_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of first ADC breakout
	co_op1 = analog_in.AnalogIn(adc0, co_op1_pin)
	co_op2 = analog_in.AnalogIn(adc0, co_op2_pin)
	co_sensor = isb.CO(co_op1, co_op2, serial=co_serial)

	## Instantiate NO2-B43F sensor:
	no2_serial = '202931852'  ## Found on sticker on side of sensor
	no2_op1_pin = 2  ## WE: Orange wire from Molex connector --> channel A2 of first ADC breakout
	no2_op2_pin = 3  ## AE: Yellow wire from Molex connector --> channel A3 of first ADC breakout
	no2_op1 = analog_in.AnalogIn(adc0, no2_op1_pin)
	no2_op2 = analog_in.AnalogIn(adc0, no2_op2_pin)
	no2_sensor = isb.NO2(no2_op1, no2_op2, serial=no2_serial)

	## Instantiate OX-B431 sensor:
	ox_serial = '204930754'  ## Found on sticker on side of sensor
	ox_op1_pin = 0  ## WE: Orange wire from Molex connector --> channel A0 of second ADC breakout
	ox_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of second ADC breakout
	ox_op1 = analog_in.AnalogIn(adc1, ox_op1_pin)
	ox_op2 = analog_in.AnalogIn(adc1, ox_op2_pin)
	ox_sensor = isb.OX(ox_op1, ox_op2, serial=ox_serial)

	banner = '-' * 66
	print('{0}\n| {1:^10} | {2:^10} | {3:^10} | {4:^10} | {5:^10} |\n{0}'.format(banner, 'Temp (°C)', 'Humid (%)', 'CO (ppm)', 'NO2 (ppm)', 'O3 (ppm)'))
	while True:
		try:
			# temp = board_temperature() if bme is None else bme.get_temperature() 
			if bme_sensor is None:
				try:
					temp = util.board_temperature() # if bme is None else bme.get_temperature()
				except:
					temp = 0.0
			else:
				temp = bme_sensor.get_temperature()
			humid = 0.0 if bme_sensor is None else bme_sensor.get_humidity()
			co_ppm = co_sensor.ppm
			time.sleep(0.5)
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if util.HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
				ox_ppm = ox_sensor.get_oxide_ppm_only(no2_ppm)
			else:
				ox_ppm = ox_sensor.ppm

			print('| {0:^10.4f} | {1:^10.4f} | {2:^10.4f} | {3:^10.4f} | {4:^10.4f} |'.format(temp, humid, co_ppm, no2_ppm, ox_ppm))
			time.sleep(util.MEASUREMENT_INTERVAL)
		except Exception as e:  #KeyboardInterrupt:
			print(f"\n[{__file__}] Program termination triggered by {type(e).__name__}:\n\t({e})\n")
			# db.kill()
			# break
			die()


def Full_Test_OPC_USB():
	# opc_n2 = opcn2.OPC_N2(use_usb=True)
	try:
		opc_n2 = opcn2.OPC_N2(use_usb=True)
	except ValueError as ve:
		print("[Full_Test_OPC_GPIO] Critical exception occurred:\n{}".format(ve))
		# db.kill()
		# sys.exit(1)
		die()

	## Create two ADS1115 ADC (16-bit) instances or an ADS1015 ADC (12-bit) instances
	adc0 = None
	adc1 = None
	if util.ADC_PREC == 12:
		adc0 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
	elif util.ADC_PREC == 16:
		adc0 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
	if adc0 is None or adc1 is None:
		print(f"[ERROR] Invalid ADC precision specified (only 12 or 16 supported):  ADC_PREC = {util.ADC_PREC}")
		sys.exit(2)

	## Instantiate CO-B4 sensor:
	co_serial = '162030904'  ## Found on sticker on side of sensor
	co_op1_pin = 0 	## WE: Orange wire from Molex connector --> channel A0 of first ADC breakout
	co_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of first ADC breakout
	co_op1 = analog_in.AnalogIn(adc0, co_op1_pin)
	co_op2 = analog_in.AnalogIn(adc0, co_op2_pin)
	co_sensor = isb.CO(co_op1, co_op2, serial=co_serial)

	## Instantiate NO2-B43F sensor:
	no2_serial = '202931852'  ## Found on sticker on side of sensor
	no2_op1_pin = 2  ## WE: Orange wire from Molex connector --> channel A2 of first ADC breakout
	no2_op2_pin = 3  ## AE: Yellow wire from Molex connector --> channel A3 of first ADC breakout
	no2_op1 = analog_in.AnalogIn(adc0, no2_op1_pin)
	no2_op2 = analog_in.AnalogIn(adc0, no2_op2_pin)
	no2_sensor = isb.NO2(no2_op1, no2_op2, serial=no2_serial)

	## Instantiate OX-B431 sensor:
	ox_serial = '204930754'  ## Found on sticker on side of sensor
	ox_op1_pin = 0  ## WE: Orange wire from Molex connector --> channel A0 of second ADC breakout
	ox_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of second ADC breakout
	ox_op1 = analog_in.AnalogIn(adc1, ox_op1_pin)
	ox_op2 = analog_in.AnalogIn(adc1, ox_op2_pin)
	ox_sensor = isb.OX(ox_op1, ox_op2, serial=ox_serial)


	opc_n2.on()
	# time.sleep(2)

	banner = '-' * 53
	print('{0}\n| {1:^10} | {2:^10} | {3:^10} | {4:^10} | {5:^16} | {6:^16} | {7:^16} |\n{0}'.format(banner, 'Temp (°C)', 'CO (ppm)', 'NO2 (ppm)', 'O3 (ppm)', 'PM1 (#/cc)', 'PM2.5 (#/cc)', 'PM10 (#/cc)'))
	

	while True:
		try:
			# temp = board_temperature() if bme is None else bme.get_temperature()
			if bme_sensor is None:
				try:
					temp = util.board_temperature() # if bme is None else bme.get_temperature()
				except:
					temp = 0.0
			else:
				temp = bme_sensor.get_temperature()
			co_ppm = co_sensor.ppm
			time.sleep(0.5)
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if util.HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
				ox_ppm = ox_sensor.get_oxide_ppm_only(no2_ppm)
			else:
				ox_ppm = ox_sensor.ppm

			pm = opc_n2.pm()
			pm1 = pm['PM1']
			pm25 = pm['PM2.5']
			pm10 = pm['PM10']

			print('| {0:^10.4f} | {1:^10.4f} | {2:^10.4f} | {3:^10.4f} | {4:^16.4f} | {5:^16.4f} | {6:^16.4f} |'.format(temp, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
			time.sleep(util.MEASUREMENT_INTERVAL)
		except Exception as e:  #KeyboardInterrupt:
			print(f"\n[{__file__}] Program termination triggered by {type(e).__name__}:\n\t({e})\n")
			opc_n2.off()
			# db.kill()
			# break
			die()


def Full_Test_OPC_GPIO():
	""" Wiring configuration for SPI via GPIO:
	------------------------------------------------------------------------
	| Pin	|	Function			| OPC	| RPi						   |
	------------------------------------------------------------------------
	| 1		| 5V DC					| VCC	| 5V                           |
	| 2		| Serial Clock			| SCK	| SCLK (Pin 23)                |
	| 3		| Master In Slave Out	| SDO	| MISO (Pin 21)                |
	| 4		| Master Out Slave In	| SDI	| MOSI (Pin 19)                |
	| 5		| Chip Select			| /SS	| CE0 (Pin 24) or CE1 (Pin 26) |
	| 6		| Ground				| GND	| GND                          |
	------------------------------------------------------------------------
	"""
	try:
		opc_n2 = opcn2.OPC_N2(use_usb=False)
	except ValueError as ve:
		print("[Full_Test_OPC_GPIO] Critical exception occurred:\n{}".format(ve))
		# db.kill()
		# sys.exit(1)
		die()

	## Create two ADS1115 ADC (16-bit) instances or an ADS1015 ADC (12-bit) instances
	adc0 = None
	adc1 = None
	if util.ADC_PREC == 12:
		adc0 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
	elif util.ADC_PREC == 16:
		adc0 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
	if adc0 is None or adc1 is None:
		print(f"[ERROR] Invalid ADC precision specified (only 12 or 16 supported):  ADC_PREC = {util.ADC_PREC}")
		sys.exit(2)

	isb_temp_func = bme_sensor.get_temperature if bme_sensor is not None else None 
	## Instantiate CO-B4 sensor:
	co_serial = '162030904'  ## Found on sticker on side of sensor
	co_op1_pin = util.A0 	## WE: Orange wire from Molex connector --> channel A0 of first ADC breakout
	co_op2_pin = util.A1 	## AE: Yellow wire from Molex connector --> channel A1 of first ADC breakout
	co_op1 = analog_in.AnalogIn(adc0, co_op1_pin)
	co_op2 = analog_in.AnalogIn(adc0, co_op2_pin)
	co_sensor = isb.CO(co_op1, co_op2, serial=co_serial, temperature_function=isb_temp_func)

	## Instantiate NO2-B43F sensor:
	no2_serial = '202931852'  ## Found on sticker on side of sensor
	no2_op1_pin = util.A2  ## WE: Orange wire from Molex connector --> channel A2 of first ADC breakout
	no2_op2_pin = util.A3  ## AE: Yellow wire from Molex connector --> channel A3 of first ADC breakout
	no2_op1 = analog_in.AnalogIn(adc0, no2_op1_pin)
	no2_op2 = analog_in.AnalogIn(adc0, no2_op2_pin)
	no2_sensor = isb.NO2(no2_op1, no2_op2, serial=no2_serial, temperature_function=isb_temp_func)

	## Instantiate OX-B431 sensor:
	ox_serial = '204930754'  ## Found on sticker on side of sensor
	ox_op1_pin = util.A0  ## WE: Orange wire from Molex connector --> channel A0 of second ADC breakout
	ox_op2_pin = util.A1 	## AE: Yellow wire from Molex connector --> channel A1 of second ADC breakout
	ox_op1 = analog_in.AnalogIn(adc1, ox_op1_pin)
	ox_op2 = analog_in.AnalogIn(adc1, ox_op2_pin)
	ox_sensor = isb.OX(ox_op1, ox_op2, serial=ox_serial, temperature_function=isb_temp_func)

	opc_n2.on()
	time.sleep(1)
	header = ''

	if util.INCLUDE_VOC:
		if util.INCLUDE_ECO2:
			header += '-' * 155
			header += '\n| {0:^10} | {1:^10} | {2:^12} | {3:^12} || {4:^10} | {5:^10} | {6:^10} | {7:^16} | {8:^16} | {9:^16} |\n'.format('Temp (°C)', 'Humid (%)', 'VOC (ppb)', 'eCO2 (ppm)' 'CO (ppm)', 'NO2 (ppm)', 'O3 (ppm)', 'PM1 (#/cc)', 'PM2.5 (#/cc)', 'PM10 (#/cc)')
			header += '-' * 155
			data_str = '| {0:^10.4f} | {1:^10.4f} | {2:^12.4f} | {3:^12.4f} || {4:^10.4f} | {5:^10.4f} | {6:^10.4f} | {7:^16.4f} | {8:^16.4f} | {9:^16.4f} |'
		else:
			header += '-' * 139
			header += '\n| {0:^10} | {1:^10} | {2:^12} || {3:^10} | {4:^10} | {5:^10} | {6:^16} | {7:^16} | {8:^16} |\n'.format('Temp (°C)', 'Humid (%)', 'VOC (ppb)', 'CO (ppm)', 'NO2 (ppm)', 'O3 (ppm)', 'PM1 (#/cc)', 'PM2.5 (#/cc)', 'PM10 (#/cc)')
			header += '-' * 139
			data_str = '| {0:^10.4f} | {1:^10.4f} | {2:^12.4f} || {3:^10.4f} | {4:^10.4f} | {5:^10.4f} | {6:^16.4f} | {7:^16.4f} | {8:^16.4f} |'
	else:
		header += '-' * 123
		header += '\n| {0:^10} | {1:^10} | {2:^10} | {3:^10} | {4:^10} | {5:^16} | {6:^16} | {7:^16} |\n'.format('Temp (°C)', 'Humid (%)', 'CO (ppm)', 'NO2 (ppm)', 'O3 (ppm)', 'PM1 (#/cc)', 'PM2.5 (#/cc)', 'PM10 (#/cc)')
		header += '-' * 123
		data_str = '| {0:^10.4f} | {1:^10.4f} | {2:^10.4f} | {3:^10.4f} | {4:^10.4f} | {5:^16.4f} | {6:^16.4f} | {7:^16.4f} |'

	print(header)
	timestamp = time.time()
	while True:
		payload = dict()
		try:
			if time.time() - timestamp >= util.HEADER_PRINT_INTERVAL:
				print(header)
				timestamp = time.time()

			# temp = board_temperature() if bme is None else bme.get_temperature()
			if bme_sensor is None:
				try:
					temp = util.board_temperature()
				except:
					temp = 0.0
			else:
				temp = bme_sensor.get_temperature()
			humid = 0.5 if bme_sensor is None else bme_sensor.get_humidity()    ## TODO: Use OpenWeatherMap to get local RH
			co_ppm = co_sensor.ppm
			time.sleep(0.5)
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if util.HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
				ox_ppm = ox_sensor.get_oxide_ppm_only(no2_ppm)
			else:
				ox_ppm = ox_sensor.ppm

			pm = opc_n2.pm()
			if any(pm_val < 0 for pm_val in list(pm.values())):
				## Account for any potential intialization error for the OPC-N2
				opc_n2.on()
				time.sleep(1)
				pm = opc_n2.pm()
			pm1 = pm['PM1'] if pm['PM1'] >= 0 else 0.0000
			pm25 = pm['PM2.5'] if pm['PM2.5'] >= 0 else 0.0000
			pm10 = pm['PM10'] if pm['PM10'] >= 0 else 0.0000

			## Populate a batch of measurement data to be sent to the backend
			payload.update(
					{
						influx.MeasurementTypes.temp: temp,
						influx.MeasurementTypes.rh: humid,
						influx.MeasurementTypes.co: co_ppm,
						influx.MeasurementTypes.no2: no2_ppm,
						influx.MeasurementTypes.ox: ox_ppm,
						influx.MeasurementTypes.pm1: pm1,
						influx.MeasurementTypes.pm25: pm25,
						influx.MeasurementTypes.pm10: pm10,
					}
				)
			# db.queue_measurement_batch(payload)
			if db:
				db.queue_data_point(payload)
			# db.queue_data_line(payload)

			if util.INCLUDE_VOC:
				voc = sgp_sensor.get_tvoc() if sgp_sensor is not None else get_voc()
				# payload.update({ influx.MeasurementTypes.tvoc: voc })
				# db.queue_measurement(influx.MeasurementTypes.tvoc, voc)
				# db.queue_data_line({ influx.MeasurementTypes.tvoc: voc })
				if db:
					db.queue_data_point({ influx.MeasurementTypes.tvoc: voc })

				if util.INCLUDE_ECO2:  # and sgp is not None:
					eco2 = sgp_sensor.get_eco2()
					# db.queue_measurement(influx.MeasurementTypes.eco2, eco2)
					# db.queue_data_line({ influx.MeasurementTypes.eco2: eco2 })
					if db:
						db.queue_data_point({ influx.MeasurementTypes.eco2: eco2 })

					if util.SHOW_DATETIME:
						print(data_str.format(temp, humid, voc, eco2, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10) + '  [ {} ]'.format(util.get_datetime()))
					else:
						print(data_str.format(temp, humid, voc, eco2, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
				else:
					if util.SHOW_DATETIME:
						print(data_str.format(temp, humid, voc, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10) + '  [ {} ]'.format(util.get_datetime()))
					else:
						print(data_str.format(temp, humid, voc, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
			else:
				if util.SHOW_DATETIME:	
					print(data_str.format(temp, humid, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10) + '  [ {} ]'.format(util.get_datetime()))
				else:
					print(data_str.format(temp, humid, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
			
			## Publish sensor measurements to the database
			# db.queue_measurement_batch(payload)
			# success = db.write()
			if db:
				success = db.flush()
				# print("[Full_Test_OPC_GPIO] Write to backend success: {}".format(success))
				if not success:
					print("[Full_Test_OPC_GPIO] Write to InfluxDB failed!  ({})".format(util.get_datetime()))
			time.sleep(util.MEASUREMENT_INTERVAL)
		except KeyboardInterrupt:
			opc_n2.off()
			die(exit=False)
			break
		except Exception as e:  #KeyboardInterrupt:
			print(f"\n[{__file__}] Program termination triggered by {type(e).__name__}:\n\t({e})\n")
			opc_n2.off()
			# db.kill()
			# print("DEAD @ {}".format(util.get_datetime()))
			die() #exit=False)
			# break


#------------------------------------------------------------------------------

def main():
	# function_map = dict() 

	k33_usb_port = None 
	opc_usb_port = None 
	ports_dict = comports.get_com_ports(display_ports=False)
	for port in ports_dict.keys():
		desc = ports_dict[port]
		if 'USB-ISS' in desc:
			opc_usb_port = port
			print("[{}] Using port '{}' for connecting the OPC-N2 sensor  ('{}')".format(__file__, port, desc))
		elif 'FT232R USB UART' in desc:
			k33_usb_port = port 
			print("[{}] Using port '{}' for connecting the K33-ELG sensor  ('{}')".format(__file__, port, desc))

	try:
		## Instantiate K33-ELG sensor:
		co2_sensor = k33.K33(port=k33_usb_port) if k33_usb_port is not None else k33.K33()
		# k33_co2_func = co2_sensor.read_co2
		# function_map[influx.MeasurementTypes.co2] = k33_co2_func
		print(f"[{__file__}] K33-ELG enabled.")

		## Instantiate OPC-N2 sensor:
		opc_sensor = opcn2.OPC_N2(use_usb=True, usb_port=opc_usb_port) if opc_usb_port is not None else opcn2.OPC_N2()
		# opc_pm1_func = opc_sensor.PM1 
		# opc_pm25_func = opc_sensor.PM25
		# opc_pm10_func = opc_sensor.PM10
		# function_map.update({
		# 		influx.MeasurementTypes.pm1: opc_pm1_func,
		# 		influx.MeasurementTypes.pm25: opc_pm25_func,
		# 		influx.MeasurementTypes.pm10: opc_pm10_func
		# })
		print(f"[{__file__}] OPC-N2 enabled.")

		## Create two ADS1115 ADC (16-bit) instances or an ADS1015 ADC (12-bit) instances
		adc0 = None
		adc1 = None
		if util.ADC_PREC == 12:
			adc0 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
			adc1 = ads1015.ADS1015(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
		elif util.ADC_PREC == 16:
			adc0 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
			adc1 = ads1115.ADS1115(i2c, gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
		if adc0 is None or adc1 is None:
			print(f"[ERROR] Invalid ADC precision specified (only 12 or 16 supported):  ADC_PREC = {util.ADC_PREC}")
			sys.exit(2)

		print(f"[{__file__}] ADS1{'0' if util.ADC_PREC == 12 else '1'}15 enabled.")

		## Setup a 'get_temperature' function pointer to give to temp dependent sensors (i.e., the ISBs)
		## If the global `bme` instance exists, use `bme.get_temperature`
		## Elif our co2_sensor (the K33) is hooked up, use `co2_sensor.read_temp`
		## Else, use `board_temperature` from util.py
		if bme_sensor is not None:
			# get_temperature = bme_sensor.get_temperature
			def get_temperature():
				bme_temp = bme_sensor.get_temperature()
				k33_temp = co2_sensor.read_temp()
				return round(((bme_temp + k33_temp) / 2), 2)

			def get_humidity():
				bme_rh = bme_sensor.get_humidity()
				k33_rh = co2_sensor.read_rh()
				return round(((bme_rh + k33_rh) / 2), 2)
		else:
			get_temperature = co2_sensor.read_temp 	## NOTE: Experimentally, the K33 temperature reading appears more accurate than the BME680's!
			get_humidity = co2_sensor.read_rh
		# else:
		# 	get_temperature = util.board_temperature
		## ^ NOTE: Do NOT use board temperature!! It is unreliable (much hotter than what the sensors are exposed to)

		# function_map.update({
		# 		influx.MeasurementTypes.temp: get_temperature,
		# 		influx.MeasurementTypes.rh: get_humidity
		# })

		## Instantiate CO-B4 sensor:
		co_serial = '162030905'  ## Found on sticker on side of sensor
		co_op1_pin = 0 	## WE: Orange wire from Molex connector --> channel A0 of first ADC breakout
		co_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of first ADC breakout
		co_op1 = analog_in.AnalogIn(adc0, co_op1_pin)
		co_op2 = analog_in.AnalogIn(adc0, co_op2_pin)
		co_sensor = isb.CO(co_op1, co_op2, serial=co_serial, temperature_function=get_temperature)
		# isb_co_func = co_sensor.get_ppm 
		print(f"[{__file__}] CO-B4 enabled.")

		## Instantiate NO2-B43F sensor:
		no2_serial = '202931852'  ## Found on sticker on side of sensor
		no2_op1_pin = 2  ## WE: Orange wire from Molex connector --> channel A2 of first ADC breakout
		no2_op2_pin = 3  ## AE: Yellow wire from Molex connector --> channel A3 of first ADC breakout
		no2_op1 = analog_in.AnalogIn(adc0, no2_op1_pin)
		no2_op2 = analog_in.AnalogIn(adc0, no2_op2_pin)
		no2_sensor = isb.NO2(no2_op1, no2_op2, serial=no2_serial, temperature_function=get_temperature)
		# isb_no2_func = no2_sensor.get_ppm 
		# function_map[influx.MeasurementTypes.no2] = isb_no2_func
		print(f"[{__file__}] NO2-B43F enabled.")

		## Instantiate OX-B431 sensor:
		ox_serial = '204930756'  ## Found on sticker on side of sensor
		ox_op1_pin = 0  ## WE: Orange wire from Molex connector --> channel A0 of second ADC breakout
		ox_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of second ADC breakout
		ox_op1 = analog_in.AnalogIn(adc1, ox_op1_pin)
		ox_op2 = analog_in.AnalogIn(adc1, ox_op2_pin)
		ox_sensor = isb.OX(ox_op1, ox_op2, serial=ox_serial, temperature_function=get_temperature)
		# isb_ox_func = ox_sensor.get_ppm 
		# function_map[influx.MeasurementTypes.ox] = isb_ox_func
		if util.HAVE_NO2_AND_OX:   ## Obviously true in this scenario
			def get_ozone():
				return round(ox_sensor.get_oxide_ppm_only(no2_sensor.ppm), 4)
		else:
			get_ozone = ox_sensor.get_ppm 
		# function_map[influx.MeasurementTypes.ox] = get_ozone
		print(f"[{__file__}] OX-B431 enabled.")

		## Instantiate MQ7 sensor (optional):
		if util.INCLUDE_MQ7_CO:
			mq_adc_pin = 3  ## We have an MQ7 connected to channel A3 of the second ADC breakout
			mq_adc = analog_in.AnalogIn(adc1, mq_adc_pin)
			mq_sensor = mq.MQ7(mq_adc, vdd=5.0)  ## MQ7 is powered by either 5.0V or 3.3V 
			# mq_co_func = mq_sensor.MQ_CO_PPM
			print(f"[{__file__}] MQ7 enabled.")

			def get_avg_co():
				## Using sensor fusion to acquire an average carbon monoxide concentration
				# isb_co = isb_co_func()
				# mq7_co = mq_co_func()
				# return round(((isb_co + mq7_co) / 2), 4)
				return round(((co_sensor.get_ppm() + mq_sensor.MQ_CO_PPM()) / 2), 4)
		else:
			mq_sensor = None 
			# get_avg_co = isb_co_func 
			get_avg_co = co_sensor.get_ppm

		# function_map[influx.MeasurementTypes.co] = get_avg_co


		## Ensure any connected SGP30 sensor has had its absolute humidity baseline set
		if sgp_sensor is not None and not sgp_sensor.humidity_set:
			## If not set by BME680, use K33 (if available)
			## TODO: Create utility function to translate relative humidity into absolute humidity
			##  (move from sgp.py into util.py, or by other means)
			# rh = bme_sensor.get_humidity() if bme_sensor is not None else co2_sensor.read_rh()
			rh = get_humidity()
			temp = get_temperature()
			press = owm.get_sea_level_pressure()
			sgp_sensor.set_iaq_humidity(util.rh_to_abs_humidity(rh, temp, press))
			print(f"[{__file__}] SGP30 re-enabled.")
		
		# sgp_tvoc_func = sgp_sensor.get_tvoc if (sgp_sensor is not None and util.INCLUDE_VOC) else None
		# sgp_eco2_func = sgp_sensor.get_eco2 if (sgp_sensor is not None and util.INCLUDE_ECO2) else None
		# function_map.update({influx.MeasurementTypes.tvoc: sgp_tvoc_func, influx.MeasurementTypes.eco2: sgp_eco2_func})

		function_map = {
				influx.MeasurementTypes.temp: get_temperature,
				influx.MeasurementTypes.rh:   get_humidity,
				influx.MeasurementTypes.co:   get_avg_co,
				influx.MeasurementTypes.co2:  co2_sensor.read_co2,  #k33_co2_func,
				influx.MeasurementTypes.no2:  no2_sensor.get_ppm,  #isb_no2_func,
				influx.MeasurementTypes.ox:   get_ozone,  #ox_sensor.get_ppm,  #isb_ox_func,
				influx.MeasurementTypes.eco2: sgp_sensor.get_eco2 if (sgp_sensor is not None and util.INCLUDE_ECO2) else None,   #sgp_eco2_func
				influx.MeasurementTypes.tvoc: sgp_sensor.get_tvoc if (sgp_sensor is not None and util.INCLUDE_VOC) else None,   #sgp_tvoc_func,
				influx.MeasurementTypes.pm1:  opc_sensor.PM1,    #opc_pm1_func,
				influx.MeasurementTypes.pm25: opc_sensor.PM25,  #opc_pm25_func,
				influx.MeasurementTypes.pm10: opc_sensor.PM10,  #opc_pm10_func,
		}

		units_map = {
				influx.MeasurementTypes.temp: '°C',
				influx.MeasurementTypes.rh:   '%',
				influx.MeasurementTypes.co:   'ppm',
				influx.MeasurementTypes.co2:  'ppm',
				influx.MeasurementTypes.no2:  'ppm',
				influx.MeasurementTypes.ox:   'ppm',
				influx.MeasurementTypes.eco2: 'ppm',
				influx.MeasurementTypes.tvoc: 'ppb',
				influx.MeasurementTypes.pm1:  '#/cc',
				influx.MeasurementTypes.pm25: '#/cc',
				influx.MeasurementTypes.pm10: '#/cc',				
		}

		pump_relay = pump.AirPump(util.AIR_PUMP_PIN) if util.INCLUDE_AIR_PUMP else None 
		if pump_relay is not None:
			pump_relay.on()
			print(f"[{__file__}] Air pump enabled.")

		## TODO: Setup display format strings for all data points
		header = '='*(len(function_map) * 5)  #10)


		timestamp = time.time()
		while True:
			payload = dict()
			try:
				if time.time() - timestamp >= util.HEADER_PRINT_INTERVAL:
					print(header)
					timestamp = time.time()

				disp_str = f"{header}\n {util.get_datetime()}:"

				## Read all sensors using the associated callables in function_map to populate the payload dictionary
				for sensor_type in function_map:
					if function_map[sensor_type] is not None:
						sensor_reading = function_map[sensor_type]()
						payload[sensor_type] = sensor_reading
						disp_str += f"\n\t{sensor_type.name.upper():5} =  {sensor_reading:^10.4f} ({units_map[sensor_type]})"
						time.sleep(0.1)

				## TODO: Print sensor readings to the console
				"""
				if util.SHOW_DATETIME:
					print(data_str.format(temp, humid, voc, eco2, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10) + '  [ {} ]'.format(util.get_datetime()))
				else:
					print(data_str.format(temp, humid, voc, eco2, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
				"""
				disp_str += f"\n{header}\n"
				print(disp_str)

				## Publish sensor measurements to the database
				if db is not None and not util.DRY_RUN:
					db.queue_data_point(payload)
					success = db.flush()
					if not success:
						print("[{}}] Write to InfluxDB failed!  ({})".format(__file__, util.get_datetime()))

				time.sleep(util.MEASUREMENT_INTERVAL)

			except KeyboardInterrupt:
				if pump_relay is not None:
					pump_relay.off()
					print(f"[{__file__}] Air pump disabled.")
				opc_sensor.off()
				print(f"[{__file__}] OPC-N2 disabled.")
				die(exit=False)
				break 

	except ValueError:
		opc_sensor.off()
		die(msg="Critial exception occurred in 'main' (ValueError)")

#------------------------------------------------------------------------------

def die(msg="DEAD", exit=True):
	if db is not None:
		db.kill()
	death_text = "\n[air_node::die] {} @ {}".format(msg, util.get_datetime())
	print(death_text)
	with open(util.ERROR_LOGFILE, 'a') as f:
		f.write(death_text)
	if exit:
		sys.exit(2)

tests = {
	1 : CO_Test,
	2 : NO2_OX_Test,
	3 : Full_ISB_Test,
	4 : Full_Test_OPC_USB,
	5 : Full_Test_OPC_GPIO,
	#### TODO: More tests here for specific sensors: BME680, SGP30, OPC-N2 (only)
}

def menu_select():
	menu_prompt = 'Enter test number to run:'
	menu_prompt += '\n\t1. Carbon Monoxide (CO-B4) Test'
	menu_prompt += '\n\t2. Nitrogen Dioxide (NO2-B43F) & Ozone (OX-B431) Test'
	menu_prompt += '\n\t3. Full ISB Test (CO, NO2, O3)'
	menu_prompt += '\n\t4. Full Test + OPC-N2 (USB)'
	menu_prompt += '\n\t5. Full Test + OPC-N2 (SPI/GPIO)  <-- default\n'
	err_str = '[ValueError] Invalid input: "{}" --> Please enter a number from 1 to {}'
	test_num = input(menu_prompt)
	try:
		n = int(test_num)
		if not (1 <= n <= len(tests)):
			print(err_str.format(test_num, len(tests)))
			n = None
	except ValueError:
		print(err_str.format(test_num, len(tests)))
		n = None 
	return n



if __name__ == "__main__":
	# if not db.created:
	# 	db.create_database()

	if not util.DISPLAY_TEST_MENU:
		## Launch default test
		# Full_Test_OPC_GPIO()
		main()
	else:
		n = None 
		while n is None:
			n = menu_select()

		# ## Temporary...
		# if n == 2:
		# 	print('Sorry, Test #2 is yet to be implemented')
		# 	sys.exit()

		## Run the selected test
		tests[n]() 

