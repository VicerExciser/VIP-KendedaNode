# The MIT License (MIT)
#
# Copyright (c) 2018 Carter Nelson for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`ads1x15`
====================================================

PYNQ base class driver for ADS1015/1115 ADCs.
Adapted from the CircuitPython base class driver for ADS1015/1115 ADCs.

* Author(s): Carter Nelson, Austin Condict
"""

import time
# from adafruit_bus_device.i2c_device import I2CDevice
# from pynq import Overlay, PL
# from pynq.lib import MicroblazeLibrary

_ADS1X15_DEFAULT_ADDRESS = (0x48)
_ADS1X15_POINTER_CONVERSION = (0x00)
_ADS1X15_POINTER_CONFIG = (0x01)
_ADS1X15_CONFIG_OS_SINGLE = (0x8000)
_ADS1X15_CONFIG_MUX_OFFSET = (12)
_ADS1X15_CONFIG_COMP_QUE_DISABLE = (0x0003)
_ADS1X15_CONFIG_GAIN = {
	2 / 3: 0x0000,
	1: 0x0200,
	2: 0x0400,
	4: 0x0600,
	8: 0x0800,
	16: 0x0A00,
}


class Mode:
	"""An enum-like class representing possible ADC operating modes."""

	# See datasheet "Operating Modes" section
	# values here are masks for setting MODE bit in Config Register
	# pylint: disable=too-few-public-methods
	CONTINUOUS = 0x0000
	SINGLE = 0x0100


class ADS1x15:
	"""Base functionality for ADS1x15 analog to digital converters."""

	def __init__(
		self,
		i2c,
		gain=1,
		data_rate=None,
		mode=Mode.SINGLE,
		address=_ADS1X15_DEFAULT_ADDRESS,
	):
		# pylint: disable=too-many-arguments
		self._last_pin_read = None
		self.buf = bytearray(3)
		self._data_rate = self._gain = self._mode = None
		self.gain = gain
		self.data_rate = self._data_rate_default() if data_rate is None else data_rate
		self.mode = mode
		self.address = address

		#### (Original code from https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15/blob/master/adafruit_ads1x15/ads1x15.py#L82):
		# self.i2c_device = I2CDevice(i2c, address)
		####

		#### (My attempt at replacing the typically expected `busio.I2C` object with a PYNQ I2C object (created thru MicroblazeLibrary elsewhere)):
		## Ensure the passed i2c device was created by pynq.lib.pynqmicroblaze.rpc
		assert (i2c is not None) and (i2c.__class__.__name__ == 'i2c') and (i2c.val == 0)
		self.i2c_device = i2c
		####

	@property
	def data_rate(self):
		"""The data rate for ADC conversion in samples per second."""
		return self._data_rate

	@data_rate.setter
	def data_rate(self, rate):
		possible_rates = self.rates
		if rate not in possible_rates:
			raise ValueError("Data rate must be one of: {}".format(possible_rates))
		self._data_rate = rate

	@property
	def rates(self):
		"""Possible data rate settings."""
		raise NotImplementedError("Subclass must implement rates property.")

	@property
	def rate_config(self):
		"""Rate configuration masks."""
		raise NotImplementedError("Subclass must implement rate_config property.")

	@property
	def gain(self):
		"""The ADC gain."""
		return self._gain

	@gain.setter
	def gain(self, gain):
		possible_gains = self.gains
		if gain not in possible_gains:
			raise ValueError("Gain must be one of: {}".format(possible_gains))
		self._gain = gain

	@property
	def gains(self):
		"""Possible gain settings."""
		g = list(_ADS1X15_CONFIG_GAIN.keys())
		g.sort()
		return g

	@property
	def mode(self):
		"""The ADC conversion mode."""
		return self._mode

	@mode.setter
	def mode(self, mode):
		if mode not in (Mode.CONTINUOUS, Mode.SINGLE):
			raise ValueError("Unsupported mode.")
		self._mode = mode

	def read(self, pin, is_differential=False):
		"""I2C Interface for ADS1x15-based ADCs reads.

		params:
			:param pin: individual or differential pin.
			:param bool is_differential: single-ended or differential read.
		"""
		pin = pin if is_differential else pin + 0x04
		return self._read(pin)

	def _data_rate_default(self):
		"""Retrieve the default data rate for this ADC (in samples per second).
		Should be implemented by subclasses.
		"""
		raise NotImplementedError("Subclasses must implement _data_rate_default!")

	def _conversion_value(self, raw_adc):
		"""Subclasses should override this function that takes the 16 raw ADC
		values of a conversion result and returns a signed integer value.
		"""
		raise NotImplementedError("Subclass must implement _conversion_value function!")

	def _read(self, pin):
		"""Perform an ADC read. Returns the signed integer result of the read."""
		if self.mode == Mode.CONTINUOUS and self._last_pin_read == pin:
			return self._conversion_value(self.get_last_result(True))
		self._last_pin_read = pin
		if self.mode == Mode.SINGLE:
			config = _ADS1X15_CONFIG_OS_SINGLE
		else:
			config = 0
		config |= (pin & 0x07) << _ADS1X15_CONFIG_MUX_OFFSET
		config |= _ADS1X15_CONFIG_GAIN[self.gain]
		config |= self.mode
		config |= self.rate_config[self.data_rate]
		config |= _ADS1X15_CONFIG_COMP_QUE_DISABLE
		self._write_register(_ADS1X15_POINTER_CONFIG, config)

		if self.mode == Mode.SINGLE:
			# poll conversion complete status bit
			while not self._conversion_complete():
				pass
		else:
			# just sleep (can't poll in continuous)
			time.sleep(2 / self.data_rate)

		return self._conversion_value(self.get_last_result(False))

	def _conversion_complete(self):
		"""Return status of ADC conversion."""
		# OS is bit 15
		# OS = 0: Device is currently performing a conversion
		# OS = 1: Device is not currently performing a conversion
		return self._read_register(_ADS1X15_POINTER_CONFIG) & 0x8000

	def get_last_result(self, fast=False):
		"""Read the last conversion result when in continuous conversion mode.
		Will return a signed integer value. If fast is True, the register
		pointer is not updated as part of the read. This reduces I2C traffic
		and increases possible read rate.
		"""
		return self._read_register(_ADS1X15_POINTER_CONVERSION, fast)



	def _write_register(self, reg, value):
		"""Write 16 bit value to register.
		
		For replacing the original invocation of I2C_Device.write(), see its implementation in the sources:
		https://circuitpython.readthedocs.io/projects/busdevice/en/latest/_modules/adafruit_bus_device/i2c_device.html
		https://circuitpython.readthedocs.io/en/latest/shared-bindings/busio/#busio.I2C.writeto 
		"""
		self.buf[0] = reg
		self.buf[1] = (value >> 8) & 0xFF
		self.buf[2] = value & 0xFF
		
		#### (Original code from https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15/blob/master/adafruit_ads1x15/ads1x15.py#L204):
		# with self.i2c_device as i2c:
		#     i2c.write(self.buf)
		####

		#### (My attempt at replacing the above `write` operation to use PYNQ's I2C API):
		num_bytes = 2
		self.i2c_device.write(self.address, self.buf, num_bytes)
		####
		


	def _read_register(self, reg, fast=False):
		"""Read 16 bit register value. If fast is True, the pointer register
		is not updated.

		For replacing the original invocations of I2C_Device.readinto() and 
		I2C_Device.write_then_readinto(), see their implementations in the sources:
		https://circuitpython.readthedocs.io/projects/busdevice/en/latest/_modules/adafruit_bus_device/i2c_device.html
		https://circuitpython.readthedocs.io/en/latest/shared-bindings/busio/#busio.I2C.writeto_then_readfrom
		 https://github.com/adafruit/Adafruit_Blinka/blob/master/src/busio.py#L99 
		"""
		#### (Original code from https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15/blob/master/adafruit_ads1x15/ads1x15.py#L211):
		# with self.i2c_device as i2c:
		#     if fast:
		#         i2c.readinto(self.buf, end=2)
		#     else:
		#         i2c.write_then_readinto(bytearray([reg]), self.buf, in_end=2)
		####
		
		#### (My attempt at replacing the above `readinto` & `write_then_readinto` operations to use PYNQ's I2C API):
		num_bytes = 2
		if fast:
			self.i2c_device.read(self.address, self.buf, num_bytes)
		else:
			out_buffer = bytearray([reg])
			self.i2c_device.write(self.address, out_buffer, len(out_buffer))
			self.i2c_device.read(self.address, self.buf, num_bytes)
		####

		return self.buf[0] << 8 | self.buf[1]
