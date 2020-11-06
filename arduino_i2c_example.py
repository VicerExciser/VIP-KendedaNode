###################################
######  Arduino I2C Example  ######
###################################
import time
from pynq import Overlay
from pynq.lib import MicroblazeLibrary

## Arduino Shield I2C Pin Definitions
ARDUINO_SDA = 18
ARDUINO_SCL = 19

EXAMPLE_I2C_ADDRESS = 0x68         ## I2C address for the slave device
EXAMPLE_REGISTER_ADDRESS = 0x08    ## RAM address for a data register on the slave device

## Obtain a reference to the Base Overlay (bitstream) loaded into the PL
overlay = Overlay('base.bit')

## Using the Arduino IO Processor for this example
iop = overlay.iop_arduino

## Instantiate the Python object that wraps the library functions defined in 'i2c.h' for the IOP
lib = MicroblazeLibrary(iop, ['i2c'])

## Open an I2C device object for the 'I2C0' controller
i2c_device = lib.i2c_open_device(0)

## ^ The above assumes the header pins labeled SDA & SCL are being used; however, the following 
##   alternative instantiation does not seem to work for the Arduino IOP for some reason:
# i2c_device = lib.i2c_open(ARDUINO_SDA, ARDUINO_SCL)

## The following sequence demonstrates sending a request to read data from the slave device:
##   1. Send a packet of bytes issuing a command to read 2 bytes from a particular data register
##      NOTE: The exact I2C comms procedure / packet structure will likely be unique for each 
##            I2C sensor; these specifications should be covered in datasheets for the device
read_command = 0x20
num_bytes_to_read = 2
request = [read_command | num_bytes_to_read, 0x00, EXAMPLE_REGISTER_ADDRESS]
request.append(sum(request) & 0xFF)    ## Appending a checksum byte to the end of packet
i2c_device.write(EXAMPLE_I2C_ADDRESS, request, len(request))

##   2. Wait ~10 ms, then read the response on the I2C bus; in this example, because we requested 
##      2 bytes from the sensor (specified by the byte 0x22 that was sent), we must read in a 
##      4-byte response which includes the payload, checksum, & a command status byte
time.sleep(10e-3)
response = [0x00] * 4    ## 4-byte response buffer
i2c_device.read(EXAMPLE_I2C_ADDRESS, response, len(response))

##   3. The 'response' buffer should contain our requested data bytes, verifiable by the checksum
data_value = (response[1] << 8) | response[2]
checksum = sum(response[:-1])    ## Checksum == sum of all bytes other than the checksum byte
received_checksum = response[-1]
if checksum != received_checksum:
	print('Checksum error occurred')
else:
	print(data_value)

## Close the I2C device handle once finished
i2c_device.close()