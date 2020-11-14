## triple_opc_test.py
import os
import sys
import time
from pynq.overlays.base import BaseOverlay
try:
    from opc_pynq import OPC_Pmod, OPC_Arduino, OPC_USB 
except ModuleNotFoundError:
    for root, dirs, files in os.walk('/home/xilinx'):
        if 'opc_pynq.py' in files:
            sys.path.append(root)
    from opc_pynq import OPC_Pmod, OPC_Arduino, OPC_USB 


WAIT_FOR_START=False
LOOP_DELAY=5

base = BaseOverlay('base.bit')
opc_pmod = OPC_Pmod(pmod_ab='A', overlay=base, wait=WAIT_FOR_START)
print()
opc_arduino = OPC_Arduino(overlay=base, wait=WAIT_FOR_START)
print()
opc_usb = OPC_USB(overlay=base, port="/dev/ttyACM0", wait=WAIT_FOR_START)
print()
devices = {'pmod':opc_pmod, 'arduino':opc_arduino, 'usb':opc_usb}
for device in devices.values():
    device.on()
    print()
    time.sleep(2)

print('*'*40)
while True:
    try:
        print(f"\n\t{time.asctime(time.localtime())}")
        for name, device in devices.items():
            print(f"[{name}]")
            pm = device.pm()
            print(f"\tPM1:    {pm['PM1']}")
            print(f"\tPM2.5:  {pm['PM2.5']}")
            print(f"\tPM10:   {pm['PM10']}\n")

        print('_'*40)
        time.sleep(LOOP_DELAY)
    except KeyboardInterrupt:
        print("\n< KeyboardInterrupt acknowledged >\n")
        break 

for name, device in devices.items():
    print(f"==>  Closing {name} OPC-N2")
    device.close()
    print()
