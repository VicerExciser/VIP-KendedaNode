import os
import sys
import time
from pynq.lib import Wifi

time.sleep(2)
try:
	port = Wifi()
except ValueError:
	print(f"\n[{__file__}]  No compatible USB WiFi device found. Interface 'wlan0' will be unavailable.")
	sys.exit(2)
ssid = input('\nPlease enter your WiFi network name:  ')
pwd = input('Please enter your WiFi network password:  ')
port.connect(ssid, pwd, auto=True)

## Pause a few seconds while connection is established, then test connection
time.sleep(3)
os.system('ping -I wlan0 www.github.com -c 3')
