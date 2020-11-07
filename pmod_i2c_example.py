################################
######  Pmod I2C Example  ######
################################
import time
from pynq import Overlay
from pynq.lib import MicroblazeLibrary

## Pmod I2C Pin Definitions
PMOD_SDA_PIN = 6    ## or 2
PMOD_SCL_PIN = 7    ## or 3

EXAMPLE_I2C_ADDRESS = 0x77         ## I2C address for the slave device
EXAMPLE_REGISTER_ADDRESS = 0x14    ## RAM (offset) address for a data register on the slave device

## Obtain a reference to the Base Overlay (bitstream) loaded into the PL
overlay = Overlay('base.bit')

## Using the PmodA IO Processor for this example
iop = overlay.iop_pmoda

## Instantiate the Python object that wraps the library functions defined in 'i2c.h' for the IOP
lib = MicroblazeLibrary(iop, ['i2c'])

## Open an I2C device object on the specified SDA and SCL pins
i2c_device = lib.i2c_open(PMOD_SDA_PIN, PMOD_SCL_PIN)

## Example for writing a 16-bit value to a register
##   NOTE: The exact I2C comms procedure / packet structure will likely be unique for each 
##         I2C sensor; these specifications should be covered in datasheets for the device
write_value = 0xABCD
buffer = bytearray(3)
buffer[0] = EXAMPLE_REGISTER_ADDRESS  ## Typically the MSB of the buffer will be a register offset for writes
buffer[1] = (write_value >> 8) & 0xFF
buffer[2] = write_value & 0xFF
i2c_device.write(EXAMPLE_I2C_ADDRESS, buffer, len(buffer))

time.sleep(10e-3)    ## A ~10 ms delay between read / write operations may be necessary

## Example for reading a 16-bit register value back from the device
num_bytes_to_read = 2
i2c_device.read(EXAMPLE_I2C_ADDRESS, buffer, num_bytes_to_read)
read_value = (buffer[0] << 8) | buffer[1]
print(read_value)

## Close the I2C device handle once finished
i2c_device.close()