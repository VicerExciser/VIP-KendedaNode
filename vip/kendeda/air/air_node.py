#!/usr/local/bin/python3.6

""" NOTE/TODO: Only Full_Test_OPC_GPIO() && CO_Test() currently utilize DBCloud interface! """

""" TODO: Enhance logging -- using logging module to commit errors & milestones/heartbeats to local files """

import os
import sys
import time
import RPi.GPIO as GPIO
from adafruit_ads1x15 import ads1115, ads1015, analog_in

try:
	from util.util import *
	import alphasense.isb as isb
	from opcn2 import opcn2
	from k33 import k33_uart as k33
	from util import comports
	from mq7 import mq 
	# import backend.dbutil as influx
	# import backend.influx_cloud as influx
except ImportError:
	print("[air_node] ImportError caught")
	# sys.path.append(os.path.join(os.environ['HOME'], 'air'))
	sys.path.append(os.getcwd())
	from util.util import *
	import alphasense.isb as isb
	from opcn2 import opcn2
	from k33 import k33_uart as k33
	from util import comports
	from mq7 import mq 
	# import backend.dbutil as influx
	# import backend.influx_cloud as influx
	

#------------------------------------------------------------------------------
## Global singleton interface for writing data to the InfluxDB backend
# db = influx.DB()
# db.create_database(DB_NAME)

# db = influx.DBCloud() 		## UPDATE: Global db instance moved to util.py (4/21/20)
#------------------------------------------------------------------------------


def CO_Test():
	## Create an ADS1115 ADC (16-bit) instance or an ADS1015 ADC (12-bit) instance
	adc = None
	if ADC_PREC == 12:
		adc = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
	elif ADC_PREC == 16:
		adc = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
	if adc is None:
		print("[ERROR] Invalid ADC precision specified (only 12 or 16 supported): ADC_PREC=" + ADC_PREC)
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

			db.queue_measurement(influx.MeasurementTypes.co, co_ppm)
			success = db.write()
			# print("[CO_Test] Write to backend success: {}".format(success))
			if not success:
				print("[CO_Test] Write to InfluxDB failed!")

			time.sleep(MEASUREMENT_INTERVAL)
		# except KeyboardInterrupt:
		# 	db.kill()
		# 	break
		except Exception as e:  #KeyboardInterrupt:
			print("\n[air_node.py] Program termination triggered by {0}:\n\t({1})\n".format(type(e).__name__, e))
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
	if not HAVE_NO2_AND_OX:
		print("[NO2_OX_Test] This test requires connected ISBs for both one NO2-B43F and one OX-B431 sensor  (HAVE_NO2_AND_OX == False)")
		sys.exit()
	adc = None
	if ADC_PREC == 12:
		adc = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
	elif ADC_PREC == 16:
		adc = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
	if adc is None:
		print("[ERROR] Invalid ADC precision specified (only 12 or 16 supported): ADC_PREC=" + ADC_PREC)
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

	print('-' * 63)
	print('| {0:^10} | {1:^10} | {2:^10} | {3:^10} |'.format('Temp (°C)', 'Humid (%)', 'NO2 (ppm)', 'O3 (ppm)'))
	print('-' * 63)
	while True:
		try:
			if bme is None:
				try:
					temp = board_temperature() # if bme is None else bme.get_temperature()
				except:
					temp = 0.0
			else:
				temp = bme.get_temperature()
			humid = 0.0 if bme is None else bme.get_humidity()
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
				ox_ppm = ox_sensor.get_oxide_ppm_only(no2_ppm)
			else:
				ox_ppm = ox_sensor.ppm

			print('| {0:^10.4f} | {1:^10.4f} | {2:^10.4f} | {3:^10.4f} |'.format(temp, humid, no2_ppm, ox_ppm))
			time.sleep(MEASUREMENT_INTERVAL)
		# except KeyboardInterrupt:
		# 	db.kill()
		# 	break
		except Exception as e:  #KeyboardInterrupt:
			print("\n[air_node.py] Program termination triggered by {0}:\n\t({1})\n".format(type(e).__name__, e))
			# db.kill()
			# break
			die()


def Full_ISB_Test():
	""" Test circuit: 2 ADS1x15 ADC breakouts + 1 CO-B4 + 1 NO2-B43F + 1 OX-B431
	"""

	## Create two ADS1115 ADC (16-bit) instances or an ADS1015 ADC (12-bit) instances
	adc0 = None
	adc1 = None
	if ADC_PREC == 12:
		adc0 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
		adc1 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
	elif ADC_PREC == 16:
		adc0 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
		adc1 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
	if adc0 is None or adc1 is None:
		print("[ERROR] Invalid ADC precision specified (only 12 or 16 supported): ADC_PREC=" + ADC_PREC)
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

	print('-' * 66)
	print('| {0:^10} | {1:^10} | {2:^10} | {3:^10} | {4:^10} |'.format('Temp (°C)', 'Humid (%)', 'CO (ppm)', 'NO2 (ppm)', 'O3 (ppm)'))
	print('-' * 66)
	while True:
		try:
			# temp = board_temperature() if bme is None else bme.get_temperature()
			if bme is None:
				try:
					temp = board_temperature() # if bme is None else bme.get_temperature()
				except:
					temp = 0.0
			else:
				temp = bme.get_temperature()
			humid = 0.0 if bme is None else bme.get_humidity()
			co_ppm = co_sensor.ppm
			time.sleep(0.5)
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
				ox_ppm = ox_sensor.get_oxide_ppm_only(no2_ppm)
			else:
				ox_ppm = ox_sensor.ppm

			print('| {0:^10.4f} | {1:^10.4f} | {2:^10.4f} | {3:^10.4f} | {4:^10.4f} |'.format(temp, humid, co_ppm, no2_ppm, ox_ppm))
			time.sleep(MEASUREMENT_INTERVAL)
		except Exception as e:  #KeyboardInterrupt:
			print("\n[air_node.py] Program termination triggered by {0}:\n\t({1})\n".format(type(e).__name__, e))
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
	if ADC_PREC == 12:
		adc0 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
		adc1 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
	elif ADC_PREC == 16:
		adc0 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
		adc1 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
	if adc0 is None or adc1 is None:
		print("[ERROR] Invalid ADC precision specified (only 12 or 16 supported): ADC_PREC=" + ADC_PREC)
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

	print('-' * 53)
	print('| {0:^10} | {1:^10} | {2:^10} | {3:^10} | {4:^16} | {5:^16} | {6:^16} |'.format('Temp (°C)', 'CO (ppm)', 'NO2 (ppm)', 'O3 (ppm)', 'PM1 (#/cc)', 'PM2.5 (#/cc)', 'PM10 (#/cc)'))
	print('-' * 53)
	

	while True:
		try:
			# temp = board_temperature() if bme is None else bme.get_temperature()
			if bme is None:
				try:
					temp = board_temperature() # if bme is None else bme.get_temperature()
				except:
					temp = 0.0
			else:
				temp = bme.get_temperature()
			co_ppm = co_sensor.ppm
			time.sleep(0.5)
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
				ox_ppm = ox_sensor.get_oxide_ppm_only(no2_ppm)
			else:
				ox_ppm = ox_sensor.ppm

			pm = opc_n2.pm()
			pm1 = pm['PM1']
			pm25 = pm['PM2.5']
			pm10 = pm['PM10']

			print('| {0:^10.4f} | {1:^10.4f} | {2:^10.4f} | {3:^10.4f} | {4:^16.4f} | {5:^16.4f} | {6:^16.4f} |'.format(temp, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
			time.sleep(MEASUREMENT_INTERVAL)
		except Exception as e:  #KeyboardInterrupt:
			print("\n[air_node.py] Program termination triggered by {0}:\n\t({1})\n".format(type(e).__name__, e))
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
	if ADC_PREC == 12:
		adc0 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
		adc1 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
	elif ADC_PREC == 16:
		adc0 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
		adc1 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
	if adc0 is None or adc1 is None:
		print("[ERROR] Invalid ADC precision specified (only 12 or 16 supported): ADC_PREC=" + ADC_PREC)
		sys.exit(2)

	## Instantiate CO-B4 sensor:
	co_serial = '162030904'  ## Found on sticker on side of sensor
	co_op1_pin = A0 	## WE: Orange wire from Molex connector --> channel A0 of first ADC breakout
	co_op2_pin = A1 	## AE: Yellow wire from Molex connector --> channel A1 of first ADC breakout
	co_op1 = analog_in.AnalogIn(adc0, co_op1_pin)
	co_op2 = analog_in.AnalogIn(adc0, co_op2_pin)
	co_sensor = isb.CO(co_op1, co_op2, serial=co_serial)

	## Instantiate NO2-B43F sensor:
	no2_serial = '202931852'  ## Found on sticker on side of sensor
	no2_op1_pin = A2  ## WE: Orange wire from Molex connector --> channel A2 of first ADC breakout
	no2_op2_pin = A3  ## AE: Yellow wire from Molex connector --> channel A3 of first ADC breakout
	no2_op1 = analog_in.AnalogIn(adc0, no2_op1_pin)
	no2_op2 = analog_in.AnalogIn(adc0, no2_op2_pin)
	no2_sensor = isb.NO2(no2_op1, no2_op2, serial=no2_serial)

	## Instantiate OX-B431 sensor:
	ox_serial = '204930754'  ## Found on sticker on side of sensor
	ox_op1_pin = A0  ## WE: Orange wire from Molex connector --> channel A0 of second ADC breakout
	ox_op2_pin = A1 	## AE: Yellow wire from Molex connector --> channel A1 of second ADC breakout
	ox_op1 = analog_in.AnalogIn(adc1, ox_op1_pin)
	ox_op2 = analog_in.AnalogIn(adc1, ox_op2_pin)
	ox_sensor = isb.OX(ox_op1, ox_op2, serial=ox_serial)

	opc_n2.on()
	time.sleep(1)
	header = ''

	if INCLUDE_VOC:
		if INCLUDE_ECO2:
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
			if time.time() - timestamp >= HEADER_PRINT_INTERVAL:
				print(header)
				timestamp = time.time()

			# temp = board_temperature() if bme is None else bme.get_temperature()
			if bme is None:
				try:
					temp = board_temperature()
				except:
					temp = 0.0
			else:
				temp = bme.get_temperature()
			humid = 0.0 if bme is None else bme.get_humidity()
			co_ppm = co_sensor.ppm
			time.sleep(0.5)
			no2_ppm = no2_sensor.ppm
			time.sleep(0.5)
			if HAVE_NO2_AND_OX:  ## Obviously true for this test scenario
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
						influx.MeasurementTypes.t: temp,
						influx.MeasurementTypes.h: humid,
						influx.MeasurementTypes.co: co_ppm,
						influx.MeasurementTypes.no2: no2_ppm,
						influx.MeasurementTypes.ox: ox_ppm,
						influx.MeasurementTypes.p1: pm1,
						influx.MeasurementTypes.p25: pm25,
						influx.MeasurementTypes.p10: pm10,
					}
				)
			# db.queue_measurement_batch(payload)
			if db:
				db.queue_data_point(payload)
			# db.queue_data_line(payload)

			if INCLUDE_VOC:
				voc = sgp.get_tvoc() if sgp is not None else get_voc()
				# payload.update({ influx.MeasurementTypes.v: voc })
				# db.queue_measurement(influx.MeasurementTypes.v, voc)
				# db.queue_data_line({ influx.MeasurementTypes.v: voc })
				if db:
					db.queue_data_point({ influx.MeasurementTypes.v: voc })

				if INCLUDE_ECO2:  # and sgp is not None:
					eco2 = sgp.get_eco2()
					# db.queue_measurement(influx.MeasurementTypes.eco2, eco2)
					# db.queue_data_line({ influx.MeasurementTypes.eco2: eco2 })
					if db:
						db.queue_data_point({ influx.MeasurementTypes.eco2: eco2 })

					if SHOW_DATETIME:
						print(data_str.format(temp, humid, voc, eco2, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10) + '  [ {} ]'.format(get_datetime()))
					else:
						print(data_str.format(temp, humid, voc, eco2, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
				else:
					if SHOW_DATETIME:
						print(data_str.format(temp, humid, voc, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10) + '  [ {} ]'.format(get_datetime()))
					else:
						print(data_str.format(temp, humid, voc, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
			else:
				if SHOW_DATETIME:	
					print(data_str.format(temp, humid, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10) + '  [ {} ]'.format(get_datetime()))
				else:
					print(data_str.format(temp, humid, co_ppm, no2_ppm, ox_ppm, pm1, pm25, pm10))
			
			## Publish sensor measurements to the database
			# db.queue_measurement_batch(payload)
			# success = db.write()
			if db:
				success = db.flush()
				# print("[Full_Test_OPC_GPIO] Write to backend success: {}".format(success))
				if not success:
					print("[Full_Test_OPC_GPIO] Write to InfluxDB failed!  ({})".format(get_datetime()))
			time.sleep(MEASUREMENT_INTERVAL)
		except KeyboardInterrupt:
			opc_n2.off()
			die(exit=False)
			break
		except Exception as e:  #KeyboardInterrupt:
			print("\n[air_node.py] Program termination triggered by {0}:\n\t({1})\n".format(type(e).__name__, e))
			opc_n2.off()
			# db.kill()
			# print("DEAD @ {}".format(get_datetime()))
			die() #exit=False)
			# break


#------------------------------------------------------------------------------

def main():
	k33_usb_port = None 
	opc_usb_port = None 
	ports_dict = comports.get_com_ports(display_ports=False)
	for port in ports_dict.keys():
		desc = ports_dict[port]
		if 'USB-ISS' in desc:
			opc_usb_port = port
			print("\nUsing port '{}' for connecting the OPC-N2 sensor  ('{}')".format(port, desc))
		elif 'FT232R USB UART' in desc:
			k33_usb_port = port 
			print("\nUsing port '{}' for connecting the K33-ELG sensor  ('{}')".format(port, desc))

	try:
		## Instantiate K33-ELG sensor:
		co2_sensor = k33.K33(port=k33_usb_port) if k33_usb_port is not None else k33.K33()
		## Instantiate OPC-N2 sensor:
		opc_sensor = opcn2.OPC_N2(use_usb=True, usb_port=opc_usb_port) if opc_usb_port is not None else opcn2.OPC_N2()

		## Create two ADS1115 ADC (16-bit) instances or an ADS1015 ADC (12-bit) instances
		adc0 = None
		adc1 = None
		if ADC_PREC == 12:
			adc0 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
			adc1 = ads1015.ADS1015(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
		elif ADC_PREC == 16:
			adc0 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR0)
			adc1 = ads1115.ADS1115(i2c, gain=ADC_GAIN, address=ADC_I2C_ADDR1)
		if adc0 is None or adc1 is None:
			print("[ERROR] Invalid ADC precision specified (only 12 or 16 supported): ADC_PREC=" + ADC_PREC)
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

	except ValueError:
		die(msg="Critial exception occurred in 'main' (ValueError)")

#------------------------------------------------------------------------------

def die(msg="DEAD", exit=True):
	if db is not None:
		db.kill()
	death_text = "\n[air_node::die] {} @ {}".format(msg, get_datetime())
	print(death_text)
	with open(ERROR_LOGFILE, 'a') as f:
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

	if not DISPLAY_TEST_MENU:
		## Launch default test
		Full_Test_OPC_GPIO()
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

