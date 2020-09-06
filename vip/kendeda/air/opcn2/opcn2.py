import time
import opc      ## Pypi package name:  py-opc
from opc.exceptions import FirmwareVersionError

OFF_STATE = 0x0
ON_STATE  = 0x1

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
    def __init__(self, use_usb=False, usb_port="/dev/ttyACM0"):
        if use_usb:
            from usbiss.spi import SPI
            self.spi = SPI(usb_port)
        else:
            import spidev
            self.spi = spidev.SpiDev()      ## Open a SPI connection on CE0 (Pin 24)
            self.spi.open(0, 0)

        time.sleep(1)

        ## Set the SPI mode and clock speed
        self.spi.mode = 1
        self.spi.max_speed_hz = 500000
        self._state = OFF_STATE
        self._prev_pm = None
        self._last_read_time = 0
        self._opcn2 = None
        spi_err_cnt = 0
        while self._opcn2 is None and spi_err_cnt < 5:
            try:
                self._opcn2 = opc.OPCN2(self.spi)
            except FirmwareVersionError as fve:
                spi_err_cnt += 1
                print("[OPC_N2] FirmwareVersionError #{} caught, check power supply ...".format(spi_err_cnt))
                print("\t{0}: {1}".format(type(fve).__name__, fve))
                time.sleep(1)
            except IndexError as ie:
                spi_err_cnt += 1
                print("[OPC_N2] py-opc incurred an IndexError, ignoring ...")
                print("\t{0}: {1}".format(type(ie).__name__, ie))
                time.sleep(0.5)
        time.sleep(1)
        if self._opcn2:
            print("[OPC_N2] Optical Particle Counter initialized ({}) after {} attempts ...".format("USB" if use_usb else "GPIO", spi_err_cnt+1))
        else:
            raise ValueError("\n[OPC_N2] ERROR: INIT FAILED AFTER {} ATTEMPTS (SPI bus error!)\n".format(spi_err_cnt+1))
        self.on()

    def on(self):
        if self.state == OFF_STATE:
            self._opcn2.on()
            self._state = ON_STATE
            time.sleep(3)    ## Give it some time to warm up

    def off(self):
        if self.state == ON_STATE:
            self._opcn2.off()
            self._state = OFF_STATE

    def pm(self):
        """ 
        Returns a dict of the format {'PM1': x, 'PM10': y, 'PM2.5': z} 
        Particular matter density concentration units: num. of particles per cubic centimeter (#/cc).
        """
        self.on()    ## Ensure device is on before attempting a read operation
        pm = self._opcn2.pm()
        pm_err_cnt = 0
        while not any(pm.values()):
            if pm_err_cnt > 4:
                break
            pm = self._opcn2.pm()
            pm_err_cnt += 1
        for key in pm.keys():
            pm[key] = round(pm[key], 4)
        self._prev_pm = pm
        self._last_read_time = time.time()
        return pm 

    def histogram(self):
        """
        Returns a dictionary with the following entries:
            {
                'Temperature': None,
                'Pressure': None,
                'Bin 0': 0,
                'Bin 1': 0,
                'Bin 2': 0,
                ...
                'Bin 15': 0,
                'SFR': 3.700,
                'Bin1MToF': 0,
                'Bin3MToF': 0,
                'Bin5MToF': 0,
                'Bin7MToF': 0,
                'PM1': 0.0,
                'PM2.5': 0.0,
                'PM10': 0.0,
                'Sampling Period': 2.345,
                'Checksum': 0
            }
        """
        self.on()    ## Ensure device is on before attempting a read operation
        hist = self._opcn2.histogram()
        self._prev_pm = {   
                        'PM1':round(hist['PM1'], 4), 
                        'PM10':round(hist['PM10'], 4), 
                        'PM2.5':round(hist['PM2.5'], 4)
                        }
        self._last_read_time = time.time()
        return hist


    @property
    def state(self):
        return self._state

    @property
    def prev_pm(self):
        if self._prev_pm is None or (time.time() - self._last_read_time) > 2:
            return self.pm()
        return self._prev_pm

    # @property
    def PM1(self):
        return round(self.prev_pm['PM1'], 4)
    
    # @property
    def PM25(self):
        return round(self.prev_pm['PM2.5'], 4)

    # @property
    def PM10(self):
        return round(self.prev_pm['PM10'], 4)


    def __del__(self):
        self.off()
