import time
from util import util, comports
from opcn2 import opcn2
from k33 import k33_uart as k33

k33_usb_port = None 
opc_usb_port = None 
ports_dict = comports.get_com_ports(display_ports=False)
for port in ports_dict.keys():
	desc = ports_dict[port]
	if 'USB-ISS' in desc:
		opc_usb_port = port
		print(f"[{__file__}] Using port '{port}' for connecting the OPC-N2 sensor  ('{desc}')")
	elif 'FT232R USB UART' in desc:
		k33_usb_port = port 
		print(f"[{__file__}] Using port '{port}' for connecting the K33-ELG sensor  ('{desc}')")

## Instantiate K33-ELG sensor:
co2_sensor = k33.K33(port=k33_usb_port) if k33_usb_port is not None else k33.K33()
print(f"[{__file__}] K33-ELG enabled.")

## Instantiate OPC-N2 sensor:
opc_sensor = opcn2.OPC_N2(use_usb=True, usb_port=opc_usb_port) if opc_usb_port is not None else opcn2.OPC_N2()
print(f"[{__file__}] OPC-N2 enabled.")

while True:
	try:
		co2 = co2_sensor.read_co2()
		pm = opc_sensor.pm()
		print(f"\nCO2 = {co2} ppm\nPM1 = {pm['PM1']} #/cc\nPM2.5 = {pm['PM2.5']} #/cc\nPM10 = {pm['PM10']} #/cc\n========================\n")
		time.sleep(5)
	except KeyboardInterrupt:
		print(f'\n{__file__} ABORTING.\n')
		break

opc_sensor.off()
