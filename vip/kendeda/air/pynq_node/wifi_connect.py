import os
from time import sleep
from pynq.lib import Wifi

port = Wifi()
ssid = input("Type in the SSID:")
pwd = input("Type in the password:")
port.connect(ssid, pwd)

## Pause a few seconds while connection is established, then test connection
sleep(3)
os.system("ping -I wlan0 www.github.com -c 5")

## To reset WiFi connection:
# port.reset()
