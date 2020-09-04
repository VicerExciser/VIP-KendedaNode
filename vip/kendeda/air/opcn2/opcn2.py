from time import sleep
import opc      ## Pypi package name:  py-opc
from opc.exceptions import FirmwareVersionError

""" Wiring configuration for SPI via GPIO:
------------------------------------------------------------------------
| Pin   |   Function            | OPC   | RPi                          |
------------------------------------------------------------------------
| 1     | 5V DC                 | VCC   | 5V                           |
| 2     | Serial Clock          | SCK   | SCLK (Pin 23)                |
| 3     | Master In Slave Out   | SDO   | MISO (Pin 21)                |
| 4     | Master Out Slave In   | SDI   | MOSI (Pin 19)                |
| 5     | Chip Select           | /SS   | CE0 (Pin 24) or CE1 (Pin 26) |
| 6     | Ground                | GND   | GND                          |
------------------------------------------------------------------------
"""
    
class OPC_N2():
    """ 
    Wrapper class for easy standardized setup/config of an OPC-N2 sensor. 
    For driving the OPC-N2 using the provided USB cable, set the `use_usb`
    parameter to True. Else, if `use_usb` is False, connect via GPIO pins.
    All communications use the SPI protocol.
    """
    def __init__(self, use_usb=False):
        if use_usb:
            from usbiss.spi import SPI
            self.spi = SPI("/dev/ttyACM0")
        else:
            import spidev
            self.spi = spidev.SpiDev()      ## Open a SPI connection on CE0 (Pin 24)
            self.spi.open(0, 0)

        sleep(1)

        ## Set the SPI mode and clock speed
        self.spi.mode = 1
        self.spi.max_speed_hz = 500000

        self.opcn2 = None
        spi_err_cnt = 0
        while self.opcn2 is None and spi_err_cnt < 5:
            try:
                self.opcn2 = opc.OPCN2(self.spi)
            except FirmwareVersionError as fve:
                spi_err_cnt += 1
                print("[OPC_N2] FirmwareVersionError #{} caught, check power supply ...".format(spi_err_cnt))
                print("\t{0}: {1}".format(type(fve).__name__, fve))
                sleep(0.5)
        sleep(1)
        if self.opcn2:
            print("[OPC_N2] Optical Particle Counter initialized ({}) after {} attempts ...".format("USB" if use_usb else "GPIO", spi_err_cnt))
        else:
            # print("\n[OPC_N2] ERROR: INIT FAILED (SPI bus error!)\n")
            # import sys
            # sys.exit(1)
            raise ValueError("\n[OPC_N2] ERROR: INIT FAILED AFTER {} ATTEMPTS (SPI bus error!)\n".format(spi_err_cnt))


    def on(self):
        self.opcn2.on()
        sleep(3)

    def off(self):
        self.opcn2.off()

    def pm(self):
        return self.opcn2.pm()

    def histogram(self):
        return self.opcn2.histogram()