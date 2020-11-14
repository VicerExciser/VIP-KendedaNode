import os
import sys
import time
try:
	from . import Arduino
except:
	from pynq.lib import Arduino
from pynq.overlays.base import BaseOverlay

LIB_PATH_PREFIX = "/home/xilinx/pynq/lib/arduino"
OPC_PROGRAM = "opc.bin"

CONFIG_IOP_SWITCH = 0x1
OPC_ON = 0x3
OPC_OFF = 0x5
OPC_CLOSE = 0x7
READ_PM = 0x9
READ_HIST = 0xB

base = None

class OPC():
	def __init__(self, mb_info=None):
		global base 
		if base is None:
			base = BaseOverlay("base.bit")
		if mb_info is None:
			mb_info = base.ARDUINO 
		bin_location = OPC_PROGRAM
		if not os.path.exists(bin_location):
			bin_location = os.path.join(LIB_PATH_PREFIX, OPC_PROGRAM)
			if not os.path.exists(bin_location):
				bin_location = os.path.join(LIB_PATH_PREFIX, "opc", OPC_PROGRAM)
				if not os.path.exists(bin_location):
					print(f"\n[{__file__}] ERROR: Could not locate program file '{OPC_PROGRAM}' -- aborting.\n'")
					sys.exit(1)
		self.microblaze = Arduino(mb_info, OPC_PROGRAM)
		self.pm = {"PM1": 0.0, "PM2.5": 0.0, "PM10": 0.0}
		self.hist = {}


	def on(self):
		self.microblaze.write_blocking_command(OPC_ON)


	def off(self):
		self.microblaze.write_blocking_command(OPC_OFF)


	def close(self):
		self.microblaze.write_blocking_command(OPC_CLOSE)


	def __del__(self):
		try:
			self.off()
		except:
			pass
		try:
			self.close()
		except:
			pass 


	def read_pm(self):
		self.microblaze.write_blocking_command(READ_PM)
		pm1_lo = self.microblaze.read_mailbox(0)
		pm1_hi = self.microblaze.read_mailbox(1)
		self.pm["PM1"] = float(f"{pm1_lo}.{pm1_hi}")
		pm25_lo = self.microblaze.read_mailbox(2)
		pm25_hi = self.microblaze.read_mailbox(3)
		self.pm["PM2.5"] = float(f"{pm25_lo}.{pm25_hi}")
		pm10_lo = self.microblaze.read_mailbox(4)
		pm10_hi = self.microblaze.read_mailbox(5)
		self.pm["PM10"] = float(f"{pm10_lo}.{pm10_hi}")
		return self.pm


	def read_histogram(self):
		self.microblaze.write_blocking_command(READ_HIST)
		pm1_lo = self.microblaze.read_mailbox(0)
		pm1_hi = self.microblaze.read_mailbox(1)
		self.pm["PM1"] = float(f"{pm1_lo}.{pm1_hi}")
		pm25_lo = self.microblaze.read_mailbox(2)
		pm25_hi = self.microblaze.read_mailbox(3)
		self.pm["PM2.5"] = float(f"{pm25_lo}.{pm25_hi}")
		pm10_lo = self.microblaze.read_mailbox(4)
		pm10_hi = self.microblaze.read_mailbox(5)
		self.pm["PM10"] = float(f"{pm10_lo}.{pm10_hi}")
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



if __name__ == "__main__":
	opc = OPC()
	opc.on()
	for i in range(10):
		pm = opc.read_pm()
		print(pm)
		time.sleep(10)
	opc.off()
