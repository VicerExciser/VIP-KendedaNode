import os

try:
	from air.bme680.bme_pynq import BME680
	# import air.bme680.bme_pynq as bme_pynq
	# from air.bme680 import bme_pynq
except (ModuleNotFoundError, ImportError):
	"""
	import sys
	# package_path = os.path.basename(os.getcwd())
	cwd = os.getcwd()
	cwd_split = cwd.split(os.path.sep)
	i = len(cwd_split) - 1
	while i > 0:
		if cwd_split[i] == 'air':
			i += 1
			break
		i -= 1

	air_package_path = os.path.join(os.path.sep, *cwd_split[:i])
	# if not air_package_path in sys.path:
	# 	print(f"[{sys.argv[0].replace('.py','')}] Appending '{air_package_path}' to sys.path")
	# 	sys.path.append(air_package_path)

	for (root,dirs,files) in os.walk(air_package_path, topdown=True):
		if '__init__.py' in files:
			# air_package_path = os.path.basename(root)
			if not root in sys.path:
				print(f"[{sys.argv[0].replace('.py','')}] Appending '{root}' to sys.path")
				sys.path.append(root)

	# import air 
	"""

	"""
	start_dir = os.getcwd()
	while 'set_pythonpath.sh' not in os.listdir():
		os.chdir('..')
	os.system("sudo bash set_pythonpath.sh")
	os.chdir(start_dir)
	"""

	from air.bme680.bme_pynq import BME680
	# from air.bme680 import bme_pynq
	# import air.bme680.bme_pynq as bme_pynq

from air.pynq_ads1x15.analog_in import AnalogIn
from air.pynq_ads1x15.ads1015 import ADS1015
import air.util.comports as comports
import air.util.weather as weather
import air.util.util as util
import air.k33.k33_pynq as k33
import air.alphasense.isb_pynq as isb
import air.opcn2.opc_pynq as opc
import air.mq7.mq7_pynq as mq7
import air.backend.influx_cloud as influx
# from pynq_ads1x15 import ads1015, analog_in




from pynq import Overlay, PL
from pynq.lib import MicroblazeLibrary

print('poop!')

