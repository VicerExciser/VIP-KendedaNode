## Recommended to add to the bottom of ~/.bashrc:
##
##    python3 /home/pi/VIP-KendedaNode/vip/kendeda/air/opc_off.py >/dev/null
##
import opcn2
opc = opcn2.OPC_N2(use_usb=True, usb_port="/dev/ttyACM0")
opc.off()

