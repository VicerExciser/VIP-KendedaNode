import time
from pynq import Overlay, PL
from pynq.lib.arduino import Arduino_Analog, Arduino_IO

LOW  = 0
HIGH = 1

#### 10.90.12.99
#### 172.20.108.244

class AnalogMultiplexer:
	""" 
	Class for a 16-Channel Analog Multiplexer 
	https://www.sparkfun.com/datasheets/IC/cd74hc4067.pdf
	"""

	def __init__(self, en, s0, s1, s2, s3, sig):
		## The 'SIG' or 'Common' pin outputs the analog value of a selected input channel
		assert (hasattr(sig, 'read'))  # or isinstance(sig, Arduino_Analog))
		self.sig = sig 

		## The control/select pins 'S0-3' are pulled HIGH or LOW for selecting 1 of the 16 input channels
		assert (hasattr(s3, 'write') or (isinstance(s3, Arduino_IO) and s3.direction == 'out'))
		self.s3 = s3
		assert (hasattr(s2, 'write') or (isinstance(s2, Arduino_IO) and s2.direction == 'out'))
		self.s2 = s2 
		assert (hasattr(s1, 'write') or (isinstance(s1, Arduino_IO) and s1.direction == 'out'))
		self.s1 = s1 
		assert (hasattr(s0, 'write') or (isinstance(s0, Arduino_IO) and s0.direction == 'out'))
		self.s0 = s0 

		## The 'EN' pin is for enabling channel reads (must be held LOW for reading & HIGH when inactive)
		assert (hasattr(en, 'write') or (isinstance(en, Arduino_IO) and en.direction == 'out'))
		self.en = en 


	def log(self, msg):
		print(f'[{self.__class__.__name__}]  {msg}')


	def enable(self):
		self.log('Pulling EN low')
		# self.en.write(HIGH)
		self.en.write(LOW)


	def disable(self):
		self.log('Pulling EN high')
		# self.en.write(LOW)
		self.en.write(HIGH)


	def _select_channel(self, chan):
		chan_bin = (bin(chan)[2:])
		while len(chan_bin) < 4:
			chan_bin = '0' + chan_bin
		self.log(f'Selecting channel C{chan} ({chan_bin})')
		chan_bin = chan_bin[::-1]    ## Reverse bit order

		if int(chan_bin[0]):
			self.log('Enabling S0')
			self.s0.write(HIGH)
		else:
			self.s0.write(LOW)

		if int(chan_bin[1]):
			self.log('Enabling S1')
			self.s1.write(HIGH)
		else:
			self.s1.write(LOW)

		if int(chan_bin[2]):
			self.log('Enabling S2')
			self.s2.write(HIGH)
		else:
			self.s2.write(LOW)

		if int(chan_bin[3]):
			self.log('Enabling S2')
			self.s2.write(HIGH)
		else:
			self.s2.write(LOW)


	def read_channel(self, chan):
		assert 0 <= chan <= 15
		self.enable()
		self._select_channel(chan)
		voltages = self.sig.read()
		self.disable()

		if isinstance(self.sig, Arduino_Analog):
			return voltages[0]
		return voltages


arduino_pin_map = {
	## Digital pins
	'D0': 0,
	'D1': 1,
	'D2': 2,
	'D3': 3,
	'D4': 4,
	'D5': 5,
	'D6': 6,
	'D7': 7,
	'D8': 8,
	'D9': 9,
	'D10': 10,
	'D11': 11,
	'D12': 12,
	'D13': 13,
	## Analog pins
	'A0': 14,
	'A1': 15,
	'A2': 16,
	'A3': 17,
	'A4': 18,
	'A5': 19
}

universal_sig_pin = 0   ## 'A0'
universal_sig_pin_group = [0, 1]   ## ARDUINO_GROVE_A1
universal_sig_pin_index = 0

control_pin_map = {
	## Multiplexer select pin name --> PYNQ Arduino IO pin number
	'EN': 3,
	'S0': 4,
	'S1': 5,
	'S2': 6,
	'S3': 7,
}

analog_sensors_info = {
	'CO': {
		'Serial': '162030907',
		'OP1_WE': 0,  ## 'C0' channel on multiplexer (ORANGE wire)
		'OP2_AE': 1,  ## 'C1' channel on multiplexer (YELLOW wire)
		# 'WEe': ,
		# 'AEe': ,
		# 'Sens': ,
	}, 
	'NO2': {
		'Serial': '202931851',
		'OP1_WE': 2,  ## 'C2' channel on multiplexer (ORANGE wire)
		'OP2_AE': 3,  ## 'C3' channel on multiplexer (YELLOW wire)
	},
	'OX': {
		'Serial': '204930754',
		'OP1_WE': 4,  ## 'C4' channel on multiplexer (ORANGE wire)
		'OP2_AE': 5,  ## 'C5' channel on multiplexer (YELLOW wire)
	},
	'MQ7': {
		'AO': 6,
	}
}

def main():
	overlay = Overlay('base.bit', download=(PL.bitfile_name.split('/')[-1] != "base.bit"))
	assert hasattr(overlay, 'iop_arduino')
	iop = overlay.iop_arduino
	mb_info = iop.mb_info

	en_pin = Arduino_IO(mb_info, control_pin_map['EN'], 'out')
	s0_pin = Arduino_IO(mb_info, control_pin_map['S0'], 'out')
	s1_pin = Arduino_IO(mb_info, control_pin_map['S1'], 'out')
	s2_pin = Arduino_IO(mb_info, control_pin_map['S2'], 'out')
	s3_pin = Arduino_IO(mb_info, control_pin_map['S3'], 'out')

	# sig_pin = Arduino_Analog(mb_info, universal_sig_pin_group)   # [0, 1])  # ARDUINO_GROVE_A1)
	sig_pin = Arduino_IO(mb_info, arduino_pin_map['A0'], 'in')

	multiplexer = AnalogMultiplexer(en_pin, s0_pin, s1_pin, s2_pin, s3_pin, sig_pin)

	while True:
		try:
			co_we = multiplexer.read_channel(0)   # [universal_sig_pin_index]
			co_ae = multiplexer.read_channel(1)   # [universal_sig_pin_index]
			print(f'\nCO-B4:\n  WE Voltage = {co_we} V\n  AE Voltage = {co_ae} V')

			no2_we = multiplexer.read_channel(2)   # [universal_sig_pin_index]
			no2_ae = multiplexer.read_channel(3)   # [universal_sig_pin_index]
			print(f'\nNO2-B43F:\n  WE Voltage = {no2_we} V\n  AE Voltage = {no2_ae} V')

			ox_we = multiplexer.read_channel(4)   # [universal_sig_pin_index]
			ox_ae = multiplexer.read_channel(5)   # [universal_sig_pin_index]
			print(f'\nOX-B431:\n  WE Voltage = {ox_we} V\n  AE Voltage = {ox_ae} V')

			mq7_rs = multiplexer.read_channel(6)   # [universal_sig_pin_index]
			mq7_ro = 10.0
			mq7_co_ppm = round((1538.46 * (mq7_rs / mq7_ro)) ** (-1.709), 4)
			print(f'\nMQ-7:\n  Rs Voltage = {mq7_rs} V\n  Approx. CO = {mq7_co_ppm} ppm\n')

			time.sleep(2)
		except KeyboardInterrupt:
			print('\n>>> Breaking from main loop\n')

if __name__ == '__main__':
	main()
