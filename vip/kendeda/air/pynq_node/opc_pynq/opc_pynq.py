"""
	Alphasense OPC-N2 driver (adapted from https://github.com/dhhagan/py-opc/blob/master/opc/__init__.py) 
	intended for applications on the Xilinx PYNQ-Z1 APSoC.

	Contains the following classes:

		OPC_Pmod    -  For driving an OPC-N2 via PmodA or PmodB
		OPC_Arduino -  For driving an OPC-N2 via Arduino header (digital pins IO10-13)
		OPC_USB     -  For driving an OPC-N2 connected to the USB Host via USB-ISS adapter


	All above subclasses inherit the following methods from the _OPC_Base class:

		on()
		off()
		wait()
		reset()
		close()
		pm()
		histogram()
		ping()
		sn()
		read_info_string()
		firmware_version()
		set_fan_power()
		toggle_fan()
"""
import os
import sys
import time
import struct
import functools
from pynq.lib import MicroblazeLibrary

## ==================================================================

TESTING = False			## If True, will only run the OPC '_test_*' functions
MOCK_MICROBLAZE = False
RUN_FAN_POWER_TEST = False
INFINITE_POLL = False

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
FP_PRECISION = 5

## ==================================================================

class _OPC_Base:

	def __init__(self, overlay=None):
		log_msg_prefix = f"[{self.__class__.__name__}] "

		if overlay is None:
			from pynq import Overlay, PL
			already_downloaded = PL.bitfile_name.split('/')[-1] == 'base.bit'
			if not already_downloaded:
				self.log(log_msg_prefix, "Downloading Overlay('base.bit')")
			overlay = Overlay('base.bit', download=(not already_downloaded))
		
		self._overlay = overlay 
		self._lib = None 
		self.spi = None 

		self._pm_dict = {'PM1': 0.0, 'PM2.5': 0.0, 'PM10': 0.0}
		self._hist_dict = {}
		self.state = OFF


	def log(self, prefix, msg, end='\n'):
		print(f"{prefix} {msg}", end=end)


	def _shorts2float(self, lo_byte_pair, hi_byte_pair):
		""" 
		Takes in 2 unsigned short (integers) and packs their collective
		4 bytes into a floating point value, then returns that float.
		"""
		ba = bytearray(struct.pack("HH", lo_byte_pair, hi_byte_pair))
		[f] = struct.unpack('f', ba)
		return f


	def _compare_arrays(self, resp, expected):
		same = functools.reduce(lambda x,y: map(lambda p,q: p == q, resp, expected), True)
		return same 


	def _map_value(self, x, in_min, in_max, out_min, out_max):
		return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min


	def _translate(self, value, leftMin, leftMax, rightMin, rightMax):
		## Figure out how 'wide' each range is
		leftSpan = leftMax - leftMin
		rightSpan = rightMax - rightMin

		## Convert the left range into a 0-1 range (float)
		valueScaled = float(value - leftMin) / float(leftSpan)

		## Convert the 0-1 range into a value in the right range.
		return int(rightMin + (valueScaled * rightSpan))


	def _16bit_unsigned(self, LSB, MSB):
		"""Returns the combined LSB and MSB
		:param LSB: Least Significant Byte
		:param MSB: Most Significant Byte
		:type LSB: byte
		:type MSB: byte
		:rtype: 16-bit unsigned int
		"""
		return (MSB << 8) | LSB


	def _calculate_float(self, byte_array):
		"""Returns an IEEE 754 float from an array of 4 bytes
		:param byte_array: Expects an array of 4 bytes
		:type byte_array: array
		:rtype: float
		"""
		if len(byte_array) != 4:
			return None
		f = struct.unpack('f', struct.pack('4B', *byte_array))[0]
		return round(f, FP_PRECISION)


	def _calculate_mtof(self, mtof):
		"""Returns the average amount of time that particles in a bin
		took to cross the path of the laser [units -> microseconds]
		:param mtof: mass time-of-flight
		:type mtof: float
		:rtype: float
		"""
		return round((mtof / 3.0), FP_PRECISION)


	def _calculate_temp(self, vals):
		"""Calculates the temperature in degrees celcius
		:param vals: array of bytes
		:type vals: array
		:rtype: float
		"""
		if len(vals) < 4:
			return None
		t = ((vals[3] << 24) | (vals[2] << 16) | (vals[1] << 8) | vals[0]) / 10.0
		return round(t, FP_PRECISION)


	def _calculate_pressure(self, vals):
		"""Calculates the pressure in pascals
		:param vals: array of bytes
		:type vals: array
		:rtype: float
		"""
		if len(vals) < 4:
			return None
		return ((vals[3] << 24) | (vals[2] << 16) | (vals[1] << 8) | vals[0])


	def _calculate_period(self, vals):
		"""Calculate the sampling period in seconds"""
		if len(vals) < 4:
			return None
		# if self.firmware['major'] < 16:
		# 	return ((vals[3] << 24) | (vals[2] << 16) | (vals[1] << 8) | vals[0]) / 12e6
		# else:
		return self._calculate_float(vals)

## - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

	def on(self, force=False):
		"""Turn ON the OPC (fan and laser)

		:returns: boolean success state
		"""
		rb0 = [0x00]
		rb1 = [0x00, 0x00]
		attempts = 0

		if force:
			self.state = OFF 

		while self.state != ON and attempts < MAX_RETRIES:
			self.spi.transfer([0x03], rb0, 1)		## Send the command byte; response will be written to rb0
			time.sleep(9e-3) 						## Sleep for 9 ms
			self.spi.transfer([0x00, 0x01], rb1, 2)	## Send the following 2 bytes; response will be written to rb1
			time.sleep(0.1)

			if rb0[0] < 0: 						## Account for implicit unsigned-to-signed 
				rb0[0] += 256					## conversion from the transfer operation

			attempts += 1
			self.log(self.log_msg_prefix, '', end='')
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


	def off(self, force=False):
		rb0 = [0x00]
		rb1 = [0x00]
		attempts = 0

		if force:
			self.state = ON 

		while self.state != OFF and attempts < MAX_RETRIES:
			self.spi.transfer([0x03], rb0, 1)	## Send the command byte; response will be written to rb0
			time.sleep(9e-3) 					## Sleep for 9 ms
			self.spi.transfer([0x01], rb1, 1)	## Send the following byte; response will be written to rb1
			time.sleep(0.1)

			if rb0[0] < 0: 						## Account for implicit unsigned-to-signed 
				rb0[0] += 256					## conversion from the transfer operation

			attempts += 1
			self.log(self.log_msg_prefix, '', end='')
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


	def reset(self, force=False):
		self.off(force=force)
		time.sleep(2)
		self.on(force=force)
		time.sleep(2)


	def close(self, force=False):
		if not force:
			if self.state != OFF:
				self.off()
		else:
			self.off(force=force)
		time.sleep(0.25)
		self.spi.close()
		# self.lib.spi_close(self.spi)  ## ^ Should be equivalent to the above close command


	def __del__(self):
		try:
			self.close(force=True)
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
		self._pm_dict['PM1']   = self._calculate_float(resp[:4])
		self._pm_dict['PM2.5'] = self._calculate_float(resp[4:8])
		self._pm_dict['PM10']  = self._calculate_float(resp[8:])

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
		
		self._hist_dict['bin0']  = self._16bit_unsigned(resp[0],  resp[1])
		self._hist_dict['bin1']  = self._16bit_unsigned(resp[2],  resp[3])
		self._hist_dict['bin2']  = self._16bit_unsigned(resp[4],  resp[5])
		self._hist_dict['bin3']  = self._16bit_unsigned(resp[6],  resp[7])
		self._hist_dict['bin4']  = self._16bit_unsigned(resp[8],  resp[9])
		self._hist_dict['bin5']  = self._16bit_unsigned(resp[10], resp[11])
		self._hist_dict['bin6']  = self._16bit_unsigned(resp[12], resp[13])
		self._hist_dict['bin7']  = self._16bit_unsigned(resp[14], resp[15])
		self._hist_dict['bin8']  = self._16bit_unsigned(resp[16], resp[17])
		self._hist_dict['bin9']  = self._16bit_unsigned(resp[18], resp[19])
		self._hist_dict['bin10'] = self._16bit_unsigned(resp[20], resp[21])
		self._hist_dict['bin11'] = self._16bit_unsigned(resp[22], resp[23])
		self._hist_dict['bin12'] = self._16bit_unsigned(resp[24], resp[25])
		self._hist_dict['bin13'] = self._16bit_unsigned(resp[26], resp[27])
		self._hist_dict['bin14'] = self._16bit_unsigned(resp[28], resp[29])
		self._hist_dict['bin15'] = self._16bit_unsigned(resp[30], resp[31])

		self._hist_dict['bin1_MToF'] = self._calculate_mtof(resp[32])
		self._hist_dict['bin3_MToF'] = self._calculate_mtof(resp[33])
		self._hist_dict['bin5_MToF'] = self._calculate_mtof(resp[34])
		self._hist_dict['bin7_MToF'] = self._calculate_mtof(resp[35])

		self._hist_dict['sfr'] = self._calculate_float(resp[36:40])		## Sample flow rate

		## Alright, we don't know whether it is temp or pressure since it switches...
		tmp = self._calculate_pressure(resp[40:44])
		if tmp > 98000:
			self._hist_dict['temperature'] = None
			self._hist_dict['pressure']    = tmp
		else:
			tmp = self._calculate_temp(resp[40:44])
			if tmp < 500:
				self._hist_dict['temperature'] = tmp
				self._hist_dict['pressure']    = None
			else:
				self._hist_dict['temperature'] = None
				self._hist_dict['pressure']    = None

		self._hist_dict['period'] = self._calculate_float(resp[44:48])		## Sampling period

		self._hist_dict['checksum'] = self._16bit_unsigned(resp[48], resp[49])

		self._hist_dict['PM1']   = self._calculate_float(resp[50:54])
		self._hist_dict['PM2.5'] = self._calculate_float(resp[54:58])
		self._hist_dict['PM10']  = self._calculate_float(resp[58:])

		## Calculate the sum of the histogram bins
		histogram_sum = self._hist_dict['bin0'] + self._hist_dict['bin1'] + self._hist_dict['bin2']   + \
				self._hist_dict['bin3'] + self._hist_dict['bin4'] + self._hist_dict['bin5'] + self._hist_dict['bin6']   + \
				self._hist_dict['bin7'] + self._hist_dict['bin8'] + self._hist_dict['bin9'] + self._hist_dict['bin10']  + \
				self._hist_dict['bin11'] + self._hist_dict['bin12'] + self._hist_dict['bin13'] + self._hist_dict['bin14'] + \
				self._hist_dict['bin15']

		## Check that checksum and the least significant bits of the sum of histogram bins are equivilant
		if (histogram_sum & 0x0000FFFF) != self._hist_dict['checksum']:
			self.log(self.log_msg_prefix, "CHECKSUM ERROR: Histogram data transfer was incomplete")
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
			infostring.append(chr(resp[0] & 0xFF))

		time.sleep(0.1)
		return ''.join(infostring).strip()

	
	def firmware_version(self):
		info = self.read_info_string()
		return info[info.index('FirmwareVer='):info.index('...')]


	def set_fan_power(self, power):
		if not 0 <= power <= 255:
			raise ValueError("The fan power should be a single byte (0-255).")

		mapped_pval = [self._translate(power, 0, 255, -128, -1)]
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

		self.log(self.log_msg_prefix, '', end=' ')
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

		self.log(self.log_msg_prefix, '', end=' ')
		if success:
			print(f"Fan toggled to {'OFF' if state == OFF else 'ON'}")
		else:
			print("ERROR: Failed to toggle OPC fan power")

		return success 


## ==================================================================

class OPC_Pmod(_OPC_Base):
	""" 
	Methods inherited from _OPC_Base:
		- log(self, prefix, msg, end='\n')
		- on(self, force=False)
		- off(self, force=False)
		- wait(self, **kwargs)
		- reset(self, force=False)
		- close(self, force=False)
		- pm(self)
		- histogram(self, number_concentration=True)
		- ping(self)
		- sn(self)
		- read_info_string(self)
		- firmware_version(self)
		- set_fan_power(self, power)
		- toggle_fan(self, state)
	"""

	PMOD_SCLK_PIN = 1
	PMOD_MISO_PIN = 0
	PMOD_MOSI_PIN = 4
	PMOD_SS_PIN   = 5

	def __init__(self, pmod_ab='A', overlay=None, mb_info=None, wait=False):
		super().__init__(overlay)

		self.log_msg_prefix = f"[{self.__class__.__name__}] "

		if mb_info is None:
			mb_info = self._overlay.iop_pmoda if pmod_ab.upper() == 'A' else self._overlay.iop_pmodb

		self._lib = MicroblazeLibrary(mb_info, ['spi'])
		self.spi = self._lib.spi_open(self.PMOD_SCLK_PIN, self.PMOD_MISO_PIN, self.PMOD_MOSI_PIN, self.PMOD_SS_PIN)
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
		self.log(self.log_msg_prefix, f"Invocation of spi_open() returned:  {self.spi}")
		self.log(self.log_msg_prefix, f"# of SPI devices found:  {self.get_num_devices()}")

		if wait:
			self.wait()

		self.log(self.log_msg_prefix, f"{self.read_info_string()}")
		self.log(self.log_msg_prefix, f"Serial #:  {self.sn()}")
		assert self.off(force=True)
		self.log(self.log_msg_prefix, "Initialization complete.")


## ==================================================================

class OPC_Arduino(_OPC_Base):
	""" 
	Methods inherited from _OPC_Base:
		- log(self, prefix, msg, end='\n')
		- on(self, force=False)
		- off(self, force=False)
		- wait(self, **kwargs)
		- reset(self, force=False)
		- close(self, force=False)
		- pm(self)
		- histogram(self, number_concentration=True)
		- ping(self)
		- sn(self)
		- read_info_string(self)
		- firmware_version(self)
		- set_fan_power(self, power)
		- toggle_fan(self, state)
	"""

	ARDUINO_SCLK_PIN = 13
	ARDUINO_MISO_PIN = 12
	ARDUINO_MOSI_PIN = 11
	ARDUINO_SS_PIN   = 10

	def __init__(self, overlay=None, mb_info=None, wait=False):
		super().__init__(overlay)

		self.log_msg_prefix = f"[{self.__class__.__name__}] "

		if mb_info is None:
			mb_info = self._overlay.iop_arduino

		self._lib = MicroblazeLibrary(mb_info, ['spi'])
		self.spi = self._lib.spi_open(self.ARDUINO_SCLK_PIN, self.ARDUINO_MISO_PIN, self.ARDUINO_MOSI_PIN, self.ARDUINO_SS_PIN)
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
		self.log(self.log_msg_prefix, f"Invocation of spi_open() returned:  {self.spi}")
		self.log(self.log_msg_prefix, f"# of SPI devices found:  {self.get_num_devices()}")

		if wait:
			self.wait()

		self.log(self.log_msg_prefix, f"{self.read_info_string()}")
		self.log(self.log_msg_prefix, f"Serial #:  {self.sn()}")
		assert self.off(force=True)
		self.log(self.log_msg_prefix, "Initialization complete.")


## ==================================================================

class OPC_USB(_OPC_Base):

	def __init__(self, overlay=None, port="/dev/ttyACM0", wait=False):
		super().__init__(overlay=overlay)
		self.log_msg_prefix = f"[{self.__class__.__name__}] "

		import opc      ## Pypi package name:  py-opc
		from opc.exceptions import FirmwareVersionError
		from usbiss.spi import SPI
		self.port = port
		self.spi = SPI(self.port)

		 ## Set the SPI mode and clock speed
		self.spi.mode = 1
		self.spi.max_speed_hz = OPC_CLK_SPEED
		self._prev_pm = None
		self._last_read_time = 0
		self._opcn2 = None
		spi_err_cnt = 0

		original_stdout = sys.stdout 
		sys.stdout = open('/dev/null', 'w')
		while self._opcn2 is None and spi_err_cnt < 5:
			try:
				self._opcn2 = opc.OPCN2(self.spi)
			except FirmwareVersionError as fve:
				spi_err_cnt += 1
				print("[OPC_N2] FirmwareVersionError #{} caught, check power supply ...".format(spi_err_cnt))
				print("\t{0}: {1}".format(type(fve).__name__, fve))
				time.sleep(1)
			except IndexError as ie:
				spi_err_cnt += 1
				print("[OPC_N2] py-opc incurred an IndexError, ignoring ...")
				print("\t{0}: {1}".format(type(ie).__name__, ie))
				time.sleep(0.5)
		sys.stdout = original_stdout

		time.sleep(1)
		# if self._opcn2:
		# 	self.log(self.log_msg_prefix, f"USB Optical Particle Counter initialized ({self.port}) after {spi_err_cnt+1} attempts.")
		# else:
		if self._opcn2 is None:
			raise ValueError(f"\n{self.log_msg_prefix} ERROR: INIT FAILED AFTER {spi_err_cnt+1} ATTEMPTS (SPI bus error for {self.port})\n")
		
		if wait:
			self.wait()

		self.log(self.log_msg_prefix, f"{self.read_info_string()}")
		self.log(self.log_msg_prefix, f"Serial #:  {self.sn()}")
		self.log(self.log_msg_prefix, f"Port:  {self.port}")
		assert self.off(force=True)
		self.log(self.log_msg_prefix, f"Initialization complete after {spi_err_cnt+1} attempts.")

		
	## Overriden method
	def on(self, force=False):
		if force:
			self.state = OFF 
		if self.state == OFF:
			self._opcn2.on()
			self.state = ON
			time.sleep(3)    ## Give it some time to warm up
		if self.state == ON:
			self.log(self.log_msg_prefix, "SUCCESS -- device powered on.")
			return True
		self.log(self.log_msg_prefix, "ERROR -- command failed.")
		return False

	## Overriden method
	def off(self, force=False):
		if force:
			self.state = ON 
		if self.state == ON:
			self._opcn2.off()
			self.state = OFF
			time.sleep(1)
		if self.state == OFF:
			self.log(self.log_msg_prefix, "SUCCESS -- device powered off.")
			return True
		self.log(self.log_msg_prefix, "ERROR -- command failed.")
		return False


	# def wait(self, **kwargs):     ## <-- Allowing instead the invocation of parent's wait() method
	# def reset(self, force=False): ## <-- Allowing instead the invocation of parent's reset() method
	# def close(self, force=False): ## <-- Allowing instead the invocation of parent's close() method
	# def firmware_version(self):   ## <-- Allowing instead the invocation of parent's firmware_version() method


	## Overriden method
	def get_num_devices(self):
		return 1


	## Overriden method
	def ping(self):
		return self._opcn2.ping()


	## Overriden method
	def sn(self):
		return self._opcn2.sn().strip()


	## Overriden method
	def read_info_string(self):
		return self._opcn2.read_info_string()


	## Overriden method
	def set_fan_power(self, power):
		return self._opcn2.set_fan_power(power)

	
	## Overriden method
	def toggle_fan(self, state):
		return self._opcn2.toggle_fan(state)


	## Overriden method
	def pm(self):
		""" 
		Returns a dict of the format {'PM1': x, 'PM10': y, 'PM2.5': z} 
		Particular matter density concentration units: num. of particles per cubic centimeter (#/cc).
		"""
		if self._prev_pm is not None and (time.time() - self._last_read_time) < 2:
			return self._prev_pm
			
		# self.on()    ## Ensure device is on before attempting a read operation
		pm = self._opcn2.pm()
		pm_err_cnt = 0
		while not any(pm.values()):
			if pm_err_cnt > 4:
				break
			pm = self._opcn2.pm()
			pm_err_cnt += 1
		for key in pm.keys():
			pm[key] = round(pm[key], FP_PRECISION)
		self._prev_pm = pm
		self._last_read_time = time.time()

		# self._pm_dict = pm
		self._pm_dict['PM1']   = round(pm.get('PM1'), FP_PRECISION)
		self._pm_dict['PM2.5'] = round(pm.get('PM2.5'), FP_PRECISION)
		self._pm_dict['PM10']  = round(pm.get('PM10'), FP_PRECISION)
		time.sleep(0.1)
		return self._pm_dict


	## Overriden method
	def histogram(self, number_concentration=True):
		# self.on()    ## Ensure device is on before attempting a read operation
		hist = self._opcn2.histogram(number_concentration=number_concentration)
		self._hist_dict = hist
		self._prev_pm = {   
						'PM1':round(hist['PM1'], FP_PRECISION), 
						'PM10':round(hist['PM10'], FP_PRECISION), 
						'PM2.5':round(hist['PM2.5'], FP_PRECISION)
						}
		self._pm_dict = self._prev_pm
		self._last_read_time = time.time()
		time.sleep(0.1)
		return self._hist_dict 


## ==================================================================
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

		assert enabled

		print(">>> New OPC_Pmod state:", end='  ')
		sys.stdout.flush()
		print('OFF' if opc.state == OFF else 'ON')

	print('='*60, end='\n\n')
	
	time.sleep(1)
	ping_test(opc)

	if RUN_FAN_POWER_TEST:
		fan_power_test(opc)

	if INFINITE_POLL:
		while True:
			try:
				timestamp = time.asctime(time.localtime())
				pm = opc.pm()
				print(f"({timestamp}) -- {pm}")
				print('='*60)
				time.sleep(SAMPLE_DELAY)
			except:
				print(f">>> [{timestamp}] {__file__} TERMINATED FROM MAIN LOOP")
				break
	else:
		for i in range(10):
			timestamp = time.asctime(time.localtime())
			pm = opc.pm()
			print(f"({timestamp}) -- {pm}")
			print('='*60)
			time.sleep(SAMPLE_DELAY)

	if not MOCK_MICROBLAZE:
		print(">>> Turning the OPC_Pmod off ...")
		enabled = opc.off()
		assert enabled
		print(">>> Final OPC_Pmod state:", end='  ')
		sys.stdout.flush()
		print('OFF' if opc.state == OFF else 'ON')
		
