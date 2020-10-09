"""
	Alphasense OPC-N2 driver (adapted from https://github.com/dhhagan/py-opc/blob/master/opc/__init__.py) 
	intended for applications on the Xilinx PYNQ-Z1 APSoC
"""
import os
import sys
import time
import struct
import functools
try:
	from . import Pmod
except:
	from pynq.lib import Pmod
from pynq.overlays.base import BaseOverlay
from pynq.lib import MicroblazeLibrary

## ==================================================================

TESTING = False			## If True, will only run the OPC '_test_*' functions
MOCK_MICROBLAZE = False
USE_RF2_PIN_SCHEME = False
HACKY_PING = False
RUN_FAN_POWER_TEST = False

LIB_PATH_PREFIX = "/home/xilinx/pynq/lib/pmod"
# OPC_PROGRAM = "opc_pmod.bin"

OFF = 0
ON  = 1
MAX_RETRIES = 4
RETRY_DELAY = 10 	## Seconds to wait in between reattempting failed on/off commands
SAMPLE_DELAY = 5	## Seconds to wait in between reading new sensor data

MSBFIRST = 'BIG_ENDIAN' 	## I believe the OPC is big endian
LSBFIRST = 'LITTLE_ENDIAN'	## I believe the IOP is little endian

## See: https://github.com/dhhagan/opcn2/blob/master/src/opcn2.cpp
OPC_CLK_SPEED = 500000
OPC_BIT_ORDER = MSBFIRST
OPC_DATA_MODE = 'SPI_MODE1'	## For SPI mode 1 on ARM-based controllers: Clock polarity = 0, Clock phase = 1  (source: https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Mode_numbers) 
OPC_CLK_POLAR = 0
OPC_CLK_PHASE = 1

MB_BIT_ORDER = LSBFIRST

if not USE_RF2_PIN_SCHEME:
	SCLK_PIN = 1
	MISO_PIN = 0
	MOSI_PIN = 4
	SS_PIN   = 5
else:
	SCLK_PIN = 3
	MISO_PIN = 2
	MOSI_PIN = 1
	SS_PIN   = 0

# CONFIG_IOP_SWITCH = 0x1
# OPC_ON            = 0x3
# OPC_OFF           = 0x5
# OPC_CLOSE         = 0x7
# READ_PM           = 0x9
# READ_HIST         = 0xB
# NUM_DEVICES       = 0xD
# READ_STATE        = 0xF

# command_byte = {
# 	"ON" : 0x0C,
# 	"OFF" : 0x03,
# 	"PING" : 0xCF,
# 	"PM" : 0x32,
# 	"HIST" : 0x30,
# 	"FIRM" : 0x12,
# 	"SN" : 0x10, 	## sn()
# 	"FAN" : 0x42,	## set_fan_power(power)
# }

## ==================================================================

def _shorts2float(lo_byte_pair, hi_byte_pair):
	""" 
	Takes in 2 unsigned short (integers) and packs their collective
	4 bytes into a floating point value, then returns that float.
	"""
	ba = bytearray(struct.pack("HH", lo_byte_pair, hi_byte_pair))
	[f] = struct.unpack('f', ba)
	return f


def _compare_arrays(resp, expected):
	same = functools.reduce(lambda x,y: map(lambda p,q: p == q, resp, expected), True)
	return same 


def _map_value(x, in_min, in_max, out_min, out_max):
	return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

def _translate(value, leftMin, leftMax, rightMin, rightMax):
	## Figure out how 'wide' each range is
	leftSpan = leftMax - leftMin
	rightSpan = rightMax - rightMin

	## Convert the left range into a 0-1 range (float)
	valueScaled = float(value - leftMin) / float(leftSpan)

	## Convert the 0-1 range into a value in the right range.
	return int(rightMin + (valueScaled * rightSpan))

'''
def maprange(a, b, s):
    (a1, a2), (b1, b2) = a, b
    return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))


a = [from_lower, from_upper]
b = [to_lower, to_upper]
'''


def _16bit_unsigned(LSB, MSB):
	"""Returns the combined LSB and MSB
	:param LSB: Least Significant Byte
	:param MSB: Most Significant Byte
	:type LSB: byte
	:type MSB: byte
	:rtype: 16-bit unsigned int
	"""
	return (MSB << 8) | LSB


def _calculate_float(byte_array):
	"""Returns an IEEE 754 float from an array of 4 bytes
	:param byte_array: Expects an array of 4 bytes
	:type byte_array: array
	:rtype: float
	"""
	if len(byte_array) != 4:
		return None

	'''
	msg_prefix = "[_calculate_float] "
	print(f"{msg_prefix}byte_array = {[hex(b) for b in byte_array]}")
	
	# if OPC_BIT_ORDER == MB_BIT_ORDER:
	pack_fstr = '4B'
	print(f" -->  Using '{pack_fstr}' as pack_str: f = {round(struct.unpack('f', struct.pack(pack_fstr, *byte_array))[0], 5)}")
	# else:
	# 	if OPC_BIT_ORDER == LSBFIRST:  ## Little endian
	pack_fstr = '<4B'
	print(f" -->  Using '{pack_fstr}' as pack_str: f = {round(struct.unpack('f', struct.pack(pack_fstr, *byte_array))[0], 5)}")
		# else: 	## Big endian
	pack_fstr = '>4B'
	print(f" -->  Using '{pack_fstr}' as pack_str: f = {round(struct.unpack('f', struct.pack(pack_fstr, *byte_array))[0], 5)}")
	'''

	f = struct.unpack('f', struct.pack('4B', *byte_array))[0]
	# f = struct.unpack('f', struct.pack(pack_fstr, *byte_array))[0]
	return round(f, 5)


def _calculate_mtof(mtof):
	"""Returns the average amount of time that particles in a bin
	took to cross the path of the laser [units -> microseconds]
	:param mtof: mass time-of-flight
	:type mtof: float
	:rtype: float
	"""
	return round((mtof / 3.0), 4)


def _calculate_temp(vals):
	"""Calculates the temperature in degrees celcius
	:param vals: array of bytes
	:type vals: array
	:rtype: float
	"""
	if len(vals) < 4:
		return None
	t = ((vals[3] << 24) | (vals[2] << 16) | (vals[1] << 8) | vals[0]) / 10.0
	return round(t, 4)


def _calculate_pressure(vals):
	"""Calculates the pressure in pascals
	:param vals: array of bytes
	:type vals: array
	:rtype: float
	"""
	if len(vals) < 4:
		return None
	return ((vals[3] << 24) | (vals[2] << 16) | (vals[1] << 8) | vals[0])


def _calculate_period(vals):
	"""Calculate the sampling period in seconds"""
	if len(vals) < 4:
		return None
	# if self.firmware['major'] < 16:
	# 	return ((vals[3] << 24) | (vals[2] << 16) | (vals[1] << 8) | vals[0]) / 12e6
	# else:
	return self._calculate_float(vals)

## ==================================================================

class OPC_Pmod():
	def __init__(self, pmod_ab='A', overlay=None, mb_info=None, wait=False):
		log_msg_prefix = f"[{self.__class__.__name__}] "

		if overlay is None:
			print(f"{log_msg_prefix}Downloading BaseOverlay('base.bit')")
			overlay = BaseOverlay("base.bit")

		if mb_info is None:
			mb_info = overlay.iop_pmoda if pmod_ab.upper() == 'A' else overlay.iop_pmodb

		self.lib = MicroblazeLibrary(mb_info, ['spi'])
		self.spi = self.lib.spi_open(SCLK_PIN, MISO_PIN, MOSI_PIN, SS_PIN)
		""" 
			^ Methods for the `spi` object:
				- configure(self, clk_phase, clk_polarity)
				- transfer(self, [write_data], [read_data], length)
				- get_num_devices(self)
				- open(self)
				- open_device(self)
				- close(self)
		"""

		# lib.spi_configure(spi, OPC_CLK_PHASE, OPC_CLK_POLAR)
		self.spi.configure(OPC_CLK_PHASE, OPC_CLK_POLAR)	 ## ^ Should be equivalent to the above command

		time.sleep(2)
		print(f"{log_msg_prefix}Invocation of spi_open() returned:  {self.spi}")

		if wait:
			self.wait()

		print(f"{log_msg_prefix}{self.read_info_string()}")
		print(f"{log_msg_prefix}Serial #:  {self.sn()}")

		self._pm_dict = {'PM1': 0.0, 'PM2.5': 0.0, 'PM10': 0.0}
		self._hist_dict = {}
		self.state = OFF
		print(f"{log_msg_prefix}Initialization complete.")


	def on(self):
		"""Turn ON the OPC (fan and laser)

		:returns: boolean success state
		"""
		rb0 = [0x00]
		rb1 = [0x00, 0x00]
		attempts = 0

		while self.state != ON and attempts < MAX_RETRIES:
			self.spi.transfer([0x03], rb0, 1)		## Send the command byte; response will be written to rb0
			time.sleep(9e-3) 						## Sleep for 9 ms
			self.spi.transfer([0x00, 0x01], rb1, 2)	## Send the following 2 bytes; response will be written to rb1
			time.sleep(0.1)

			if rb0[0] < 0: 						## Account for implicit unsigned-to-signed 
				rb0[0] += 256					## conversion from the transfer operation

			attempts += 1
			print(f"[{self.__class__.__name__}::on]", end=' ')
			if rb0[0] == 0xF3 and rb1[0] == 0x03: 	## Ensure response values are as expected
				self.state = ON 
				print("SUCCESS -- device powered on.")
			else:
				if attempts != MAX_RETRIES:
					print(f"Attempt #{attempts} failed -- retrying after delay ...")
					time.sleep(RETRY_DELAY)
				else:
					print("ERROR -- command failed.")

		return self.state == ON


	def off(self):
		rb0 = [0x00]
		rb1 = [0x00]
		attempts = 0

		while self.state != OFF and attempts < MAX_RETRIES:
			self.spi.transfer([0x03], rb0, 1)	## Send the command byte; response will be written to rb0
			time.sleep(9e-3) 					## Sleep for 9 ms
			self.spi.transfer([0x01], rb1, 1)	## Send the following byte; response will be written to rb1
			time.sleep(0.1)

			if rb0[0] < 0: 						## Account for implicit unsigned-to-signed 
				rb0[0] += 256					## conversion from the transfer operation

			attempts += 1
			print(f"[{self.__class__.__name__}::off]", end=' ')
			if rb0[0] == 0xF3 and rb1[0] == 0x03: 	## Ensure response values are as expected
				self.state = OFF 
				print("SUCCESS -- device powered off.")
			else:
				if attempts != MAX_RETRIES:
					print(f"Attempt #{attempts} failed -- retrying after delay ...")
					time.sleep(RETRY_DELAY)
				else:
					print("ERROR -- command failed.")

		return self.state == OFF 


	def wait(self, **kwargs):
		"""Wait for the OPC to prepare itself for data transmission. On some devides this can take a few seconds
		:rtype: self
		:Example:
		>> alpha = OPC_Pmod().wait(check=200)
		"""

		if not callable(self.on):
			raise UserWarning('Your device does not support the self.on function, try without wait')

		if not callable(self.histogram):
			raise UserWarning('Your device does not support the self.histogram function, try without wait')

		self.on()
		while True:
			try:
				if self.histogram() is None:
					raise UserWarning('Could not load histogram, perhaps the device is not yet connected')
				else:
					break

			except UserWarning as e:
				time.sleep(kwargs.get('check', 200) / 1000.)

		return self


	def reset(self):
		self.off()
		time.sleep(2)
		self.on()
		time.sleep(2)


	def close(self):
		if self.state != OFF:
			self.off()
		self.spi.close()
		# self.lib.spi_close(self.spi)  ## ^ Should be equivalent to the above close command


	def __del__(self):
		try:
			self.off()
		except:
			pass
		try:
			self.close()
		except:
			pass 


	def get_num_devices(self):
		return self.spi.get_num_devices()
		# return self.lib.spi_get_num_devices()  ## ^ Should be equivalent to the above command


	def pm(self):
		"""Read the PM data and reset the histogram

		**NOTE: This method is supported by firmware v18+.**

		:rtype: dictionary

		:Example:

		>>> alpha.pm()
		{
			'PM1': 0.12,
			'PM2.5': 0.24,
			'PM10': 1.42
		}
		"""

		resp = []
		self.spi.transfer([0x32], [0x00], 1)		## Send the command byte
		time.sleep(10e-3) 						## Wait 10 ms

		## Read the 12 bytes of PM data from the histogram
		for i in range(12):
			rb = [0x00]
			self.spi.transfer([0x00], rb, 1)
			if rb[0] < 0:
				rb[0] += 256
			resp.append(rb[0])

		## Make conversions to floats & store PM values
		self._pm_dict['PM1']   = _calculate_float(resp[:4])
		self._pm_dict['PM2.5'] = _calculate_float(resp[4:8])
		self._pm_dict['PM10']  = _calculate_float(resp[8:])

		time.sleep(0.1)
		return self._pm_dict


	def histogram(self, number_concentration=True):
		"""Read and reset the histogram. As of v1.3.0, histogram
		values are reported in particle number concentration (#/cc) by default.

		:param number_concentration: If true, histogram bins are reported in number concentration vs. raw values.

		:type number_concentration: boolean

		:rtype: dictionary

		:Example:

		>>> alpha.histogram()
		{
			'temperature': None,
			'pressure': None,
			'bin0': 0,
			'bin1': 0,
			'bin2': 0,
			...
			'bin15': 0,
			'sfr': 3.700,
			'bin1MToF': 0,
			'bin3MToF': 0,
			'bin5MToF': 0,
			'bin7MToF': 0,
			'PM1': 0.0,
			'PM2.5': 0.0,
			'PM10': 0.0,
			'period': 2.345,
			'checksum': 0
		}
		"""

		resp = []
		self.spi.transfer([0x30], [0x00], 1)
		time.sleep(10e-3)
		for i in range(62):
			rb = [0x00]
			self.spi.transfer([0x00], rb, 1)
			if rb[0] < 0:
				rb[0] += 256
			resp.append(rb[0])
		
		self._hist_dict['bin0'] = _16bit_unsigned(resp[0], resp[1])
		self._hist_dict['bin1'] = _16bit_unsigned(resp[2], resp[3])
		self._hist_dict['bin2'] = _16bit_unsigned(resp[4], resp[5])
		self._hist_dict['bin3'] = _16bit_unsigned(resp[6], resp[7])
		self._hist_dict['bin4'] = _16bit_unsigned(resp[8], resp[9])
		self._hist_dict['bin5'] = _16bit_unsigned(resp[10], resp[11])
		self._hist_dict['bin6'] = _16bit_unsigned(resp[12], resp[13])
		self._hist_dict['bin7'] = _16bit_unsigned(resp[14], resp[15])
		self._hist_dict['bin8'] = _16bit_unsigned(resp[16], resp[17])
		self._hist_dict['bin9'] = _16bit_unsigned(resp[18], resp[19])
		self._hist_dict['bin10'] = _16bit_unsigned(resp[20], resp[21])
		self._hist_dict['bin11'] = _16bit_unsigned(resp[22], resp[23])
		self._hist_dict['bin12'] = _16bit_unsigned(resp[24], resp[25])
		self._hist_dict['bin13'] = _16bit_unsigned(resp[26], resp[27])
		self._hist_dict['bin14'] = _16bit_unsigned(resp[28], resp[29])
		self._hist_dict['bin15'] = _16bit_unsigned(resp[30], resp[31])

		self._hist_dict['bin1_MToF'] = _calculate_mtof(resp[32])
		self._hist_dict['bin3_MToF'] = _calculate_mtof(resp[33])
		self._hist_dict['bin5_MToF'] = _calculate_mtof(resp[34])
		self._hist_dict['bin7_MToF'] = _calculate_mtof(resp[35])

		self._hist_dict['sfr'] = _calculate_float(resp[36:40])		## Sample flow rate

		## Alright, we don't know whether it is temp or pressure since it switches...
		tmp = _calculate_pressure(resp[40:44])
		if tmp > 98000:
			self._hist_dict['temperature'] = None
			self._hist_dict['pressure']    = tmp
		else:
			tmp = _calculate_temp(resp[40:44])
			if tmp < 500:
				self._hist_dict['temperature'] = tmp
				self._hist_dict['pressure']    = None
			else:
				self._hist_dict['temperature'] = None
				self._hist_dict['pressure']    = None

		self._hist_dict['period'] = _calculate_float(resp[44:48])		## Sampling period

		self._hist_dict['checksum'] = _16bit_unsigned(resp[48], resp[49])

		self._hist_dict['PM1']   = _calculate_float(resp[50:54])
		self._hist_dict['PM2.5'] = _calculate_float(resp[54:58])
		self._hist_dict['PM10']  = _calculate_float(resp[58:])

		## Calculate the sum of the histogram bins
		histogram_sum = self._hist_dict['bin0'] + self._hist_dict['bin1'] + self._hist_dict['bin2']   + \
				self._hist_dict['bin3'] + self._hist_dict['bin4'] + self._hist_dict['bin5'] + self._hist_dict['bin6']   + \
				self._hist_dict['bin7'] + self._hist_dict['bin8'] + self._hist_dict['bin9'] + self._hist_dict['bin10']  + \
				self._hist_dict['bin11'] + self._hist_dict['bin12'] + self._hist_dict['bin13'] + self._hist_dict['bin14'] + \
				self._hist_dict['bin15']

		## Check that checksum and the least significant bits of the sum of histogram bins are equivilant
		if (histogram_sum & 0x0000FFFF) != self._hist_dict['checksum']:
			print(f"[{self.__class__.__name__}::histogram] CHECKSUM ERROR: Data transfer was incomplete")
			return None

		## If number_concentration flag is set, convert histogram values to number concentration
		if number_concentration is True:
			_conv_ = self._hist_dict['sfr'] * self._hist_dict['period'] 	## Divider in units of ml (cc)

			self._hist_dict['bin0']  /= _conv_
			self._hist_dict['bin1']  /= _conv_
			self._hist_dict['bin2']  /= _conv_
			self._hist_dict['bin3']  /= _conv_
			self._hist_dict['bin4']  /= _conv_
			self._hist_dict['bin5']  /= _conv_
			self._hist_dict['bin6']  /= _conv_
			self._hist_dict['bin7']  /= _conv_
			self._hist_dict['bin8']  /= _conv_
			self._hist_dict['bin9']  /= _conv_
			self._hist_dict['bin10'] /= _conv_
			self._hist_dict['bin11'] /= _conv_
			self._hist_dict['bin12'] /= _conv_
			self._hist_dict['bin13'] /= _conv_
			self._hist_dict['bin14'] /= _conv_
			self._hist_dict['bin15'] /= _conv_

		time.sleep(0.1)
		return self._hist_dict 


	def ping(self):
		"""Checks the connection between the PYNQ and the OPC

		:rtype: Boolean
		"""
		## NOTE: the Microblaze can only accept byte values between -128 and 127 (so 0xCF is too large)
		rb = [0x00]

		# self.spi.transfer([0xCF], rb, 1)
		# mapped_cmd_byte = [_map_value(0xCF, 0, 255, -128, 127)]
		mapped_cmd_byte = [0xCF-128]
		self.spi.transfer(mapped_cmd_byte, rb, 1)

		time.sleep(0.1)
		if rb[0] < 0: 						## Account for implicit unsigned-to-signed 
			rb[0] += 256					## conversion from the transfer operation
		return rb[0] == 0xF3


	def sn(self):
		"""Read the Serial Number string. This method is only available on OPC-N2
        firmware versions 18+.

        :rtype: string

        :Example:

        >>> alpha.sn()
        'OPC-N2 123456789'
        """
		string = []
		resp = [0x00]
		self.spi.transfer([0x10], [0x00], 1)
		time.sleep(9e-3)
		for i in range(60):
			self.spi.transfer([0x00], resp, 1)
			string.append(chr(resp[0]))
		time.sleep(0.1)
		return ''.join(string).strip()


	def read_info_string(self):
		"""Reads the information string for the OPC

		:rtype: string

		:Example:

		>>> alpha.read_info_string()
		'OPC-N2 FirmwareVer=OPC-018.2....................BD'
		"""
		infostring = []

		## Send the command byte and sleep for 9 ms
		self.spi.transfer([0x3F], [0x00], 1)
		time.sleep(9e-3)

		## Read the info string by sending 60 empty bytes
		for i in range(60):
			resp = [0x00]
			self.spi.transfer([0x00], resp, 1)
			infostring.append(chr(resp[0]))

		time.sleep(0.1)
		return ''.join(infostring).strip()

	
	def firmware_version(self):
		info = self.read_info_string()
		return info[info.index('FirmwareVer='):info.index('...')]


	def set_fan_power(self, power):
		## TODO
		if not 0 <= power <= 255:
			raise ValueError("The fan power should be a single byte (0-255).")

		# mapped_pval = [_map_value(power, 0, 255, -128, 127)]
		# mapped_pval = [power-128]
		# mapped_pval = [(power // 2)-128]
		## ^ NOTE: Apparently max power occurs when mapped_pval = 127 (0x7F)
		# if power <= 127:
		# 	mapped_pval = [_translate(power, 0, 127, -128, 0)]
		# else:
		# 	mapped_pval = [_translate(power, 128, 255, 0, 127)]
		mapped_pval = [_translate(power, 0, 255, -128, -1)]

		rb0 = [0x00]
		rb1 = [0x00]
		rb2 = [0x00]

		## Send command byte & wait 10 ms
		self.spi.transfer([0x42], rb0, 1)
		time.sleep(10e-3)

		## Send the next 2 bytes to set the fan power level
		self.spi.transfer([0x00], rb1, 1)

		# self.spi.transfer([power], rb2, 1)
		self.spi.transfer(mapped_pval, rb2, 1)
		time.sleep(0.1)

		if rb0[0] < 0:
			rb0[0] += 256
		if rb1[0] < 0:
			rb1[0] += 256

		success = (rb0[0] == 0xF3) and (rb1[0] == 0x42) and (rb2[0] == 0x00)

		print(f"[{self.__class__.__name__}::set_fan_power]", end=' ')
		if success:
			print(f"Fan power level set to {power}  ({mapped_pval[0]})")
		else:
			print("ERROR: Failed to set OPC fan power level")

		return success
			

	def toggle_fan(self, state):
		if state not in (OFF, ON):
			raise ValueError("The fan state must be 0|False or 1|True.")

		rb0 = [0x00]
		rb1 = [0x00]

		self.spi.transfer([0x03], rb0, 1)
		time.sleep(10e-3)

		self.spi.transfer([0x05-state], rb1, 1) 	## Write 0x04 to turn ON, else 0x05 for OFF
		time.sleep(0.1)

		if rb0[0] < 0:
			rb0[0] += 256

		success = (rb0[0] == 0xF3) and (rb1[0] == 0x03)

		print(f"[{self.__class__.__name__}::toggle_fan]", end=' ')
		if success:
			print(f"Fan toggled to {'OFF' if state == OFF else 'ON'}")
		else:
			print("ERROR: Failed to toggle OPC fan power")

		return success 


## ==================================================================

def ping_test(opc):
	print(">>> Pinging device ...")
	ping = opc.ping()
	time.sleep(1)
	if not ping:
		print(">>> ERROR: Ping failed -- device is unreachable.\n>>> Aborting operation.")
		sys.exit(1)
	print(">>> Ping successful -- device is reachable.")
	print('='*60, end='\n\n')

## ==================================================================

def fan_power_test(opc):
	print(">>> START set_fan_power test:")
	# for level in range(256):
	level = 0
	while level < 256:
		opc.set_fan_power(level)
		level += 5
		time.sleep(1)
	print("\n>>> END set_fan_power test.")
	# opc.toggle_fan(opc.state)	## Restore previous fan state
	opc.toggle_fan(OFF)
	time.sleep(0.5)
	opc.toggle_fan(ON)
	print('='*60, end='\n\n')

## ==================================================================

if __name__ == "__main__":
	print(">>> Instantiating OPC_Pmod object ...")
	opc = OPC_Pmod()
	enabled = False

	if not MOCK_MICROBLAZE:
		print(">>> Initial OPC_Pmod state:", end='  ')
		sys.stdout.flush()

		print('OFF' if opc.state == OFF else 'ON')
		print(">>> Turning the OPC_Pmod on ...")
		enabled = opc.on()
		time.sleep(4)

		assert(enabled)

		print(">>> New OPC_Pmod state:", end='  ')
		sys.stdout.flush()
		print('OFF' if opc.state == OFF else 'ON')

	print('='*60, end='\n\n')
	
	time.sleep(1)
	ping_test(opc)

	if RUN_FAN_POWER_TEST:
		fan_power_test(opc)

	for i in range(10):
		pm = opc.pm()
		print(pm)
		print('='*60)
		time.sleep(SAMPLE_DELAY)

	if not MOCK_MICROBLAZE:
		print(">>> Turning the OPC_Pmod off ...")
		enabled = opc.off()
		assert(enabled)
		print(">>> Final OPC_Pmod state:", end='  ')
		sys.stdout.flush()
		print('OFF' if opc.state == OFF else 'ON')
		
