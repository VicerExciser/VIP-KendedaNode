## arduino_opc_test.py
import os
import sys
import time
from pynq.overlays.base import BaseOverlay
try:
    from opc_pynq import OPC_Arduino 
except ModuleNotFoundError:
    for root, dirs, files in os.walk('/home/xilinx'):
        if 'opc_pynq.py' in files:
            sys.path.append(root)
    from opc_pynq import OPC_Arduino 

WAIT_FOR_START=True
LOOP_DELAY=5


# def test_   TODO


def main():
    base = BaseOverlay('base.bit')
    opc_arduino = OPC_Arduino(overlay=base, wait=WAIT_FOR_START)
    print()

    opc_arduino.on()
    print()
    time.sleep(2)

    print('*'*40)
    while True:
        try:
            print(f"\n\t{time.asctime(time.localtime())}")
            print("[arduino]")
            pm = opc_arduino.pm()
            print(f"\tPM1:    {pm['PM1']}")
            print(f"\tPM2.5:  {pm['PM2.5']}")
            print(f"\tPM10:   {pm['PM10']}\n")
            print('_'*40)
            time.sleep(LOOP_DELAY)
        except KeyboardInterrupt:
            print("\n< KeyboardInterrupt acknowledged >\n")
            break 

    print("==>  Closing arduino OPC-N2")
    opc_arduino.close()
