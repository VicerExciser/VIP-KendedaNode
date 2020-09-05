import serial
import time
import sys
import signal
import termios
from datetime import datetime as dt

#######################
######  GLOBALS  ######
#######################

## Seconds in between successful measurement readings
LOOP_DELAY = 20

## For tracking 3 statistic classifications: I/O error count, serial read failure count, & empty response packets
DISPLAY_STATS = True
RESET_STATS_ON_SUCCESS = True
REQUEST_CO2 = True
REQUEST_RH = True
REQUEST_TEMP = True

## For termios.error: (5, 'Input/output error')
MAX_ERR_CNT = 8
_ERR = 0

## For serial.SerialException events incurred by ser.read() failure
MAX_FAIL_CNT = 16
_FAIL = 1

## For empty byte response blocks returned from the K33
MAX_EMPTY_CNT = 32
_EMPTY = 2

#######################
#######################

class K33():
	""" 
    Wrapper class for easy standardized setup/config of a CO2Meter K33-ELG sensor. 
    For driving the K33-ELG using the provided USB cable, set the `port` parameter 
    to something like `/dev/ttyUSB0`. Else, if connecting via GPIO pins, `port` will
    likely be something like `/dev/serial0`. All communications use the UART protocol.
    
    Note: `/dev/serial0` == `/dev/ttyS0` == `/dev/ttyAMA0`  (see: https://www.raspberrypi.org/documentation/configuration/uart.md)
     ^ This is true for RPi 3B+ & 4  (see: https://raspberrypi.stackexchange.com/questions/69697/what-is-dev-ttyama0)

    K33's RX_D pin  <-->  Pi's TxD (pin 8)  /  PYNQ-Z1's TxD (Digital IO pin 1)
	K33's TX_D pin  <-->  Pi's RxD (pin 10) /  PYNQ-Z1's RxD (Digital IO pin 0)
    """

    ## Seven byte request for reading CO2 ppm from the K33:
	## 	[0]   = Address byte (0xFE)
	##	[1]   = Command byte (0x44 for RAM Read, else 0x46 for EEPROM Read)
	##	[2:3] = Address (0x0008 is the RAM address for the CO2 Register)
	##	[4]   = Number of bytes to read (2 bytes for 0x08 & 0x09)
	##	[5:6] = Checksum / CRC (0x259F, sent with the low byte first)
	READ_CO2_CMD = bytes([0xFE, 0x44, 0x00, 0x08, 0x02, 0x9F, 0x25])
	READ_RH_CMD = bytes([0xFE, 0x44, 0x00, 0x14, 0x02, 0x97, 0xE5]) 	## Pulls relative humidity from K33
	READ_TEMP_CMD = bytes([0xFE, 0x44, 0x00, 0x12, 0x02, 0x94, 0x45])

	def __init__(self, port='/dev/serial0'):
		self.port = port 
		self.ser = serial.Serial(port, baudrate=9600, timeout=0.5)
		self.flush()
		self.stats = [0]*3
		self.loop_cnt = 0   ## Loop counter (ignoring failed measurement attempts)
		self._prev_co2 = 0
		self._prev_rh = 0
		self._prev_temp = 0
		signal.signal(signal.SIGINT, self.handle_signal)
		signal.signal(signal.SIGTERM, self.handle_signal)
		time.sleep(1)


	@staticmethod
	def get_timestamp():
		return dt.now().strftime('%m/%d/%Y,%I:%M:%S %p')


	def flush(self):
		try:
			self.ser.flushInput()
		except termios.error as t_e:
			self.stats[_ERR] += 1
			self.loop_cnt = 0
			if self.stats[_ERR] > MAX_ERR_CNT:
				print("{}\n[ERROR] termios exceptions caused routine to fail, terminating now.\n".format(t_e))
				self.show_stats()
				self.close()
				sys.exit(1)

	def read_co2(self):
		"""
		co2 = 0
		while co2 <= 0 or co2 == self._prev_co2 or (co2 > 0 and self._prev_co2 > 0 and co2 > (self._prev_co2 << 4)):
			co2 = self._read_uart(self.READ_CO2_CMD)
			if co2 <= 0 or co2 == self._prev_co2 or (co2 > 0 and self._prev_co2 > 0 and co2 > (self._prev_co2 << 4)):
				print("[read_co2]  Bad co2 value:  {}".format(co2))
		"""
		co2 = self._read_uart(self.READ_CO2_CMD)
		self._prev_co2 = co2
		return co2

	def read_rh(self):
		rh = round(self._read_uart(self.READ_RH_CMD) * 0.01, 2)
		self._prev_rh = rh
		return rh

	def read_temp(self):
		temp = round(self._read_uart(self.READ_TEMP_CMD) * 0.01, 2)
		self._prev_temp = temp 
		return temp


	def _reset_uart(self):
		## The following close-delay-open block is absolutely necessary for reliable 
		## UART communication prior to serial reads (for some reason...)
		self.ser.close()
		time.sleep(0.5)
		self.ser.open()

	"""
	def _read_uart(self, cmd):
		self._reset_uart()
		self.ser.write(cmd)
		time.sleep(0.5)
		resp = self.ser.read(7)
		if len(resp) < 5:
			print("FAILED:  resp = '{}'".format(resp))
			return 0.00
		# high = ord(resp[3].decode())
		# low = ord(resp[4].decode())
		# retval = (high * 256) + low
		high = resp[3]
		low = resp[4]
		retval = (high << 8) + low
		return retval
	"""
	
	
	def _read_uart(self, cmd):
		self._reset_uart()
		self.flush()
		'''
		error_occurred = True
		while error_occurred:
			try:
				# self.ser.flushInput()
				self.flush()
			except termios.error as t_e:
				self.stats[_ERR] += 1
				if self.stats[_ERR] > MAX_ERR_CNT:
					print("{}\n[ERROR] termios exceptions caused routine to fail, terminating now.\n".format(t_e))
					self.show_stats()
					sys.exit(1)
				time.sleep(0.2)
				# continue
				# return -1
				break
			else:
				error_occurred = False
		'''
		## Issue command to initiate reading a measured value from RAM
		self.ser.write(cmd)
		time.sleep(0.125)  #0.5)  #1)

		error_occurred = True
		while error_occurred:
			try:
				## Request 7 bytes (CO2/RH/Temp value extracted from bytes 4 & 5)
				resp = self.ser.read(7)
			except serial.SerialException as s_e:
				self.stats[_FAIL] += 1
				self.loop_cnt = 0
				if self.stats[_FAIL] > MAX_FAIL_CNT:
					print("{}\n[FAILURE] serial.read() repeatedly failed to communicate with device, terminating now.\n".format(s_e))
					self.show_stats()
					sys.exit(1)
				time.sleep(0.2)
				# continue
				return -1
			else:
				error_occurred = False

		ret_val = 0
		bytes_recvd = len(resp)
		if bytes_recvd > 3:
			if len(resp) != 7:
				print("  ~~ [ANOMALY_1] response bytes received: {}  ~~\n".format(bytes_recvd))

			ret_val = (resp[3] << 8) + resp[4]

			if RESET_STATS_ON_SUCCESS:
				## Set all statistics to 0
				self.stats = [0 for s in self.stats]
			self.loop_cnt += 1

		elif bytes_recvd == 0:
			self.stats[_EMPTY] += 1
			self.loop_cnt = 0
			if self.stats[_EMPTY] > MAX_EMPTY_CNT:
				print("\n[NO_RESP] over {} consecutive read attempts returned no data, terminating now.\n".format(MAX_EMPTY_CNT))
				self.show_stats()
				sys.exit(1)
		else:
			print("  ~~ [ANOMALY_2] response bytes received: {}  ~~\n".format(bytes_recvd))

		return ret_val
	
	def close(self):
		if self.ser.is_open:
			self.ser.close()

	def show_stats(self):
		if DISPLAY_STATS:
			print("\n ___Stats___\n\ttermios I/O errors from flush:\t{0}\n\tSerialException read fails:\t{1}\n\tEmpty byte responses received:\t{2}\n".format(*self.stats))

	def handle_signal(self, signum, stack):
		print(" < Signal received ({}) > \n".format(signum))
		self.show_stats()
		# if self.ser.is_open:
		# 	self.ser.close()
		self.close()
		sys.exit(0)


#######################
#######################

if __name__ == "__main__":
	k33 = K33("/dev/ttyUSB0") 
	# k33 = K33("/dev/ttyAMA0") 
	# k33 = K33("/dev/ttyS0") 

	while True:
		if REQUEST_CO2:
			co2 = k33.read_co2()
			ts = K33.get_timestamp()
			print("<{}> [{}]\tCO2: {} ppm".format(k33.loop_cnt, ts, co2))

		if REQUEST_RH:
			humid = k33.read_rh()
			ts = K33.get_timestamp()
			print("<{}> [{}]\tHumidity: {} %".format(k33.loop_cnt, ts, humid))

		if REQUEST_TEMP:
			temp = k33.read_temp()
			ts = K33.get_timestamp()
			print("<{}> [{}]\tTemperature: {} C".format(k33.loop_cnt, ts, temp))
			
		print('')
		time.sleep(LOOP_DELAY)
