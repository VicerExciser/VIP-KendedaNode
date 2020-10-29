""" 
This module is a basic demonstration of how serial communication (UART) can be 
achieved for a device connected to GPIO pins 0 (RXD) & 1 (TXD) of the PYNQ's 
Arduino header.  

PYNQ UART API (https://github.com/Xilinx/PYNQ/blob/image_v2.5/boards/sw_repo/pynqmb/src/uart.h):
	typedef int uart;

	uart uart_open_device(unsigned int device);
	uart uart_open(unsigned int tx, unsigned int rx);
	void uart_close(uart dev_id);

	void uart_read(uart dev_id, unsigned char* read_data, unsigned int length);
	void uart_write(uart dev_id, unsigned char* write_data, unsigned int length);
"""
import time
from pynq import Overlay, PL
from pynq.lib import MicroblazeLibrary

##  ========================================================================

def get_base_overlay():
	"""
	Returns an instance of an object to represent the default PYNQ base overlay 
	for the purpose of exposing Microblaze / IOP (input-output processor) 
	controllers to be passed as the first positional argument when instantiating 
	a MicroblazeLibrary object.

	This function makes use of the `download` parameter for the Overlay class 
	constructor to prevent re-downloading the same 'base.bit' bitstream into
	the board's programmable logic (PL) if the active bitstream design (overlay) 
	is already 'base.bit'.

	Overlay source: https://github.com/Xilinx/PYNQ/blob/master/pynq/overlay.py
	"""
	need_to_download_overlay = PL.bitfile_name.split('/')[-1] != 'base.bit'
	base = Overlay('base.bit', download=need_to_download_overlay)
	return base

##  ========================================================================

class Arduino_UART:

	RXD = 0   ## UART RX pin is digital IO0 on the PYNQ's Arduino header
	TXD = 1   ## UART TX pin is digital IO1 on the PYNQ's Arduino header

	def __init__(self, overlay=None):
		if overlay is None:
			overlay = get_base_overlay()

		## The Overlay object should have an attribute `iop_arduino` to represent 
		## the Arduino PYNQ Microblaze that controls the board's Arduino interface.
		## More info here: https://pynq.readthedocs.io/en/v2.6.1/pynq_libraries/arduino.html
		if not hasattr(overlay, 'iop_arduino'):
			raise ValueError('Overlay "{}" is missing an Arduino IOP.'.format(overlay.bitfile_name.split('/')[-1]))
		iop = overlay.iop_arduino 

		## Instantiate the Python object that wraps the library functions defined in 'uart.h' 
		lib = MicroblazeLibrary(iop, ['uart'])
		
		## Open a UART device object capable of serial communications with a connected sensor.
		## This `uart` object has all the same methods as the above `lib` object, except the 
		## API calls (invoking functions from 'uart.h') are no longer prefixed by "uart_"
		self.uart = lib.uart_open(Arduino_UART.TXD, Arduino_UART.RXD)
		""" ^ 
		`uart` object methods (wrappers for the functions implemented in 'uart.c'):
			open(self, tx_pin, rx_pin)
			open_device(self, device_num=0)
			close(self)
			read(self, [read_data], length)
			write(self, [write_data], length)
		"""
		time.sleep(0.5)

	##   ___________________________________________________________________

	def close(self):
		self.uart.close()

	##   ___________________________________________________________________

	def reset(self):
		self.close()
		time.sleep(0.5)
		self.uart.open(Arduino_UART.TXD, Arduino_UART.RXD)
		time.sleep(0.5)

	##   ___________________________________________________________________

	def write(self, payload):
		## `payload` should be an iterable list of byte values
		if not hasattr(payload, '__iter__'):
			raise ValueError('payload argument must be an array of bytes.')

		## NOTE: Your device may require a call to `self.reset()` prior to each write or read
		# self.reset()   ## <-- Uncomment if experiencing bus IO errors, device is unresponsive, etc.

		self.uart.write(payload, len(payload))

	##   ___________________________________________________________________

	def read(self, num_bytes):
		response = [0x00] * num_bytes   ## Create empty buffer to be populated by the `uart_read` operation

		## NOTE: Your device may require a call to `self.reset()` prior to each write or read 
		# self.reset()   ## <-- Uncomment if experiencing bus IO errors, device is unresponsive, etc.
		
		self.uart.read(response, num_bytes)   ## Request {num_bytes} bytes from the device
		return response 

##  ========================================================================

def arduino_uart_test():
	## Basic example where I will issue a command to read temperature from a connect sensor
	arduino_uart = Arduino_UART()
	read_temp_command = [0xFE, 0x44, 0x00, 0x12, 0x02, 0x94, 0x45]

	arduino_uart.write(read_temp_command)
	time.sleep(0.125)

	received_bytes = arduino_uart.read(7)   ## Request 7 bytes from which the 2-byte temp value can be extracted
	temperature = ((received_bytes[3] << 8) + received_bytes[4]) * 0.01
	print('Temperature:  {:.2f} C'.format(temperature))

##  ========================================================================

if __name__ == '__main__':
	arduino_uart_test()   ## Just to demonstrate usage
