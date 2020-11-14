import time
try:
	import isb_pynq as isb
	import mq7_pynq as mq7 
except (ImportError, ModuleNotFoundError):


MEASUREMENT_INTERVAL = 5     ## Seconds

co_serial = '162030907'  ## Found on sticker on side of sensor
co_op1_pin = 0 	## WE: Orange wire from Molex connector --> channel A0 of the PYNQ Grove Shield
co_op2_pin = 1 	## AE: Yellow wire from Molex connector --> channel A1 of the PYNQ Grove Shield

## Can specify WE/Aux Zero Offset values & Sensitivity constant provided on the ISB bag label
## Else, not specifying args (or passing None) will default to the standard/typical values 
## for the sensor type (provided in Table 2 of the ISB user manual)
co_sensor = isb.CO(co_op1_pin, co_op2_pin, serial=co_serial) #, we_offset=449, ae_offset=316, sensitivty=419, bme_sensor=bme)

## Instantiating a MQ7 sensor instance for value comparisons against the Alphasense CO-B4 ISB's readings 
mq7_pin = 5 	## A5 on the PYNQ's Arduino shield
co_sensor2 = mq7.MQ7(analogPin=mq7_pin)  #, vdd=3.3)

while True:
	try:
		co_ppm = co_sensor.ppm 
		print("[ISB]  CO concentration = {:04.2f} ppm".format(co_ppm))

		co_ppm2 = co_sensor2.ppm 
		print("[MQ7]  CO concentration = {:04.2f} ppm\n".format(co_ppm2))

		# db.queue_measurement(influx.MeasurementTypes.co, co_ppm)
		# success = db.write()
		# # print("[CO_Test] Write to backend success: {}".format(success))
		# if not success:
		# 	print("[CO_Test] Write to InfluxDB failed!")

		time.sleep(MEASUREMENT_INTERVAL)
	except KeyboardInterrupt:
	# 	db.kill()
		break
	except Exception as e:  #KeyboardInterrupt:
		print(f"\n[{__file__}] Program termination triggered by {type(e).__name__}:\n\t({e})\n")
		# db.kill()
		break
		# die()

