import time

try:
	from onewire.device import OneWireDevice
	import onewire.constants as const

except (ImportError, ModuleNotFoundError):
	import os, sys
	import_path = os.path.join(os.getcwd(), 'onewire')
	print(f"[{__file__}] Appending '{import_path}' to sys.path")
	sys.path.append(import_path)

	from onewire.device import OneWireDevice
	import onewire.constants as const


eeprom_commands = { 	
		'CONVT_TEMP' : 0x44,  ## Convert Temp
		'SCRATCH_WR' : 0x4E,  ## Write Scratchpad: write 3 bytes of data to device scratchpad
		'SCRATCH_RD' : 0xBE,  ## Read Scratchpad
		'SCRATCH_CPY': 0x48,  ## Copy Scratchpad
		'RECALL_ATV' : 0xB8,  ## Recall Alarm Trigger Values
		'POWER_RD'   : 0xB4,  ## Read Power Supply
}

DS18B20_FAMILY_CODE = 0x28
DS18S20_FAMILY_CODE = 0x10
RW_TIME = 0.010  			## EEPROM write time, default value
# TRANSMIT_BITS = 0x40  	## 64-bits to transmit over the bus
SCRATCH_RD_SIZE = 0x48  ## read in 72 bits from scratch reg


RESOLUTION_VALUES = (9, 10, 11, 12)
## Maximum conversion delay in seconds, from DS18B20 datasheet
# CONVERSION_DELAY_MAP = {9: 0.09375, 10: 0.1875, 11: 0.375, 12: 0.750}
DS18B20_TCONV_12BIT = 0.750 		## Temp conversion time for 12-bit resolution, default value
DS18S20_TCONV = DS18B20_TCONV_12BIT
CONVERSION_DELAY_MAP = {
		9 : DS18B20_TCONV_12BIT/8, 
		10: DS18B20_TCONV_12BIT/4, 
		11: DS18B20_TCONV_12BIT/2, 
		12: DS18B20_TCONV_12BIT,
}
CONVERSION_TIMEOUT = 2
TEMP_REFRESH_TIMEOUT = 5

###################################################################################################

def celsius_from_raw(temp_raw):
	return round(float((temp_raw & 0x0000FFFF) / 16.0), 3)

def celsius_from_fahr(temp_f):
	return round(((temp_f - 32.0) * (5.0 / 9.0)), 3)

def fahr_from_raw(temp_raw):
	return fahr_from_celsius(celsius_from_raw(temp_raw))

def fahr_from_celsius(temp_c):
	return round((((9.0 / 5.0) * temp_c) + 32.0), 3)

###################################################################################################

MIN_TEMP_TARG_C = 0.00
MIN_TEMP_TARG_F = fahr_from_celsius(MIN_TEMP_TARG_C)  #32.00
MAX_TEMP_TARG_C = 105.00
MAX_TEMP_TARG_F = fahr_from_celsius(MAX_TEMP_TARG_C)  #221.00 

DEG = '°'
DEG_C = f'{DEG}C'
DEG_F = f'{DEG}F'
PLUSMINUS = '±'

###################################################################################################

class DS18X20:

	def __init__(self, bus, address, resolution=12, target=29.999, flux=1.5):
		# assert(isinstance(bus, onewire.bus.OneWireBus) and isinstance(address, onewire.bus.OneWireAddress))
		
		#if not (address.family_code == DS18B20_FAMILY_CODE or address.family_code == DS18S20_FAMILY_CODE):
		#	raise ValueError("Incorrect family code in device address; only DS18B20 & DS18S20 supported.")
		
		self._address = address
		self._device = OneWireDevice(bus, address)
		self._resolution = resolution if resolution in RESOLUTION_VALUES else 12
		self._conv_delay = CONVERSION_DELAY_MAP[self._resolution]		## Pessimistic default
		self._target_temp = target
		self._temp_flux = flux 
		self._last_read_temp = None
		self._last_read_time = time.monotonic() - TEMP_REFRESH_TIMEOUT


	@property
	def rom_id(self):
		return self._address.rom

	@property
	def temperature(self):
		"""The temperature in degrees Celsius."""
		if self._last_read_temp is None or (time.monotonic() - self._last_read_time) >= TEMP_REFRESH_TIMEOUT:
			assert(self._convert_temp())
			self._last_read_temp = self._read_temp()
			# self._last_read_time = time.monotonic()
		return self._last_read_temp
	
	@property
	def temperature_fahrenheit(self):
		"""The temperature in degrees Fahrenheit."""
		return fahr_from_celsius(self.temperature)


	@property
	def resolution(self):
		"""The programmable resolution. 9, 10, 11, or 12 bits."""
		
		## TODO: Implement capability for reading sensor resolution from EEPROM during runtime
		"""
		self._resolution = RESOLUTION_VALUES[self._read_scratch()[4] >> 5 & 0x03]
		"""

		return self._resolution
		
		

	@resolution.setter
	def resolution(self, bits):
		if bits not in RESOLUTION_VALUES:
			raise ValueError("Incorrect resolution. Must be 9, 10, 11, or 12.")
		
		## TODO: Implement capability for setting/changing sensor resolution during runtime
		"""
		self._buf[0] = 0  # TH register
		self._buf[1] = 0  # TL register
		self._buf[2] = RESOLUTION_VALUES.index(bits) << 5 | 0x1F  # configuration register
		self._write_scratch(self._buf)
		"""

		self._resolution = bits 


	@property
	def conversion_delay(self):
		self._conv_delay = CONVERSION_DELAY_MAP.get(self.resolution)
		return self._conv_delay



	def _convert_temp(self, timeout=CONVERSION_TIMEOUT):
		"""
		CONVERT T [44h]
		This command initiates a single temperature conversion.
		"""
		with self._device as dev: 		## Automatically invokes `OneWireBus.reset()` and `OneWireBus.match_rom(self._address)`
			dev.write_command(eeprom_commands['CONVT_TEMP'])
			dev.write_control(const.bus_commands['EXEC_W_PULLUP'])
			time.sleep(self.conversion_delay)
			return dev.status == const.bitmasks['STA_CMD']   #0x8



	def _read_temp(self):
		"""
		buf = self._read_scratch()
		if self._address.family_code == 0x10:
			if buf[1]:
				t = buf[0] >> 1 | 0x80
				t = -((~t + 1) & 0xFF)
			else:
				t = buf[0] >> 1
			return t - 0.25 + (buf[7] - buf[6]) / buf[7]
		t = buf[1] << 8 | buf[0]
		if t & 0x8000:  # sign bit set
			t = -((t ^ 0xFFFF) + 1)
		return t / 16
		"""

		assert(self._read_scratch())
		"""
		t_lo = self._device.read(const.bram_registers['RD_DATA0'])
		t_hi = self._device.read(const.bram_registers['RD_DATA1'])
		raw_temp = (t_hi << 32) + t_lo 
		"""
		temp_raw = self._device.read(const.bram_registers['RD_DATA0'])
		self._last_read_time = time.monotonic()
		return celsius_from_raw(temp_raw) 



	def _read_scratch(self):
		"""
		READ SCRATCHPAD [BEh]
		This command allows the master to read the contents of the scratchpad register.
		Note: master must generate read time slots immediately after issuing the command.
		"""
		with self._device as dev: 		## Automatically invokes `OneWireBus.reset()` and `OneWireBus.match_rom(self._address)`
			dev.write_command(eeprom_commands['SCRATCH_RD'])
			dev.write(const.bram_registers['RD_SIZE'], SCRATCH_RD_SIZE)
			dev.write_control(const.bus_commands['RD_TIME_SLOTS'])
			count = 0
			while dev.status & const.bitmasks['STA_RDD'] == 0:
				count += 1
				if count > 20:
					print('Scratchpad Read Error')
					return False
				# timeout()
				time.sleep(RW_TIME)
		return True


	def _write_scratch(self, value):
		## TODO 
		return False 


	def read_temperature(self):
		"""Read the temperature. No polling of the conversion busy bit
		(assumes that the conversion has completed)."""
		return self._read_temp()

