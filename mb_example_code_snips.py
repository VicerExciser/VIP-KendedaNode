import time
from pynq import Overlay, PL
from pynq.lib import MicroblazeLibrary

base = Overlay('base.bit', download=(PL.bitfile_name.split('/')[-1] != 'base.bit'))
iop_dict = {
	'ARDUINO': base.iop_arduino,
	'PMODA': base.iop_pmoda,
	'PMODB': base.iop_pmodb
}

""" Re: Pmod Peripherals  (https://pynq.readthedocs.io/en/v2.5/pynq_libraries/pmod.html)

All pins operate at 3.3V. Due to different pull-up/pull-down I/O requirements for different peripherals (e.g. IIC requires pull-up, and SPI requires pull-down) the Pmod data pins have different IO standards.

Pins 0,1 and 4,5 are connected to pins with pull-down resistors. This can support the SPI interface, and most peripherals. Pins 2,3 and 6,7 are connected to pins with pull-up resistors. This can support the IIC interface.

Pmods already take this pull up/down convention into account in their pin layout, so no special attention is required when using Pmods.

"""


##########################
####  I2C
##########################
""" I2C API (from https://github.com/Xilinx/PYNQ/blob/master/boards/sw_repo/pynqmb/src/i2c.h):

	typedef int i2c;

	i2c i2c_open_device(unsigned int device);
	i2c i2c_open(unsigned int sda, unsigned int scl);

	void i2c_read(i2c dev_id, unsigned int slave_address, unsigned char* buffer, unsigned int length);
	void i2c_write(i2c dev_id, unsigned int slave_address, unsigned char* buffer, unsigned int length);
	void i2c_close(i2c dev_id);



	XIIC_STOP bit automatically added under the hood to the end of each i2c_read/_write operation.

	If Repeated Start bit is not set (grep for XIIC_CR_REPEATED_START) then the Start bit is 
	sent automatically by setting MSMS bit before sending the device address on the bus. 

	For a low-level look at i2c_read, see:
	- https://github.com/Xilinx/PYNQ/blob/master/boards/sw_repo/pynqmb/src/i2c.c#L87
	- https://github.com/Xilinx/embeddedsw/blob/324e7b58ecc9ea06a929fb545d73565cafb9989a/XilinxProcessorIPLib/drivers/iic/src/xiic_l.c#L142

"""
iop = iop_dict['ARDUINO']
lib = MicroblazeLibrary(iop, ['i2c'])
ARDUINO_SDA = 20
ARDUINO_SCL = 21
# arduino_i2c = lib.i2c_open(ARDUINO_SDA, ARDUINO_SCL)
arduino_i2c = lib.i2c_open_device(0)
"""
	^ Methods available to the `arduino_i2c` object:

	read()
	write(address, write_buffer, length)
	close()

	get_num_devices()
	open_device()
"""

"""
- The 'device' object returned by i2c_open() or i2c_open_device(0) is of type pynq.lib.pynqmicroblaze.rpc 
	(https://pynq.readthedocs.io/en/v2.5.1/pynq_package/pynq.lib/pynq.lib.pynqmicroblaze.html#pynq.lib.pynqmicroblaze.rpc.MicroblazeRPC)
- 
"""

## Pmod IIC pin options: 2, 3, 6, and 7 (all have internal pull-up resistors for enabling I2C communications)
PMOD_SDA = 6  ## or 2
PMOD_SCL = 7  ## or 3
pmoda_i2c = MicroblazeLibrary(base.iop_pmoda, ['i2c']).i2c_open(PMOD_SDA, PMOD_SCL) 

pmodb_i2c = MicroblazeLibrary(base.iop_pmodb, ['i2c']).i2c_open(PMOD_SDA, PMOD_SCL) 





##########################
####  SPI
##########################
"""
There are 2 SPI controllers for the Arduino IOP subsystem: one connected to the dedicated header pin, the other connected to pin 10-13.

	- SPI0 controller is for the dedidated SPI header pins, and can be opened as 
			`spi_bus = lib.spi_open_device(0)`

	- SPI1 controller is for the digital IO pins 10-13 of the Arduino header, and can be opened as 
			`spi_bus = lib.spi_open(13, 12, 11, 10)


For SPI mode 1 on ARM-based controllers: Clock polarity = 0, Clock phase = 1  (source: https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Mode_numbers) 


"""


##########################
####  UART
##########################
"""
1 UART controller (UART0)
"""
UART_RXD = 0
UART_TXD = 1
uart_bus = lib.uart_open(UART_TXD, UART_RXD)
## _OR_
uart_bus = lib.uart_open_device(0)

""" UART API (https://github.com/Xilinx/PYNQ/blob/image_v2.5/boards/sw_repo/pynqmb/src/uart.h):
typedef int uart;
uart uart_open_device(unsigned int device);
uart uart_open(unsigned int tx, unsigned int rx);
void uart_read(uart dev_id, unsigned char* read_data, unsigned int length);
void uart_write(uart dev_id, unsigned char* write_data, unsigned int length);
void uart_close(uart dev_id);
unsigned int uart_get_num_devices(void);

`uart_bus` object methods (wrappers for the above):
	open(self, tx_pin, rx_pin)
	open_device(self, device_num=0)
	close(self)
	read(self, read_data, length)
	write(self, write_data, length)
"""

##########################
####  GPIO
##########################
"""
For GPIO, I really recommend using the Arduino_IO and Pmod_IO classes, but for special cases where manual access to gpio is
needed:
"""
lib = MicroblazeLibrary(base.iop_arduino, ['i2c', 'gpio'])
gpio = lib.gpio_open_device(0)
LOW = 0
HIGH = 1
channel = ARDUINO_SDA
gpio.configure(LOW, HIGH, channel)
IN = 1
OUT = 0
gpio.set_direction(OUT)
val = gpio.read()
gpio.write(val)
gpio.close()
