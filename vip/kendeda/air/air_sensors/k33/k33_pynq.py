import os
import sys
import signal
import time
import serial 
import termios
from datetime import datetime as dt

# from pynq import Overlay
# from pynq import PL
# from pynq.lib import MicroblazeLibrary

##=============================================================================#
##  Global Configuration Options (to be changed by developers)

# IOP_NAME = "Arduino"  # "PmodA"  # "PmodB"
# # ARDUINO_SDA = 20  ## <-- is it?? according to diagram, SDA = 18
# ARDUINO_SDA = 18
# # ARDUINO_SCL = 21  ## <-- is it?? according to diagram, SCL = 19
# ARDUINO_SCL = 19

# ## Pmod IIC pin options: 2, 3, 6, and 7 (all have internal pull-up resistors for enabling I2C communications)
# PMOD_SDA = 6  ## or 2
# PMOD_SCL = 7  ## or 3

ARDUINO_RXD = 0
ARDUINO_TXD = 1

CONTINUOUS_MEASUREMENT_MODE = False 	## True if the AnIn1 jumper is set for continuous measurement mode, else WakeUp pulses will need to be sent

STARTUP_DELAY = 5   ## Seconds (adjustable by writing new duration (1 byte) to EEPROM address 0x23C)
MEASUREMENT_PERIOD = 20 	## Time (in seconds) between start of two measurement cycles (adjust in EEPROM address 0xB0 (3 bytes))

##=============================================================================#
##  Global Constant Values (leave these alone plz)

K33_ADDR = 0x68				## I2C address (default; 7-bits)
WRITE_BIT = 0
READ_BIT  = 1

## Write: Send byte 0xD0 for default address 0x68, 
##        or byte 0xFE for "any sensor" address 0x7F
WRITE_ADDR = (K33_ADDR << 1) + WRITE_BIT

## Read: Send byte 0xD1 for default address 0x68, 
##       or byte 0xFF for "any sensor" address 0x7F
READ_ADDR  = (K33_ADDR << 1) + READ_BIT

## Write RAM Command byte's high nibble (must add the number 
## of bytes to be written) --> e.g., WRITE_3_BYTES = 0x13
WRITE_CMD = 0x10

## Read RAM Command byte's high nibble (must add the number 
## of bytes to be read) --> e.g., READ_2_BYTES = 0x22
READ_CMD = 0x20

EEPROM_WRITE_CMD = 0x30
EEPROM_READ_CMD = 0x40

I2C_DELAY = 0.02  # (20 / 1000.0) 	## 20ms in seconds (for time.time.sleep())
DEFAULT_STARTUP_DELAY = 5           ## Seconds
DEFAULT_MEASUREMENT_PERIOD = 16     ## Seconds

SCR_REG = 0x60 		## The SCR (special control register)
STATUS_REG = 0x1D
CO2_REG  = 0x0008	## Address in RAM, For reading CO2 concentration (ppm)
TEMP_REG = 0x0012 	## Address in RAM, For reading space temperature (C)
RH_REG   = 0x0014	## Address in RAM, For reading relative humidity (%)

SINGLE_MEASURE_START_CMD = 0x35
CONTIN_MEASURE_START_CMD = 0x30
CONTIN_MEASURE_STOP_CMD  = 0x31

## Length of a Write Response, and of all bytes of a Read Response other than returned Read Data bytes
RESPONSE_METADATA_BYTES = 2		
## ^ excluding the 7-bit I2C address + Read/Write bit (MSB in the diagrams below).
## This includes the checksum (LSB) and command status byte (MSB), ignoring size of any data payload.

MAX_CO2_PPM = ((2 ** 15) - 1)

##=============================================================================#

class _K33_Meta_Base:
	""" Common for all other K33-related subclasses. """
	def __init__(self, overlay=None):
		if overlay is None:
			overlay = Overlay('base.bit', download=(PL.bitfile_name.split('/')[-1] != 'base.bit'))
		self.base = overlay
		self.bus = None 
		self.initialized = False 

##______________________________________________________________________________


class _K33_I2C_Base(_K33_Meta_Base):
	""" Generic base class for communicating with a K33 sensor via I2C. """
	def __init__(self, overlay=None):
		super().__init__(overlay)
		# self.iop = None 
		self._lib = None


	@property
	def lib(self):
		if self._lib is None:
			self._lib = MicroblazeLibrary(self.iop, ['i2c'])
		return self._lib

##______________________________________________________________________________


class K33_I2C_Arduino(_K33_I2C_Base):
	""" 
	Class for a K33 sensor connected to GPIO pins 19 (SDA) and 18 (SCL) of the
	PYNQ's Arduino header to be read via I2C.
	"""

	def __init__(self, overlay=None, iop=None):
		super().__init__(overlay)
		if iop is None:
			iop = self.base.iop_arduino
		self.iop = iop 
		self.bus = self.lib.i2c_open_device(0)
		self.initialized = True


##______________________________________________________________________________


class K33_I2C_Pmod(_K33_I2C_Base):
	""" 
	Class for a K33 sensor connected to either the PmodA or PmodB port of 
	the PYNQ to be read via I2C. The SDA and SCL pin options for Pmod are 
	pins 2, 3, 6, and 7. These are internally connected to pull-up resistors
	necessary for I2C communications.
	The index of the Pmod pins:
	upper row, from left to right: {vdd,gnd,3,2,1,0}.
	lower row, from left to right: {vdd,gnd,7,6,5,4}.
	"""

	PMOD_I2C_PINS = (2, 3, 6, 7)

	def __init__(self, pmod_ab='A', sda_pin=PMOD_SDA, scl_pin=PMOD_SCL overlay=None, iop=None):
		super().__init__(overlay)
		if iop is None:
			if pmod_ab.upper() == 'A':
				iop = self.base.iop_pmoda
			elif pmod_ab.upper() == 'B':
				iop = self.base.iop_pmodb
			else:
				raise ValueError(f"Invalid Pmod specification: Pmod{pmod_ab} does not exist -- `pmod_ab` value must be 'A' or 'B'")
		self.iop = iop 

		if sda_pin not in K33_I2C_Pmod.PMOD_I2C_PINS:
			raise ValueError(f"Invalid SDA pin for Pmod{pmod_ab}: I2C supported on pins {K33_I2C_Pmod.PMOD_I2C_PINS}")
		if scl_pin not in K33_I2C_Pmod.PMOD_I2C_PINS:
			raise ValueError(f"Invalid SCL pin for Pmod{pmod_ab}: I2C supported on pins {K33_I2C_Pmod.PMOD_I2C_PINS}")
		if sda_pin == scl_pin:
			raise ValueError("Cannot assign SDA and SCL to the same Pmod pin")

		self.sda = sda_pin 
		self.scl = scl_pin
		self.bus = self.lib.i2c_open(self.sda, self.scl)
		self.initialized = True
		
##______________________________________________________________________________


class _K33_UART_Base(_K33_Meta_Base):
	"""! Generic base class for communicating with a K33 sensor serially via UART.

		Seven byte request for reading CO2 ppm from the K33:		
			[0]   = Address byte (0xFE)
			[1]   = Command byte (0x44 for RAM Read, else 0x46 for EEPROM Read)
			[2:3] = Address (0x0008 is the RAM address for the CO2 Register)
			[4]   = Number of bytes to read (2 bytes for 0x08 & 0x09)
			[5:6] = Checksum / CRC (0x259F, sent with the low byte first)
	"""
	READ_RH_CMD   = [0xFE, 0x44, 0x00, 0x14, 0x02, 0x97, 0xE5] 	## Pulls relative humidity from K33
	READ_CO2_CMD  = [0xFE, 0x44, 0x00, 0x08, 0x02, 0x9F, 0x25]
	READ_TEMP_CMD = [0xFE, 0x44, 0x00, 0x12, 0x02, 0x94, 0x45]

	def __init__(self, _serial):
		"""! K33_UART base class initializer.
		
		@param _serial  The serial device; Can either be of type `serial.Serial` (for USB connection) or a native pynq `uart` object created via `MicroblazeLibrary`

		"""
		# super().__init__(overlay)
		self.ser = _serial

	@property
	def using_usb(self):
		"""! Only if the serial device is an instance of `serial.Serial` (indicative of using USB rather than a PYNQ IOP) will it have the attribute `flushInput`.

		@return  True if instance of K33_UART_USB, else False if K33_UART_Arduino
		"""
		return hasattr(self.ser, 'flushInput')

	... TODO ... (port methods from k33_uart_pynq)

##_____________________________________________________________________________

class K33_UART_Arduino(_K33_UART_Base):
	"""
	Class for a K33 sensor connected to GPIO pins 0 (RXD) and 1 (TXD) of the 
	PYNQ's Arduino header to be read via UART.
	"""

	def __init__(self, uart):
		super().__init__(uart)

##______________________________________________________________________________


class K33_UART_USB(_K33_UART_Base):
	"""
	Wrapper class for easy standardized setup/config of a CO2Meter K33-ELG sensor. 
	For driving the K33-ELG using the provided USB cable, set the `port` parameter 
	to something like `/dev/ttyUSB0`. All communications use the UART protocol.

	NOTE: The AnIn1 Jumper on the K33 board should be set
	"""

	def __init__(self, usb=None):
		if usb is None:
			import serial 
			port='/dev/USB0'
			usb = serial.Serial(port, baudrate=9600, timeout=0.5)
		super().__init__(usb)


##______________________________________________________________________________

