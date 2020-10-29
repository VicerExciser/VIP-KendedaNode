try:
	from .bus import OneWireBus, OneWireAddress
	from . import constants as const
except (ImportError, ModuleNotFoundError):
	import os, sys
	rootpath = '/'.join(os.getcwd().split('/'))  #[:-1])
	print(f"[{__file__}] Appending '{rootpath}' to sys.path")
	sys.path.append(rootpath)
	from .bus import OneWireBus, OneWireAddress
	from . import constants as const


class OneWireDevice:
	"""A class to represent a single device on the 1-Wire bus."""

	def __init__(self, bus, address):
		assert(isinstance(bus, OneWireBus))
		self._bus = bus
		assert(isinstance(address, OneWireAddress))
		self._address = address 

		self.reset = self._bus.reset 
		self.write = self._bus.write 
		self.write_command = self._bus.write_command
		self.write_control = self._bus.write_control
		self.read = self._bus.read
		

	def __enter__(self):
		self._select_rom()
		return self

	def __exit__(self, *exc):
		return False

	@property
	def status(self):
		return self._bus.read_status()


	# def reset(self):
	# 	"""OneWireBus.reset() wrapper."""
	# 	return self._bus.reset()

	# def write(self, register, value):
	# 	"""OneWireBus.write() wrapper."""
	# 	self._bus.write(register, value)

	# def write_command(self, cmd):
	# 	"""OneWireBus.write_command() wrapper."""
	# 	self._bus.write_command(cmd)

	# def write_control(self, cmd):
	# 	"""OneWireBus.write_control() wrapper."""
	# 	self._bus.write_control(cmd)

	# def read(self, register):
	# 	"""OneWireBus.read() wrapper."""
	# 	return self._bus.read(register)


	def _select_rom(self):
		# self._bus.reset()
		# self.write_command(const.bus_commands['MATCH_ROM'])
		# self.write(const.bram_registers['WR_DATA0'], self._address.rom_lo)
		# self.write(const.bram_registers['WR_DATA1'], self._address.rom_hi))
		self._bus.match_rom(self._address)
