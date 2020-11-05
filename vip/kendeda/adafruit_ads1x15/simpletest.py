import time
import ads1015 as ADS 
from analog_in import AnalogIn 

from pynq import Overlay  #, PL
from pynq.lib import MicroblazeLibrary

overlay = Overlay('base.bit')
lib = MicroblazeLibrary(overlay.iop_arduino, ['i2c'])
i2c = lib.i2c_open_device(0)

ads = ADS.ADS1015(i2c)
chan = AnalogIn(ads, ADS.P0)

print("{:>5}\t{:>5}".format('raw', 'v'))
try:
	while True:
		print("{:>5}\t{:>5.3f}".format(chan.value, chan.voltage))
		time.sleep(0.5)
except KeyboardInterrupt:
	break 

print("\nGoodbye.")
