import time
import struct
from pynq.overlays.base import BaseOverlay
from pynq.lib.arduino import Arduino_Analog, ARDUINO_GROVE_A1


base = BaseOverlay('base.bit')
operating_voltage = 5.0  #3.3
xadc_max_raw = float((2**16) - 1)
pin = 0
pin_group = ARDUINO_GROVE_A1
assert pin in pin_group
pin_index = pin % len(pin_group)
analog_input = Arduino_Analog(base.ARDUINO, pin_group)


def _reg2float(reg):
	"""Converts 32-bit register value to floats in Python.

	Parameters
	----------
	reg: int
	    A 32-bit register value read from the mailbox.

	Returns
	-------
	float
	    A float number translated from the register value.

	"""
	s = struct.pack('>l', reg)
	return struct.unpack('>f', s)[0]


def raw_to_volt(raw):
	v = raw * (operating_voltage / xadc_max_raw)
	return round(v, 4)


while True:
	try:
		# voltage = analog_input.read()[pin_index] 	## Voltage will be in range [0.0, 3.3]
		raw = analog_input.read_raw()[pin_index] 	## Since the XADC is 16-bit, 
													## raw value will be in range [0, 65535]
		voltage = '{0:.4f}'.format(_reg2float(raw))
		alt_voltage = raw_to_volt(raw)
		print(f'\t{voltage} V\t(alt: {alt_voltage} V)\t[raw: {raw}]')
		time.sleep(0.5)
	except KeyboardInterrupt:
		break
