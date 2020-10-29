from pynq.lib.arduino import Arduino_Analog, ARDUINO_GROVE_A1, ARDUINO_GROVE_A2, ARDUINO_GROVE_A3, ARDUINO_GROVE_A4

##-----------------------------------------------------------------------------
""" References:
		https://github.gatech.edu/llerner3/vip/blob/master/kendeda/air/pynq_node/isb_pynq.py
		https://github.com/Xilinx/PYNQ/blob/image_v2.5/boards/Pynq-Z1/base/notebooks/arduino/arduino_analog.ipynb
		https://www.seeedstudio.com/blog/2020/01/19/tds-in-water-what-is-tds-and-how-do-you-measure-tds-in-water/
"""
##-----------------------------------------------------------------------------

class TDS:
	"""
	"""
	def __init__(self, pin, overlay):
		if not 0 <= pin <= 5:
			raise ValueError("TDS analog pin must be in range 0..5")
		
		self.pin = pin 	## Analog pin number for sensor (0 ... 5)
		self.pin_group = []

		## Find the grouping of analog pins (on the arduino-grove shield) that our pin belongs to
		## (see: https://github.com/Xilinx/PYNQ/blob/image_v2.5/pynq/lib/arduino/constants.py#L110)
		if self.pin in ARDUINO_GROVE_A1:
			self.pin_group = ARDUINO_GROVE_A1
		elif self.pin in ARDUINO_GROVE_A2:
			self.pin_group = ARDUINO_GROVE_A2
		elif self.pin in ARDUINO_GROVE_A3:
			self.pin_group = ARDUINO_GROVE_A3
		elif self.pin in ARDUINO_GROVE_A4:
			self.pin_group = ARDUINO_GROVE_A4
		assert len(self.pin_group) > 0

		## Ensure the passed-in Overlay object has an IO processor connected to the Arduino interface
		if not hasattr(overlay, 'iop_arduino'):
			raise ValueError("Invalid Overlay object -- missing an Arduino IOP")

		mb_info = overlay.iop_arduino.mb_info   ## NOTE: base.ARDUINO == base.iop_arduino.mb_info

		self.analog_in = Arduino_Analog(mb_info, self.pin_group)
		self.pin_idx = self.pin % len(self.pin_group)


	def read_vtg(self):
		## (see: https://pynq.readthedocs.io/en/v2.5/_modules/pynq/lib/arduino/arduino_analog.html#Arduino_Analog.read)
		return self.analog_in.read()[self.pin_idx]


def main():
	from pynq import Overlay
	sensor = TDS(1, Overlay('base.bit'))   ## Instantiate TDS object using the base Overlay just as an example
	print(f"Voltage:  {sensor.read_vtg()} V")

if __name__ == "__main__":
	main()
