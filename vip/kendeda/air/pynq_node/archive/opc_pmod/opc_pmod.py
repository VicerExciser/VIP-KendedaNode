import os
import sys
import time
import struct
try:
	from . import Pmod
except:
	from pynq.lib import Pmod
from pynq.overlays.base import BaseOverlay

## ==================================================================

TESTING = False			## If True, will only run the OPC '_test_*' functions
MOCK_MICROBLAZE = False

LIB_PATH_PREFIX = "/home/xilinx/pynq/lib/pmod"
OPC_PROGRAM = "opc_pmod.bin"

OFF = 0
ON  = 1

CONFIG_IOP_SWITCH = 0x1
OPC_ON            = 0x3
OPC_OFF           = 0x5
OPC_CLOSE         = 0x7
READ_PM           = 0x9
READ_HIST         = 0xB
NUM_DEVICES       = 0xD
READ_STATE        = 0xF

## ==================================================================

def shorts2float(lo_byte_pair, hi_byte_pair):
	""" 
	Takes in 2 unsigned short (integers) and packs their collective
	4 bytes into a floating point value, then returns that float.
	"""
	ba = bytearray(struct.pack("HH", lo_byte_pair, hi_byte_pair))
	[f] = struct.unpack('f', ba)
	return f

## ==================================================================

class OPC_Pmod():
	def __init__(self, pmod_ab='A', overlay=None, mb_info=None):
		log_msg_prefix = f"[{self.__class__.__name__}] "

		if overlay is None:
			#print(f"[{__file__.split('/')[-1]}] Downloading BaseOverlay('base.bit')")
			print(f"{log_msg_prefix}Downloading BaseOverlay('base.bit')")
			overlay = BaseOverlay("base.bit")

		if mb_info is None:
			mb_info = overlay.PMODA if pmod_ab.upper() == 'A' else overlay.PMODB 

		bin_location = OPC_PROGRAM
		if not os.path.exists(bin_location):
			bin_location = os.path.join(LIB_PATH_PREFIX, OPC_PROGRAM)
			if not os.path.exists(bin_location):
				bin_location = os.path.join(LIB_PATH_PREFIX, "opc", OPC_PROGRAM)
				if not os.path.exists(bin_location):
					#print(f"\n[{__file__.split('/')[-1]}] ERROR: Could not locate program file '{OPC_PROGRAM}' -- aborting.\n")
					print(f"\n{log_msg_prefix}ERROR: Could not locate program file '{OPC_PROGRAM}' -- aborting.\n")
					sys.exit(1)
		#print(f"[{__file__.split('/')[-1]}] MicroBlaze program filepath:  '{bin_location}'\n")
		print(f"{log_msg_prefix}MicroBlaze program filepath:  '{bin_location}'\n")

		## See:  https://github.com/Xilinx/PYNQ/blob/master/pynq/lib/pmod/pmod.py
		#print("(in __init__: invoking pynq.lib.pmod.Pmod constructor)")
		self.microblaze = Pmod(mb_info, OPC_PROGRAM) if not MOCK_MICROBLAZE else None
		#print("(in __init__: returned from pynq.lib.pmod.Pmod constructor)")

		#print(f"[{__file__.split('/')[-1]}] Number of SPI devices found:  ")  #, end='')
		#print(self.get_num_devices())

		self.pm = {"PM1": 0.0, "PM2.5": 0.0, "PM10": 0.0}
		self.hist = {}



	def on(self):
		if self.microblaze is not None:
			self.microblaze.write_blocking_command(OPC_ON)
		else:
			print("[OPC::on] Error: microblaze instance is None -- ignoring call to 'on()'.")


	def off(self):
		if self.microblaze is not None:
			self.microblaze.write_blocking_command(OPC_OFF)
		else:
			print("[OPC::off] Error: microblaze instance is None -- ignoring call to 'off()'.")


	def close(self):
		if self.microblaze is not None:
			self.microblaze.write_blocking_command(OPC_CLOSE)
		else:
			print("[OPC::close] microblaze instance is None -- ignoring call to 'close()'.")


	def __del__(self):
		try:
			self.off()
		except:
			pass
		try:
			self.close()
		except:
			pass 


	def get_num_devices(self):
		if self.microblaze is None:
			print("[OPC::get_num_devices] Error: microblaze instance is None -- ignoring call to 'get_num_devices()'.")
			return None
		self.microblaze.write_blocking_command(OPC_OFF)
		n = self.microblaze.read_mailbox(0)
		return n


	def read_pm(self):
		if TESTING:
			return self._test_read_pm()

		self.microblaze.write_blocking_command(READ_PM)

		pm1_lo = self.microblaze.read_mailbox(0)
		pm1_hi = self.microblaze.read_mailbox(1)
		self.pm["PM1"] = shorts2float(pm1_lo, pm1_hi)

		pm25_lo = self.microblaze.read_mailbox(2)
		pm25_hi = self.microblaze.read_mailbox(3)
		self.pm["PM2.5"] = shorts2float(pm25_lo, pm25_hi)

		pm10_lo = self.microblaze.read_mailbox(4)
		pm10_hi = self.microblaze.read_mailbox(5)
		self.pm["PM10"] = shorts2float(pm10_lo, pm10_hi)

		return self.pm


	def _test_read_pm(self):
		in_float_pm1 = in_float_pm25 = in_float_pm10 = None
		prompt_fstr = "Enter a floating point value for PM {}{}:  "

		while in_float_pm1 is None:
			try:
				in_float_pm1 = float(input(prompt_fstr.format('1', ' '*2)))
			except ValueError:
				in_float_pm1 = None
		ba_pm1 = bytearray(struct.pack('f', in_float_pm1))
		lo_pm1 = (ba_pm1[1] << 8) | ba_pm1[0] 		## Account for byte order
		hi_pm1 = (ba_pm1[3] << 8) | ba_pm1[2] 
		self.pm["PM1"] = shorts2float(lo_pm1, hi_pm1)

		while in_float_pm25 is None:
			try:
				in_float_pm25 = float(input(prompt_fstr.format('2.5', '')))
			except ValueError:
				in_float_pm25 = None
		ba_pm25 = bytearray(struct.pack('f', in_float_pm25))
		lo_pm25 = (ba_pm25[1] << 8) | ba_pm25[0] 		## Account for byte order
		hi_pm25 = (ba_pm25[3] << 8) | ba_pm25[2] 
		self.pm["PM2.5"] = shorts2float(lo_pm25, hi_pm25)

		while in_float_pm10 is None:
			try:
				in_float_pm10 = float(input(prompt_fstr.format('10', ' ')))
			except ValueError:
				in_float_pm10 = None
		ba_pm10 = bytearray(struct.pack('f', in_float_pm10))
		lo_pm10 = (ba_pm10[1] << 8) | ba_pm10[0] 		## Account for byte order
		hi_pm10 = (ba_pm10[3] << 8) | ba_pm10[2] 
		self.pm["PM10"] = shorts2float(lo_pm10, hi_pm10)

		print(f"[_test_read_pm]\n\tPM 1  :  {self.pm['PM1']}\n\tPM 2.5:  {self.pm['PM2.5']}\n\tPM 10 :  {self.pm['PM10']}\n")

		return self.pm
		

	def read_histogram(self):
		self.microblaze.write_blocking_command(READ_HIST)

		pm1_lo = self.microblaze.read_mailbox(0)
		pm1_hi = self.microblaze.read_mailbox(1)
		self.pm["PM1"] = shorts2float(pm1_lo, pm1_hi)

		pm25_lo = self.microblaze.read_mailbox(2)
		pm25_hi = self.microblaze.read_mailbox(3)
		self.pm["PM2.5"] = shorts2float(pm25_lo, pm25_hi)

		pm10_lo = self.microblaze.read_mailbox(4)
		pm10_hi = self.microblaze.read_mailbox(5)
		self.pm["PM10"] = shorts2float(pm10_lo, pm10_hi)

		self.hist["PM1"] = self.pm["PM1"]
		self.hist["PM2.5"] = self.pm["PM2.5"]
		self.hist["PM10"] = self.pm["PM10"]

		self.hist["bin0"] = self.microblaze.read_mailbox(6)
		self.hist["bin1"] = self.microblaze.read_mailbox(7)
		self.hist["bin2"] = self.microblaze.read_mailbox(8)
		self.hist["bin3"] = self.microblaze.read_mailbox(9)
		self.hist["bin4"] = self.microblaze.read_mailbox(10)
		self.hist["bin5"] = self.microblaze.read_mailbox(11)
		self.hist["bin6"] = self.microblaze.read_mailbox(12)
		self.hist["bin7"] = self.microblaze.read_mailbox(13)
		self.hist["bin8"] = self.microblaze.read_mailbox(14)
		self.hist["bin9"] = self.microblaze.read_mailbox(15)
		self.hist["bin10"] = self.microblaze.read_mailbox(16)
		self.hist["bin11"] = self.microblaze.read_mailbox(17)
		self.hist["bin12"] = self.microblaze.read_mailbox(18)
		self.hist["bin13"] = self.microblaze.read_mailbox(19)
		self.hist["bin14"] = self.microblaze.read_mailbox(20)
		self.hist["bin15"] = self.microblaze.read_mailbox(21)

		return self.hist 


	def read_state(self):
		self.microblaze.write_blocking_command(READ_STATE)
		return self.microblaze.read_mailbox(0)


	@property
	def state(self):
		return self.read_state()

## ==================================================================

if __name__ == "__main__":
	print(">>> Instantiating OPC_Pmod object ...")
	opc = OPC_Pmod()
	if not MOCK_MICROBLAZE:
		#print(f">>> Initial OPC_Pmod state:  {'OFF' if opc.state == OFF else 'ON'}")
		print(">>> Initial OPC_Pmod state:", end='  ')
		sys.stdout.flush()
		print('OFF' if opc.state == OFF else 'ON')
		print(">>> Turning the OPC_Pmod on ...")
		opc.on()
		time.sleep(4)
		#print(f">>> New OPC_Pmod state:  {'OFF' if opc.state == OFF else 'ON'}")
		print(">>> New OPC_Pmod state:", end='  ')
		sys.stdout.flush()
		print('OFF' if opc.state == OFF else 'ON')
	print('='*60, end='\n\n')
	for i in range(10):
		pm = opc.read_pm()  #if not TESTING else opc._test_read_pm()
		print(pm)
		print('='*60, end='\n\n')
		time.sleep(10)
	if not MOCK_MICROBLAZE:
		print(">>> Turning the OPC_Pmod off ...")
		opc.off()
		# print(f">>> Final OPC_Pmod state:  {'OFF' if opc.state == OFF else 'ON'}")
		print(">>> Final OPC_Pmod state:", end='  ')
		sys.stdout.flush()
		print('OFF' if opc.state == OFF else 'ON')
