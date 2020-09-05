import sys
# from serial.tools.list_ports import comports
import glob
import os
# from serial.tools import list_ports_common
import re

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def numsplit(text):
	"""\
	Convert string into a list of texts and numbers in order to support a
	natural sorting.
	"""
	result = []
	for group in re.split(r'(\d+)', text):
		if group:
			try:
				group = int(group)
			except ValueError:
				pass
			result.append(group)
	return result


class ListPortInfo(object):
	"""Info collection base class for serial ports"""

	def __init__(self, device, skip_link_detection=False):
		self.device = device
		self.name = os.path.basename(device)
		self.description = 'n/a'
		self.hwid = 'n/a'
		# USB specific data
		self.vid = None
		self.pid = None
		self.serial_number = None
		self.location = None
		self.manufacturer = None
		self.product = None
		self.interface = None
		# special handling for links
		if not skip_link_detection and device is not None and os.path.islink(device):
			self.hwid = 'LINK={}'.format(os.path.realpath(device))

	def usb_description(self):
		"""return a short string to name the port based on USB info"""
		if self.interface is not None:
			return '{} - {}'.format(self.product, self.interface)
		elif self.product is not None:
			return self.product
		else:
			return self.name

	def usb_info(self):
		"""return a string with USB related information about device"""
		return 'USB VID:PID={:04X}:{:04X}{}{}'.format(
			self.vid or 0,
			self.pid or 0,
			' SER={}'.format(self.serial_number) if self.serial_number is not None else '',
			' LOCATION={}'.format(self.location) if self.location is not None else '')

	def apply_usb_info(self):
		"""update description and hwid from USB data"""
		self.description = self.usb_description()
		self.hwid = self.usb_info()

	def __eq__(self, other):
		return isinstance(other, ListPortInfo) and self.device == other.device

	def __hash__(self):
		return hash(self.device)

	def __lt__(self, other):
		if not isinstance(other, ListPortInfo):
			raise TypeError('unorderable types: {}() and {}()'.format(
				type(self).__name__,
				type(other).__name__))
		return numsplit(self.device) < numsplit(other.device)

	def __str__(self):
		return '{} - {}'.format(self.device, self.description)

	def __getitem__(self, index):
		"""Item access: backwards compatible -> (port, desc, hwid)"""
		if index == 0:
			return self.device
		elif index == 1:
			return self.description
		elif index == 2:
			return self.hwid
		else:
			raise IndexError('{} > 2'.format(index))


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class SysFS(ListPortInfo):
	"""Wrapper for easy sysfs access and device info"""

	def __init__(self, device):
		super(SysFS, self).__init__(device)
		# special handling for links
		if device is not None and os.path.islink(device):
			device = os.path.realpath(device)
			is_link = True
		else:
			is_link = False
		self.usb_device_path = None
		if os.path.exists('/sys/class/tty/{}/device'.format(self.name)):
			self.device_path = os.path.realpath('/sys/class/tty/{}/device'.format(self.name))
			self.subsystem = os.path.basename(os.path.realpath(os.path.join(self.device_path, 'subsystem')))
		else:
			self.device_path = None
			self.subsystem = None
		# check device type
		if self.subsystem == 'usb-serial':
			self.usb_interface_path = os.path.dirname(self.device_path)
		elif self.subsystem == 'usb':
			self.usb_interface_path = self.device_path
		else:
			self.usb_interface_path = None
		# fill-in info for USB devices
		if self.usb_interface_path is not None:
			self.usb_device_path = os.path.dirname(self.usb_interface_path)

			try:
				num_if = int(self.read_line(self.usb_device_path, 'bNumInterfaces'))
			except ValueError:
				num_if = 1

			self.vid = int(self.read_line(self.usb_device_path, 'idVendor'), 16)
			self.pid = int(self.read_line(self.usb_device_path, 'idProduct'), 16)
			self.serial_number = self.read_line(self.usb_device_path, 'serial')
			if num_if > 1:  # multi interface devices like FT4232
				self.location = os.path.basename(self.usb_interface_path)
			else:
				self.location = os.path.basename(self.usb_device_path)

			self.manufacturer = self.read_line(self.usb_device_path, 'manufacturer')
			self.product = self.read_line(self.usb_device_path, 'product')
			self.interface = self.read_line(self.device_path, 'interface')

		if self.subsystem in ('usb', 'usb-serial'):
			self.apply_usb_info()
		#~ elif self.subsystem in ('pnp', 'amba'):  # PCI based devices, raspi
		elif self.subsystem == 'pnp':  # PCI based devices
			self.description = self.name
			self.hwid = self.read_line(self.device_path, 'id')
		elif self.subsystem == 'amba':  # raspi
			self.description = self.name
			self.hwid = os.path.basename(self.device_path)

		if is_link:
			self.hwid += ' LINK={}'.format(device)

	def read_line(self, *args):
		"""\
		Helper function to read a single line from a file.
		One or more parameters are allowed, they are joined with os.path.join.
		Returns None on errors..
		"""
		try:
			with open(os.path.join(*args)) as f:
				line = f.readline().strip()
			return line
		except IOError:
			return None


def comports(include_links=False):
	devices = glob.glob('/dev/ttyS*')           # built-in serial ports
	devices.extend(glob.glob('/dev/ttyUSB*'))   # usb-serial with own driver
	devices.extend(glob.glob('/dev/ttyXRUSB*')) # xr-usb-serial port exar (DELL Edge 3001)
	devices.extend(glob.glob('/dev/ttyACM*'))   # usb-serial with CDC-ACM profile
	devices.extend(glob.glob('/dev/ttyAMA*'))   # ARM internal port (raspi)
	devices.extend(glob.glob('/dev/rfcomm*'))   # BT serial devices
	devices.extend(glob.glob('/dev/ttyAP*'))    # Advantech multi-port serial controllers
	if include_links:
		devices.extend(list_ports_common.list_links(devices))
	return [info
			for info in [SysFS(d) for d in devices]
			if info.subsystem != "platform"]    # hide non-present internal serial ports

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def display_com_ports():
	sys.stderr.write('\n--- Available ports:\n')
	ports = dict()
	for n, (port, desc, hwid) in enumerate(sorted(comports()), 1):
		sys.stderr.write('--- {:2}: {:20} {!r}\n'.format(n, port, desc))
		ports[port] = desc 
	return ports 


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

if __name__ == "__main__":
	ports_dict = display_com_ports()
	# for k,v in ports_dict.items():
	for port in ports_dict.keys():
		desc = ports_dict[port]
		if 'USB-ISS' in desc:
			print("\nUse port '{}' for connecting the OPC-N2 sensor  ('{}')".format(port, desc))
		elif 'FT232R USB UART' in desc:
			print("\nUse port '{}' for connecting the K33-ELG sensor  ('{}')".format(port, desc))
