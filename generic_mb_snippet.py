from pynq import Overlay, PL
from pynq.lib import MicroblazeLibrary


class ArduinoMicroblaze:
	SDA = 20
	SCL = 21

	def __init__(self, overlay=None):
		if overlay is None:
			overlay = Overlay('base.bit', download=(PL.bitfile_name.split('/')[-1] != 'base.bit'))
		mb_info = overlay.iop_arduino 
		lib = MicroblazeLibrary(mb_info, ['i2c', 'spi', 'uart', 'gpio'])