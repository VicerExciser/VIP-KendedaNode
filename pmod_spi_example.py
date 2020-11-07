################################
######  Pmod SPI Example  ######
################################
import time
from pynq import Overlay
from pynq.lib import MicroblazeLibrary

## Pmod SPI Pin Definitions
PMOD_SCLK_PIN = 1
PMOD_MISO_PIN = 0
PMOD_MOSI_PIN = 4
PMOD_SS_PIN   = 5

## For SPI mode 0 on ARM-based controllers: Clock polarity = 0, Clock phase = 0
## Be sure to check the datasheet for your specific device to find which SPI mode to use
## (source: https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Mode_numbers) 
SPI_CLOCK_PHASE    = 0
SPI_CLOCK_POLARITY = 0

## Obtain a reference to the Base Overlay (bitstream) loaded into the PL
overlay = Overlay('base.bit')

## Using the PmodB IO Processor for this example
iop = overlay.iop_pmodb 

## Instantiate the Python object that wraps the library functions defined in 'spi.h' for the IOP
lib = MicroblazeLibrary(iop, ['spi'])

## Open a SPI device object capable of data transfer operations 
spi_device = lib.spi_open(PMOD_SCLK_PIN, PMOD_MISO_PIN, PMOD_MOSI_PIN, PMOD_SS_PIN)

## The SPI master must be configured with a specified clock phase & polarity, based on the 
##   slave device's SPI mode (this example uses SPI mode 0)
spi_device.configure(SPI_CLOCK_PHASE, SPI_CLOCK_POLARITY)

## The following sequence demonstrates transferring bytes to & from the SPI slave:
##   1. Send an iterable list of command byte(s) to initiate a sensor read, then wait 10 ms
##      NOTE: If just writing data, the 'read_data' argument must be an empty buffer (i.e., [0x00])
##            and cannot be None; the same applies for the 'write_data' arg when only reading data
write_data = [0x42]
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