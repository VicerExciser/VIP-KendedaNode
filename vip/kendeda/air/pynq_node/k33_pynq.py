#!/usr/bin/env python3

import os
import sys
import signal
import time

from pynq import Overlay
from pynq import PL
from pynq.lib import MicroblazeLibrary

#=========================================================#
##  Global Configuration Options (to be changed by developers)

IOP_NAME = "PmodA"  # "Arduino"  # "PmodB"
ARDUINO_SDA = 20
ARDUINO_SCL = 21
## Pmod IIC pin options: 2, 3, 6, and 7 (all have internal pull-up resistors for enabling I2C communications)
PMOD_SDA = 6  ## or 2
PMOD_SCL = 7  ## or 3

CONTINUOUS_MEASUREMENT_MODE = True 	## True if the AnIn1 jumper is set for continuous measurement mode, else WakeUp pulses will need to be sent

STARTUP_DELAY = 5   ## Seconds (adjustable by writing new duration (1 byte) to EEPROM address 0x23C)
MEASUREMENT_PERIOD = 20 	## Time (in seconds) between start of two measurement cycles (adjust in EEPROM address 0xB0 (3 bytes))

#=========================================================#
##  Global Constant Values (leave these alone plz)

K33_ADDR = 0x68				## I2C address (default; 7-bits)
WRITE_BIT = 0
READ_BIT  = 1
WRITE_ADDR = (K33_ADDR << 1) + WRITE_BIT 	## Send byte 0xD0 for default address 0x68, or byte 0xFE for "any sensor" address 0x7F
READ_ADDR  = (K33_ADDR << 1) + READ_BIT 	## Send byte 0xD1 for default address 0x68, or byte 0xFF for "any sensor" address 0x7F

WRITE_CMD = 0x10 	## Write RAM Command byte's high nibble (must add the number of bytes to be written) --> e.g., WRITE_3_BYTES = 0x13
READ_CMD = 0x20 	## Read RAM Command byte's high nibble (must add the number of bytes to be read) --> e.g., READ_2_BYTES = 0x22
EEPROM_WRITE_CMD = 0x30
EEPROM_READ_CMD = 0x40

I2C_DELAY = 0.02  # (20 / 1000.0) 	## 20ms in seconds (for time.time.sleep())
DEFAULT_STARTUP_DELAY = 5           ## Seconds
DEFAULT_MEASUREMENT_PERIOD = 16     ## Seconds

SCR_REG = 0x60 			## The SCR (special control register)
STATUS_REG = 0x1D

CO2_REG = 0x0008		## Address in RAM, For reading CO2 concentration (ppm)
TEMP_REG = 0x0012 	## Address in RAM, For reading space temperature (C)
RH_REG = 0x0014		## Address in RAM, For reading relative humidity (%)

SINGLE_MEASURE_START_CMD = 0x35
CONTIN_MEASURE_START_CMD = 0x30
CONTIN_MEASURE_STOP_CMD = 0x31

RESPONSE_METADATA_BYTES = 2		## Length of a Write Response, and of all bytes of a Read Response other than returned Read Data bytes
                                ## ^ excluding the 7-bit I2C address + Read/Write bit (MSB in the diagrams below).
								## This includes the checksum (LSB) and command status byte (MSB), ignoring size of any data payload.

#=========================================================#

initialized = False
bus = None
base = None 
lib = None

#=========================================================#

""" Read RAM -- Master reads up to 16 bytes from Sensor's RAM.

Read Request:
+-----------+-----------+------------+-------------+-----------------+-------------+------------+-----------+
|           | 7-bit I2C | Read/Write |   Command   | Number of bytes |             |            |           |
|    I2C    |  address  |    bit     | high nibble |   Low nibble    |     RAM     |   Check    |    I2C    |
|   Start   |-----------|------------|-------------|-----------------|   address   |    sum     |   Stop    |
| Condition |    0x68   |  0 (write) |     0x2     |     0..0xF      |             |            | Condition |
|           |------------------------|-------------------------------|-------------|------------|           |
|           |       [ 1 byte ]       |          [ 1 byte ]           | [ 2 bytes ] | [ 1 byte ] |           |
+-----------+------------------------+-------------------------------+-------------+------------+-----------+

'Read Complete' Response:
+-----------+-----------+------------+-------------+--------+-----------------+------------+-----------+
|           | 7-bit I2C | Read/Write |   Command   | Status |                 |            |           |
|    I2C    |  address  |    bit     | high nibble |  bit   |      Read       |   Check    |    I2C    |
|   Start   |-----------|------------|----------------------|      Data       |    sum     |   Stop    |
| Condition |    0x68   |  1 (read)  |          0x21        |                 |            | Condition |
|           |------------------------|----------------------|-----------------|------------|           |
|           |       [ 1 byte ]       |       [ 1 byte ]     | [ 1..16 bytes ] | [ 1 byte ] |           |
+-----------+------------------------+----------------------+-----------------+------------+-----------+

'Read Incomplete' Response:
+-----------+-----------+------------+-------------+--------+-----------+-----------+
|           | 7-bit I2C | Read/Write |   Command   | Status | All other |           |
|    I2C    |  address  |    bit     | high nibble |  bit   |   bytes   |    I2C    |
|   Start   |-----------|------------|----------------------|-----------|   Stop    |
| Condition |    0x68   |  1 (read)  |          0x20        |    0x20   | Condition |
|           |------------------------|----------------------|-----------|           |
|           |       [ 1 byte ]       |       [ 1 byte ]     |           |           |
+-----------+------------------------+----------------------+-----------+-----------+
"""
def format_read_request(num_bytes, ram_address):
	""" See: p. 18 of http://senseair.jp/wp-content/uploads/2019/01/I2C-comm-guide-2_15.pdf """
	if not (0 <= num_bytes <= 0xF):
		raise ValueError("Maximum number of bytes to read is 0xF")
	request = [0x00]*4
	command = READ_CMD | num_bytes
	request[0] = command
	request[1] = (ram_address >> 8) & 0xFF  # ram_address & 0xFF00   # = (ram_address >> 8) << 8
	request[2] = ram_address & 0xFF
	request[3] = sum(request[:3]) & 0xFF 		## Checksum is the summation of bytes 0 + 1 + 2
	return request


def format_eeprom_read_request(num_bytes, eeprom_address):
	""" See: p. 19 of http://senseair.jp/wp-content/uploads/2019/01/I2C-comm-guide-2_15.pdf 
	(Available only in K22/K30/K33/K45/K50 versions)
	"""
	if not (0 <= num_bytes <= 0xF):
		raise ValueError("Maximum number of bytes to read is 0xF")
	request = [0x00]*4
	command = EEPROM_READ_CMD | num_bytes
	request[0] = command
	request[1] = (eeprom_address >> 8) & 0xFF 
	request[2] = eeprom_address & 0xFF
	request[3] = sum(request[:3]) & 0xFF 		## Checksum is the summation of bytes 0 + 1 + 2
	return request


""" Write RAM -- Master writes up to 16 bytes to Sensor's RAM.

Write Request:
+-----------+-----------+------------+-------------+-----------------+-------------+-----------------+------------+-----------+
|           | 7-bit I2C | Read/Write |   Command   | Number of bytes |             |                 |            |           |
|    I2C    |  address  |    bit     | high nibble |   Low nibble    |     RAM     |     Data to     |   Check    |    I2C    |
|   Start   |-----------|------------|-------------|-----------------|   address   |      Write      |    sum     |   Stop    |
| Condition |    0x68   |  0 (write) |     0x1     |     0..0xF      |             |                 |            | Condition |
|           |------------------------|-------------------------------|-------------|-----------------|------------|           |
|           |       [ 1 byte ]       |          [ 1 byte ]           | [ 2 bytes ] | [ 1..16 bytes ] | [ 1 byte ] |           |
+-----------+------------------------+-------------------------------+-------------+-----------------+------------+-----------+

'Write Complete' Response:
+-----------+-----------+------------+-------------+--------+------------+-----------+
|           | 7-bit I2C | Read/Write |   Command   | Status |            |           |
|    I2C    |  address  |    bit     | high nibble |  bit   |   Check    |    I2C    |
|   Start   |-----------|------------|----------------------|    sum     |   Stop    |
| Condition |    0x68   |  1 (read)  |          0x11        |            | Condition |
|           |------------------------|----------------------|------------|           |
|           |       [ 1 byte ]       |       [ 1 byte ]     | [ 1 byte ] |           |
+-----------+------------------------+----------------------+------------+-----------+

'Write Incomplete' Response:
+-----------+-----------+------------+-------------+--------+------------+-----------+
|           | 7-bit I2C | Read/Write |   Command   | Status |            |           |
|    I2C    |  address  |    bit     | high nibble |  bit   |   Check    |    I2C    |
|   Start   |-----------|------------|----------------------|    sum     |   Stop    |
| Condition |    0x68   |  1 (read)  |          0x10        |            | Condition |
|           |------------------------|----------------------|------------|           |
|           |       [ 1 byte ]       |       [ 1 byte ]     | [ 1 byte ] |           |
+-----------+------------------------+----------------------+------------+-----------+
"""
def format_write_request(num_bytes, ram_address, data):
	""" See: p. 18 of http://senseair.jp/wp-content/uploads/2019/01/I2C-comm-guide-2_15.pdf """
	# if num_bytes > 0xF:
	if not (0 <= num_bytes <= 0xF):
		raise ValueError("Maximum number of bytes to write is 0xF")
	request = [0x00]*(4+num_bytes)
	command = WRITE_CMD | num_bytes
	request[0] = command
	request[1] = (ram_address >> 8) & 0xFF 
	request[2] = ram_address & 0xFF
	## TODO: Possibly pack `data` into an iterable buffer of bytes (see struct.pack_into())
	for i in range(num_bytes):
		request[i+3] = data[i]
	request[-1] = sum(request[:-1]) & 0xFF
	return request


def format_eeprom_write_request(num_bytes, eeprom_address, data):
	""" See: p. 19 of http://senseair.jp/wp-content/uploads/2019/01/I2C-comm-guide-2_15.pdf 
	(Available only in K22/K30/K33/K45/K50 versions)
	"""
	if not (0 <= num_bytes <= 0xF):
		raise ValueError("Maximum number of bytes to write is 0xF")
	request = [EEPROM_WRITE_CMD | num_bytes]
	request.append((eeprom_address >> 8) & 0xFF)
	request.append(eeprom_address & 0xFF)
	for i in range(num_bytes):
		request.append(data[i])
	request.append(sum(request) & 0xFF)
	return request


#=========================================================#

def measurement_cycle():
	""" 
	A typical measurement cycle is broken into multiple steps:

		1.  Send "Initiate Measurement" Command to Sensor
		2.  Wait 16 seconds while device takes data
		3.  Read CO2, Temperature, and RH
		4.  Wait an additional 9 seconds to avoid internal heating
		    affecting measurement accuracy
	"""
	print("[measurement_cycle]  Invoking wake_sensor()")
	wake_sensor()
	print("[measurement_cycle]  Invoking start_single_measurement()")
	start_single_measurement()

	print("[measurement_cycle]  Waiting for 16 seconds while device takes data... ", end=' ')
	sys.stdout.flush()
	time.sleep(16)
	print("Done.")

	print("[measurement_cycle]  Invoking wake_sensor()")
	wake_sensor()
	print("[measurement_cycle]  Invoking read_temp()")
	temp_val = read_temp()

	time.sleep(0.02)		## Delay for 20ms
	print("[measurement_cycle]  Invoking wake_sensor()")
	wake_sensor()
	print("[measurement_cycle]  Invoking read_rh()")
	rh_val = read_rh()

	time.sleep(0.02)
	print("[measurement_cycle]  Invoking wake_sensor()")
	wake_sensor()
	print("[measurement_cycle]  Invoking read_co2()")
	co2_val = read_co2()

	if co2_val >= 0:
		print(f"\nCO2:  {co2_val} ppm\nTemp:  {temp_val} C\nRh:  {rh_val} %\n")
	else:
		print("\nChecksum failed / I2C communication failure occurred.\n")

	print("[measurement_cycle]  Sleeping for 9 seconds for data integrity.")
	print('-'*45, end='\n')
	time.sleep(9)


#=========================================================#

def continuous_measurement_cycle():
	start_continuous_measurement()
	time.sleep(STARTUP_DELAY)

	## ... TODO ...
	raise NotImplementedError


#=========================================================#

def loop():
	while True:
		if not CONTINUOUS_MEASUREMENT_MODE:
			measurement_cycle()
		else:
			try:
				continuous_measurement_cycle()
			except NotImplementedError:
				measurement_cycle()


#=========================================================#

def wake_sensor():
	## TODO: Check this method... adapted from flowchart (Figure 12) on p. 21-23 of http://senseair.jp/wp-content/uploads/2019/01/I2C-comm-guide-2_15.pdf
	if not initialized:
		initialize()
	""" 
	Step 1:
		Make pulse 1-0-1 on line SDA (~300us)
			-- OR --
		Send Start Condition, byte 0x00, then Stop Condition
	"""
	# bus.write(K33_ADDR, [0x00], 1)
	bus.write(WRITE_ADDR, [0x00], 1)
	## NOTE: ^ The above method does not work for waking a sensor in sleep mode (when AnIn1 jumper is not set)

	"""
	Step 2:
		Delay 1ms for Sensor WakeUp from SleepMode
	"""
	time.sleep(0.001)


#=========================================================#

def check_complete_bit_set(bit_index):
	""" Read STATUS_REG[bit_index] and return True if the bit flag at position `bit_index`
	indicates a "Read/Write Complete", else False for a "Read/Write Incomplete" response.

	NOTE: Contents of status register get parsed in MSB order, so a `bit_index` of 0 would 
	      check whether the least significant bit is set (which would be part of the checksum byte).

	For checking status of "single measurement" command, bit_index = 5
	For checking status of "start continuous measurement" command or
	                        "stop continuous measurement" command, bit_index = 6
	"""
	if not initialized:
		initialize()
	
	num_bytes_to_read = 2
	request = format_read_request(num_bytes_to_read, STATUS_REG) 	## Create a request packet for reading 2 bytes from STATUS_REG (0x1D)
	print(f"\n[check_complete_bit_set]  Request bytes:  {[hex(b) for b in request]}")
	# bus.write(READ_ADDR)
	bus.write(WRITE_ADDR, request, len(request))
	time.sleep(I2C_DELAY)

	resp_length = RESPONSE_METADATA_BYTES + num_bytes_to_read
	response = [0x00] * resp_length
	bus.read(READ_ADDR, response, resp_length)
	print(f"[check_complete_bit_set]  Response bytes:  {[hex(b) for b in response]}")

	# status = ((response[0] << 8) | response[1])
	status = ((response[3] << 8) | response[2])
	status_bin = bin(status)  #[2:][bit_index]
	print(status_bin)
	return status & (0x1 << bit_index)



def read_i2c_address():
	if not initialized:
		initialize()

	num_bytes_to_read = 1
	request = format_read_request(num_bytes_to_read, 0x20)
	print(f"[read_i2c_address]  Request bytes:  {[hex(b) for b in request]}")
	bus.write(WRITE_ADDR, request, len(request))
	time.sleep(I2C_DELAY)

	resp_length = RESPONSE_METADATA_BYTES + num_bytes_to_read
	response = [0x00] * resp_length
	bus.read(READ_ADDR, response, resp_length)
	print(f"[read_i2c_address]  Response bytes:  {[hex(b) for b in response]}\n")


#=========================================================#

def start_single_measurement():
	"""
	Start single measurement on K33 BLG/ELG:
	• Write 0x35 (“single measurement” command) to RAM address 0x60
	• Read RAM address 0x1D and check that bit 5 is set (1), bit set means sensor has
		received “measurement” command and will start measurement cycle
	• Wait 20s
	• Read RAM address 0x1D again and check that bit 5 is cleared (0), bit cleared
		means that “measurement” cycle has finished
	• Read CO2, temp, RH etc

	Check of bit 5 in RAM 0x1D can be skipped, however then it’s possible that sensor have
	not received the “single measurement” command or have not finished the measurement
	cycle and data read from sensor will be from previous measurement cycle. 
	"""
	if not initialized:
		initialize()
	# request = [0x11, 0x00, 0x60, 0x35, 0xA6]	## 5 byte request
	request = format_write_request(1, SCR_REG, [SINGLE_MEASURE_START_CMD])
	# bus.write(K33_ADDR, request, len(request))
	print(f"[start_single_measurement]  Request bytes:  {[hex(b) for b in request]}")
	bus.write(WRITE_ADDR, request, len(request))
	time.sleep(I2C_DELAY)

	## NOTE: The following is (at this point) purely experimental code

	'''
	resp_length = RESPONSE_METADATA_BYTES + 2 	## 2 byte response
	response = [0x00] * resp_length 
	bus.read(READ_ADDR, response, resp_length)
	time.sleep(I2C_DELAY)
	print(f"[start_single_measurement]  Response bytes:  {[hex(b) for b in response]}\n")
	'''
	
	TIMEOUT = 20
	start_t = time.monotonic()
	while not check_complete_bit_set(5):
		if abs(time.monotonic() - start_t) > TIMEOUT:
			print("[start_single_measurement]  FAILED: Measurement bit never set (Timed Out)")
			break
		time.sleep(5)

	time.sleep(20)

	start_t = time.monotonic()
	while check_complete_bit_set(5):
		if abs(time.monotonic() - start_t) > TIMEOUT:
			print("[start_single_measurement]  FAILED: Measurement bit never cleared (Timed Out)")
			break
		time.sleep(5)



#=========================================================#

def start_continuous_measurement():
	"""
	Start continuous measurement on K33 BLG/ELG:
	• Write 0x30 (“start continuous measurement” command) to RAM address 0x60
	• Read RAM address 0x1D and check that bit 6 is set (1), bit set means sensor has
		received “continuous measurement” command and will start a measurement cycle 
		after a 5 second start-up delay (NOTE: Start-up delay duration is adjustable)
	• Write 0x31 ("stop continuous measurement" command) to stop measurement.
	• Read RAM address 0x1D again and check that bit 6 is cleared (0), bit cleared
		means sensor has received "stop continuous measurement" command.

	Check of bit 6 in RAM 0x1D is only to verify that sensor actually received the commands.
	"""
	if not initialized:
		initialize()
	## Write 0x30 ("start continuous measurement" command) to RAM address 0x60 (special control register)
	request = format_write_request(1, SCR_REG, [CONTIN_MEASURE_START_CMD])
	print(f"[start_continuous_measurement]  Request bytes:  {[hex(b) for b in request]}")
	bus.write(WRITE_ADDR, request, len(request))
	time.sleep(I2C_DELAY)

	## FIXME: How to properly receive an I2C response...
	'''
	response = [0x00, 0x00] 	## 2 byte response
	bus.read(READ_ADDR, response, len(response))
	time.sleep(I2C_DELAY)
	print(f"[start_continuous_measurement]  Response1 bytes:  {[hex(b) for b in response]}\n")

	time.sleep(5)
	response = [0x00, 0x00] 	## 2 byte response
	bus.read(READ_ADDR, response, len(response))
	time.sleep(I2C_DELAY)
	print(f"[start_continuous_measurement]  Response2 bytes:  {[hex(b) for b in response]}\n")
	'''


#=========================================================#

def set_startup_delay(new_delay):
	""" Write desired start-up delay (in seconds) to EEPROM addres 0x23C (1 byte). """
	if not initialized:
		initialize()
	request = [0x31, (0x23C >> 8) & 0xFF, 0x23C & 0xFF, new_delay & 0xFF] 	## 0x31 = Write EEPROM command byte
	request.append(sum(request) & 0xFF)
	bus.write(WRITE_ADDR, request, len(request))
	response = [0x00, 0x00, 0x00, 0x00] 	## 4 byte response
	bus.read(READ_ADDR, response, len(response))
	time.sleep(I2C_DELAY)
	print(f"[set_startup_delay]\n\trequest = {[hex(b) for b in request]}\n\tresponse = {[hex(b) for b in response]}\n")


def set_measurement_period(new_period):
	""" Change measurement period (time between start of two measurement cycles): 
		Write desired period in seconds to EEPROM address 0xB0 (3 byte, most significant bit first).
	"""
	if not initialized:
		initialize()
	# request = [0x31, (0xB0 >> 8) & 0xFF, 0xB0 & 0xFF, new_period & 0xFF]
	period_bytes = [(((new_period & 0xFF0000) >> 16) & 0xFF), (((new_period & 0x00FF00) >> 8) & 0xFF), (new_period & 0xFF)]
	request = format_eeprom_write_request(3, 0xB0, period_bytes)
	# request.append(sum(request) & 0xFF)
	bus.write(WRITE_ADDR, request, len(request))
	response = [0x00, 0x00, 0x00, 0x00] 	## 4 byte response
	bus.read(READ_ADDR, response, len(response))
	time.sleep(I2C_DELAY)
	print(f"[set_measurement_period]\n\trequest = {[hex(b) for b in request]}\n\tresponse = {[hex(b) for b in response]}\n")


#=========================================================#

def read_co2():
	if not initialized:
		initialize()
	"""
	I2C Session structure:  [p. 13 of http://senseair.jp/wp-content/uploads/2019/01/I2C-comm-guide-2_15.pdf]
		1) Write I2C request [takes 120ms Max]
		2) Wait 1-20ms
		3) Read response [takes 120ms Max]
	"""
	co2 = 0

	## Begin Write Sequence
	# request = (0x22, 0x00, 0x08, 0x2A) 	## 4 byte request: 0x22 = Command (Read 2 bytes), 0x0008 = RAM address, 0x2A = Checksum
	num_bytes = 2
	ram_addr = CO2_REG  # 0x0008
	'''
	request = [0x00]*4
	command = READ_CMD + num_bytes
	request[0] = command
	request[1] = ram_addr & 0xFF00   # = (ram_addr >> 8) << 8
	request[2] = ram_addr & 0x00FF
	request[3] = sum(request[:3]) 		## Checksum is the summation of bytes 0 + 1 + 2
	'''
	request = format_read_request(num_bytes, ram_addr)

	print(f"[read_co2] Request bytes:  {[hex(b) for b in request]}")
	bus.write(WRITE_ADDR, request, len(request))
	"""
		We wait 10-20ms for the sensor to process our command.
		The sensor's primary duties are to accurately measure
		CO2 values. Waiting 10ms will ensure the data is 
		properly written to RAM.
	"""
	time.sleep(I2C_DELAY)

	## Begin Read Sequence
	"""
		Sensor we requested 2 bytes from the sensor (specified by the byte 0x22),
		we must read in a 4 byte response. This includes the payload, checksum,
		and command status byte.
	"""
	response = [0x00, 0x00, 0x00, 0x00] 	## 4 byte response
	bus.read(READ_ADDR, response, len(response))
	time.sleep(I2C_DELAY)

	'''
	co2 |= response[1] & 0xFF
	co2 <<= 8
	co2 |= response[2] & 0xFF
	'''
	co2 = ((response[1] & 0xFF) << 8) | (response[2] & 0xFF)

	# if bin(response[0])[-1] == '1':
	# if response[0] & 1:
	if response[0] == 0x21:
		print(">>> Request Complete.")
	elif response[0] == 0x20:
		print(">>> Request Incomplete!")
	else:
		print(f">>> UNKOWN REQUEST STATUS BYTE:  {hex(response[0])}")

	print(f"[read_co2] Response bytes:  {[hex(b) for b in response]}")

	checksum = sum(response[:3])  # = response[0] + response[1] + response[2]
	if checksum > 0 and checksum == response[3]:
		print("[read_co2] CHECKSUM CORRECT\n")
	else:
		print(f"[read_co2] CHECKSUM ERROR:\n  --> Received:  {hex(response[3])}\n  --> Expected:  {hex(checksum)}\n")
		return -1

	return co2 / 1.0


#=========================================================#

def read_temp():
	if not initialized:
		initialize()
	temp = 0
	request = format_read_request(2, TEMP_REG)
	print(f"[read_temp] Request bytes:  {[hex(b) for b in request]}")
	bus.write(WRITE_ADDR, request, len(request))
	time.sleep(I2C_DELAY)

	response = [0x00, 0x00, 0x00, 0x00] 	## 4 byte response
	bus.read(READ_ADDR, response, len(response))
	time.sleep(I2C_DELAY)

	temp = ((response[1] & 0xFF) << 8) | (response[2] & 0xFF)
	if response[0] == 0x21:
		print(">>> Request Complete.")
	elif response[0] == 0x20:
		print(">>> Request Incomplete!")
	else:
		print(f">>> UNKOWN REQUEST STATUS BYTE:  {hex(response[0])}")
	print(f"[read_temp] Response bytes:  {[hex(b) for b in response]}")

	checksum = sum(response[:3])  # = response[0] + response[1] + response[2]
	if checksum > 0 and checksum == response[3]:
		print("[read_temp] CHECKSUM CORRECT\n")
		return temp / 100.0
	print(f"[read_temp] CHECKSUM ERROR:\n  --> Received:  {hex(response[3])}\n  --> Expected:  {hex(checksum)}\n")
	return -1


#=========================================================#

def read_rh():
	if not initialized:
		initialize()
	rh = 0
	request = format_read_request(2, RH_REG)
	print(f"[read_rh] Request bytes:  {[hex(b) for b in request]}")
	bus.write(WRITE_ADDR, request, len(request))
	time.sleep(I2C_DELAY)

	response = [0x00, 0x00, 0x00, 0x00] 	## 4 byte response
	bus.read(READ_ADDR, response, len(response))
	time.sleep(I2C_DELAY)

	rh = ((response[1] & 0xFF) << 8) | (response[2] & 0xFF)
	if response[0] == 0x21:
		print(">>> Request Complete.")
	elif response[0] == 0x20:
		print(">>> Request Incomplete!")
	else:
		print(f">>> UNKOWN REQUEST STATUS BYTE:  {hex(response[0])}")
	print(f"[read_rh] Response bytes:  {[hex(b) for b in response]}")

	checksum = sum(response[:3])  # = response[0] + response[1] + response[2]
	if checksum > 0 and checksum == response[3]:
		print("[read_rh] CHECKSUM CORRECT\n")
		return rh / 100.0
	print(f"[read_rh] CHECKSUM ERROR:\n  --> Received:  {hex(response[3])}\n  --> Expected:  {hex(checksum)}\n")
	return -1


#=========================================================#

def initialize():
	global initialized, bus, base, lib
	if not initialized or bus is None:
		signal.signal(signal.SIGINT, handle_signal)
		signal.signal(signal.SIGTERM, handle_signal)

		base = Overlay('base.bit', download=(PL.bitfile_name.split('/')[-1] != 'base.bit'))
		if IOP_NAME.upper() == "ARDUINO":
			print(f"[initialize]  Using the {IOP_NAME} Microblaze on pins {ARDUINO_SDA} (SDA) & {ARDUINO_SCL} (SCL)")
			mb_info = base.iop_arduino
			lib = MicroblazeLibrary(mb_info, ['i2c'])
			bus = lib.i2c_open_device(0)
		else:
			print(f"[initialize]  Using the {IOP_NAME} Microblaze on pins {PMOD_SDA} (SDA) & {PMOD_SCL} (SCL)")
			if IOP_NAME.upper() == "PMODA":
				mb_info = base.iop_pmoda
			else:
				mb_info = base.iop_pmodb
			lib = MicroblazeLibrary(mb_info, ['i2c'])
			bus = lib.i2c_open(PMOD_SDA, PMOD_SCL)

		initialized = True
		print(f"[initialize]  AnIn1 Jumper Set?  -->  {CONTINUOUS_MEASUREMENT_MODE}")


def cleanup():
	global initialized, bus
	## Perform clean-up operations
	if bus is not None:
		bus.close()
	initialized = False
	print("[cleanup]  Finished.")


def handle_signal(signum, stack):
	print('\n[handle_signal]  Received: ', signum)
	cleanup()
	sys.exit(2)


def delay(ms=I2C_DELAY):
	s = float(ms) / 1000.00 
	time.sleep(s)


#=========================================================#

if __name__ == "__main__":
	initialize()
	# start_single_measurement()

	wake_sensor()
	read_i2c_address()

	if STARTUP_DELAY != DEFAULT_STARTUP_DELAY:
		print(f"Setting start-up delay to {STARTUP_DELAY} seconds ...")
		set_startup_delay(STARTUP_DELAY)
		time.sleep(5)

	if MEASUREMENT_PERIOD != DEFAULT_MEASUREMENT_PERIOD:
		print(f"Setting measurement period to {MEASUREMENT_PERIOD} seconds ...")
		set_measurement_period(MEASUREMENT_PERIOD)
		time.sleep(5)

	loop()


#=========================================================#
