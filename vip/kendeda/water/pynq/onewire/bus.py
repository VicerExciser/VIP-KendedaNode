import os
import time
from pynq import MMIO, Clocks
from pynq.overlays.base import BaseOverlay
from . import constants as const

###################################################################################################

def timeout(ticks=256):		## timeout for 256 ticks == ~0.01 second delay
	for c in range(1, ticks):
		for d in range(1, ticks):
			pass
	return

###################################################################################################

class OneWireError(Exception):
	"""A class to represent a 1-Wire exception."""

###################################################################################################

class OneWireAddress:
	"""A class to represent a 1-Wire address."""

	def __init__(self, rom):
		self._rom = rom		## Example:  0x5f0000060719f528

	@property
	def rom(self):
		"""The unique 64 bit ROM code."""
		return self._rom

	@property
	def rom_hi(self):
		return self._rom >> 32

	@property
	def rom_lo(self):
		return self._rom & 0xFFFFFFFF

	@property
	def crc(self):
		"""The 8 bit CRC."""
		# return self._rom[7]
		# return int((hex(self._rom)[2:])[12:14], 16)
		return self._rom >> 56

	@property
	def serial_number(self):
		"""The 48 bit serial number."""
		# return self._rom[1:7]
		return ((self._rom >> 8) & 0x00FFFFFFFFFFFF)

	@property
	def family_code(self):
		"""The 8 bit family code."""
		# return self._rom[0]
		return self._rom & 0xFF

	def __str__(self):
		return f"OneWireAddress_{hex(self.rom)}"

	def equals(self, other):
		return isinstance(other, OneWireAddress) and self.rom == other.rom 

###################################################################################################

class OneWireBus:
	""" Singleton
	"""
	# OVERLAY = None 	## Pynq Overlay instance currently installed in the fabric
	OVERLAY = BaseOverlay(const.OVERLAY_PATH)   #, download=(not OVERLAY_NAME == PL.bitfile_name.split('/')[-1]))
	# ##                               #  ^ Skipping the re-download will break 1-Wire search
	
	ROMAD_SIZE = 20 	## Large enough to hold 10 temp. sensor ROM IDs
	
	__instance = None 
	__bus_initialized = False 
	search_complete = False 

	
	@staticmethod
	def get_instance(overlay_path=const.OVERLAY_PATH):
		base_address = const.AXI_OW_ADDR(OneWireBus.OVERLAY)
		address_range = const.AXI_OW_RANGE(OneWireBus.OVERLAY)
		if OneWireBus.__instance is None:
			OneWireBus(base_addr=base_address, addr_range=address_range)			
		return OneWireBus.__instance


	def __init__(self, base_addr=const._DEFAULT_AXI_OW_ADDR, addr_range=const._DEFAULT_AXI_OW_RANGE):
		""" Virtually private constructor for singleton OneWire class. """
		if OneWireBus.__instance is None:
			self.axi_addr = base_addr
			self.axi_range = addr_range 
			self.bram = MMIO(base_addr, addr_range)
			self.device_addresses = [None]

			OneWireBus.num_roms = 0
			OneWireBus.set_clk()		## Set the PL function clock tied to the ow_master IP to 33 MHz
			OneWireBus.search_complete = True
			OneWireBus.__bus_initialized = True 
			OneWireBus.__instance = self 

			print(f"\n[__init__]  New '{self.__class__.__name__}' singleton instance has been instantiated.\n")


	@property
	def initialized(self):
		return self.__bus_initialized


	@staticmethod
	def initialized():
		return OneWire.__bus_initialized

## ---------------------------------------------------------------------------------------------

	@staticmethod
	def set_clk(mhz=const.CLK_MHZ, idx=const.OW_FCLK_IDX):
		if idx == 3:
			cur_freq = Clocks.fclk3_mhz 
		elif idx == 2:
			cur_freq = Clocks.fclk2_mhz
		elif idx == 1:
			cur_freq = Clocks.fclk1_mhz  
		elif idx == 0:
			cur_freq = Clocks.fclk0_mhz
		else:
			 print(f"[set_clk]  Invalid PL clock index: idx={idx} (must be value in range [0, 3])")
			 return
		print(f"[set_clk]  Clocks.fclk{idx}_mhz = {cur_freq}MHz")
		if abs(cur_freq - mhz) > 1: 		## Tests approximate equality to prevent call redundancy 
			print(f"[set_clk]  Setting fclk{idx} to {mhz}MHz")
			Clocks.set_pl_clk(idx, clk_mhz=mhz)


	def write(self, reg_addr, cmd):
		self.bram.write(reg_addr, cmd)


	def read(self, reg_addr):
		return self.bram.read(reg_addr)


	def read_status(self):
		return self.read(const.bram_registers['STATUS'])


	def read_num_found_roms(self):
		return self.read(const.bram_registers['FOUND'])


	def write_command(self, cmd):
		self.write(const.bram_registers['COMMAND'], cmd)


	def write_control(self, cmd):
		self.write(const.bram_registers['CONTROL'], cmd)


	def serialize_command(self):
		self.write_control(const.bus_commands['SERIALIZE'])


	def reset(self):
		"""
		RESET
		Master sends a reset pulse (by pulling the 1-Wire bus low for at least 8 time slots) 
		and any/all [DS18B20] devices respond with a presence pulse.

		NOTE: This MUST be called prior to any ROM commands/device functions as a part of the 
		necessary initialization process
		(exceptions to this are Search ROM and Search Alarms, for which both must re-initialize
		after executing)
		"""

		self.write_control(const.bus_commands['RESET_PULSE'])
		r_status = self.read_status() & const.bitmasks['STA_RSD']
		count = 0
		while r_status == 0:
			r_status = self.read_status() & const.bitmasks['STA_RSD']
			count += 1
			if count > 20:
				print('No presence pulse detected thus no devices on the bus!')
				return False
			timeout()
		return True
		
## ---------------------------------------------------------------------------------------------

	## Polls the bus for devices & returns number of slaves
	# def search(self, SensorClass, search_cmd):
	def search(self, search_cmd=const.bus_commands['SEARCH_ROM']):
		"""
		SEARCH ROM [F0h]
		The master learns the ROM codes through a process of elimination that requires the master to perform
		a Search ROM cycle as many times as necessary to identify all of the slave devices.

		Returns the count of all device IDs discovered on the bus.

		This function has been configured so that an ALARM SEARCH [ECh] command and an alarms_array may
		be passed in to only collect ROMs of slaves with a set alarm flag.
		"""

		while OneWireBus.search_complete == False:
			print('.', end='')
			timeout()
		OneWireBus.search_complete = False		## Lock the bus while performing search

		## Write search command to the command register, then serialize onto the bus to begin search
		self.write_command(search_cmd)
		self.serialize_command()

		r_status = self.read_status()
		# print(f"r_status = {hex(r_status)}")
		x = r_status & const.bitmasks['STA_SRD']
		miss_count = 0
		while x != 1 and miss_count < 30:
			r_status = self.read_status()
			# print(f"r_status = {hex(r_status)}")
			x = r_status & const.bitmasks['STA_SRD']
			timeout()
			miss_count += 1

		if r_status & const.bitmasks['STA_SER']:
			print('SEARCH PROTOCOL ERROR : SEARCH INCOMPLETE DUE TO ONE WIRE PROTOCOL ERROR\n')
			return None
		elif r_status & const.bitmasks['STA_SME']:
			print('SEARCH MEMORY ERROR : NOT ENOUGH FPGA MEMORY ALLOCATED FOR # of OW DEVICES FOUND\n')
			return None

		self.num_roms = self.read_num_found_roms()
		print(f'# ROMS FOUND = {self.num_roms}')

		# new_size = self.num_roms * 2
		# if new_size > self.ROMAD_SIZE:
		# 	self.ROMAD_SIZE = new_size
		# self.device_addresses = [0] * self.ROMAD_SIZE 
		# self.device_addresses = [None] * self.num_roms
		if self.num_roms > len(self.device_addresses):
			self.device_addresses.extend([None] * (self.num_roms - len(self.device_addresses)))

		for i in range(self.num_roms):
			rom_lo = self.read((const.bram_registers['ROM_ID0'] + (i << 3)))
			rom_hi = self.read((const.bram_registers['ROM_ID1'] + (i << 3)))
			rom_long = (rom_hi << 32) + rom_lo
			print(f"\nROM {i} ID: {hex(rom_long)}")

			# self.device_addresses[i * 2] = rom_lo
			# self.device_addresses[(i * 2) + 1] = rom_hi
			# new_device = SensorClass(rom_hi, rom_lo, onewire_index=index)
			# yield new_device

			discovered_new_rom = True
			# if self.device_addresses[i] is not None and self.device_addresses[i].rom == rom_long:
			for device in self.device_addresses:
				if device is not None and device.rom == rom_long:
					## Device has already been discovered on bus
					print(f"[OneWireBus.search]\tRe-discovered ROM:  {hex(rom_long)}")
					discovered_new_rom = False
					break 
			
			if discovered_new_rom:
				new_device = OneWireAddress(rom_long)
				print(f"[OneWireBus.search]\tDiscovered new device ROM on bus:  {new_device}")
				j = i 
				while j < len(self.device_addresses) and self.device_addresses[j] is not None:
					j += 1
				self.device_addresses[j%len(self.device_addresses)] = new_device 

		OneWireBus.search_complete = True 		## Unlock the 1-Wire bus after search is completed

		# return list(self.device_addresses)
		return [addr for addr in self.device_addresses if addr is not None]		


	def match_rom(self, address):
		"""
		MATCH ROM [55h]
		The match ROM command allows to address a specific slave device on a multidrop or single-drop bus.
		Only the slave that exactly matches the 64-bit ROM code sequence will respond to the function command
		issued by the master; all other slaves on the bus will wait for a reset pulse.
		"""
		assert(isinstance(address, OneWireAddress))
		self.reset()
		self.write_command(const.bus_commands['MATCH_ROM'])
		self.write(const.bram_registers['WR_SIZE'], const.TRANSMIT_BITS)
		self.write(const.bram_registers['WR_DATA0'], address.rom_lo)
		self.write(const.bram_registers['WR_DATA1'], address.rom_hi)
		self.write_control(const.bus_commands['EXEC_WO_PULLUP'])
		count = 0
		while self.read_status() & const.bitmasks['STA_WRD'] == 0:
			count += 1
			if (count > 20):
				print('[match_rom] Desired ROM address not matched')
				return False
			timeout()
		return True 

## ---------------------------------------------------------------------------------------------

# if __name__ == "__main__":
# 	ow_bus = OneWire.get_instance()
