###################################
######  Arduino SPI Example  ######
###################################
import time
from pynq import Overlay
from pynq.lib import MicroblazeLibrary

## Arduino Shield SPI Pin Definitions
ARDUINO_SCLK_PIN = 13
ARDUINO_MISO_PIN = 12
ARDUINO_MOSI_PIN = 11
ARDUINO_SS_PIN   = 10

## For SPI mode 1 on ARM-based controllers: Clock polarity = 0, Clock phase = 1  
## (source: https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Mode_numbers) 
SPI_CLOCK_PHASE    = 1
SPI_CLOCK_POLARITY = 0

## Obtain a reference to the Base Overlay (bitstream) loaded into the PL
overlay = Overlay('base.bit')

## Using the Arduino IO Processor for this example
iop = overlay.iop_arduino

## Instantiate the Python object that wraps the library functions defined in 'spi.h' for the IOP
lib = MicroblazeLibrary(iop, ['spi'])

## Open a SPI device object for the 'SPI1' controller (which uses IO pins 10-13)
spi_device = lib.spi_open(ARDUINO_SCLK_PIN, ARDUINO_MISO_PIN, ARDUINO_MOSI_PIN, ARDUINO_SS_PIN)

## ^ Alternatively, the 'SPI0' controller uses the dedicated 6-pin SPI header & can be opened as:
# spi_device = lib.spi_open_device(0)

## The SPI master must be configured with a specified clock phase & polarity, based on the 
##   slave device's SPI mode (this example uses SPI mode 1)
spi_device.configure(SPI_CLOCK_PHASE, SPI_CLOCK_POLARITY)

## The following sequence demonstrates transferring bytes to & from the SPI slave:
##   1. Send an iterable list of command byte(s) to initiate a sensor read, then wait 10 ms
##      NOTE: If just writing data, the 'read_data' argument must be an empty buffer (i.e., [0x00])
##            and cannot be None; the same applies for the 'write_data' arg when only reading data
write_data = [0x32]
spi_device.transfer(write_data, [0x00], len(write_data))
time.sleep(10e-3)

##   2. Read back some number of bytes from the slave; in this example we are expecting a 12-byte 
##      response & are receiving 1 byte at a time into an empty buffer 'read_data'
response = []
for i in range(12):
	read_data = [0x00]
	spi_device.transfer([0x00], read_data, 1)
	response.append(read_data[0])

## Close the SPI device handle once finished
spi_device.close()