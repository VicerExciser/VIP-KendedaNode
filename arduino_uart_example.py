####################################
######  Arduino UART Example  ######
####################################
import time
from pynq import Overlay
from pynq.lib import MicroblazeLibrary

## Arduino Shield UART Pin Definitions
ARDUINO_RXD = 0
ARDUINO_TXD = 1

## Obtain a reference to the Base Overlay (bitstream) loaded into the PL
overlay = Overlay('base.bit')

## Using the Arduino IO Processor for this example
iop = overlay.iop_arduino

## Instantiate the Python object that wraps the library functions defined in 'uart.h' for the IOP
lib = MicroblazeLibrary(iop, ['uart'])

## Open a UART device object
uart_device = lib.uart_open(ARDUINO_TXD, ARDUINO_RXD)

## ^ Alternatively, since there is only 1 UART controller enabled ('UART0'), this works too:
# uart_device = lib.uart_open_device(0)

## The following sequence demonstrates sending a request to read data from the device:
##   1. Write an iterable list/bytearray of command bytes to initiate a read
read_command = [0xDE, 0xAD, 0xBE, 0xEF]
uart_device.write(read_command, len(read_command))

time.sleep(0.125)    ## A brief delay may be necessary

##   2. Request a 4-byte response from which the desired data may be extracted
num_bytes = 4
response = [0x00] * num_bytes
uart_device.read(response, num_bytes)

##   3. The wrapped call to `uart_read()` will populate the empty 'response' buffer with data
data_value = (response[1] << 8) | response[2]
print(data_value)

## Close the UART device handle once finished
uart_device.close()