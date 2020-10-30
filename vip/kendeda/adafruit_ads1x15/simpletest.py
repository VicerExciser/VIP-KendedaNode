import time
import ads1015 as ADS 
from analog_in import AnalogIn 

from pynq import Overlay  #, PL
from pynq.lib import MicroblazeLibrary

overlay = Overlay('base.bit')
lib = MicroblazeLibrary(overlay.iop_arduino, ['i2c'])
i2c = lib.i2c_open_device(0)

ads = ADS.ADS1015(i2c)
channels = [AnalogIn(ads, ADS.P0), AnalogIn(ads, ADS.P1), AnalogIn(ads, ADS.P2), AnalogIn(ads, ADS.P3)] 

print("[x] {:>5}\t{:>5}".format('raw', 'v'))
try:
	while True:
		for i in range(4):
			chan = channels[i]
			print("[{}] {:>5}\t{:>5.3f}".format(i, chan.value, chan.voltage))
			time.sleep(0.5)
		print("\n")
		time.sleep(2)
except KeyboardInterrupt:
	pass 

print("\nGoodbye.")
