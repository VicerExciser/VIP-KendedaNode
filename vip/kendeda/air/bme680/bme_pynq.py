"""
Vin - 3v3
3vo - DNC
GND - GND
SCK - SCK [I2C] | SCLK [SPI]
SDO -     [I2C] | MISO [SPI]
SDI - SDA [I2C] | MOSI [SPI]
CS  -     [I2C] | CS   [SPI] 
"""


import math

RV = 461.5  ## specific gas constant for water vapor

class BME680():
	""" Wrapper class for an Adafruit BME680 sensor breakout.
	"""

	I2C_ADDR = 0x77

	def __init__(self, bus, use_i2c=True, stabilize_humidity=False):
		""" Can use I2C or SPI to communicate with a Raspberry Pi.

		Note that the internally created Adafruit_BME680 object requires that 
		its `sea_level_pressure` attribute be set after instantiation to match
		the sensor location's barometric pressure (hPa) at sea level.
		This hPa value for Atlanta can be found here: 
			https://w1.weather.gov/data/obhistory/KATL.html
			[ Subnote: 1 millibar (mb) == 1 hectoPascal (hPa) ]

		Args:
			bus (busio.I2C or busio.SPI): Either an I2C connection if the 
				`use_i2c` flag is set to True, else an SPI connection.
			use_i2c: Boolean, defaults True for an I2C connection between the 
				board and the BME680 sensor breakout. If False and SPI is 
				preferred, the CS0 chip select pin is assumed, as well as a
				default baudrate of 100000.
			stabilize_humidity: Boolean, set to True to have the sensor 
				continuously poll its relative humidity upon initialization
				until the readings stabilize/converge

		Raises:
			ValueError: If no connected BME680 sensor is found
		"""
		if use_i2c:
			self.bme = Pynq_BME680_I2C(bus)
		else:
			self.bme = Pynq_BME680_SPI(spi, cs=0)

		## Default: A rough average of previous month's recorded air 
		## pressure measurements in Atlanta (as of March, 2020)
		self.bme.sea_level_pressure = 1029.9

		if stabilize_humidity:
			self._stabilize()

	def _stabilize(self):
		from time import sleep 
		print("[BME680] Stabilizing humidity ...")
		prev = 100.1
		hum = self.get_humidity()
		while hum < prev:
			prev = hum 
			sleep(0.5)
			hum = self.get_humidity()
		print("[BME680] Humidity stabilized at {:4.2f}%".format(hum))

	def get_temperature(self):
		""" Returns the compensated temperature in degrees celsius.
		"""
		return self.bme.temperature 	## Units: °C

	def get_pressure(self):
		""" Returns the barometric pressure in hectoPascals.
		"""
		return self.bme.pressure 		## Units: hPa

	def get_humidity(self):
		""" Returns the current relative humidity in RH %.
		"""
		return self.bme.humidity 		## Units: %

	def get_absolute_humidity(self):
		""" Returns the current absolute humidity (in grams
		per cubic meter) based on the current relative 
		humidity, temperature, and barometric pressure.
		Source: https://planetcalc.com/2167/
		"""
		rh = self.bme.humidity
		t = self.bme.temperature
		p = self.bme.pressure
		eW = self._saturation_vapor_pressure(p, t)
		e = eW * (rh / 100.0)
		ah = ((e / (t * RV)) * 10.0) * 1000 ## * 1000 to convert kg/m3 to g/m3
		"""
		print('-'*40)
		print(f"Temp: {t:5.3f} °C\nPressure: {p:6.3f} hPa\nSat. Press: {eW:5.3f} hPa")
		print(f"RH: {rh:5.3f} %\nAH: {ah:4.3f} g/m3\n\n")
		"""
		return self.bme.abs_humidity 		## Units: g/m3

	def _saturation_vapor_pressure(self, p, t):
		""" Source: https://planetcalc.com/2161/ """
		fp = 1.0016 + ((3.15 * 10**(-6)) * p) - (0.074 * (p**(-1)))
		ewt = 6.112 * (math.e ** ((17.62 * t) / (243.12 + t)))
		eW = fp * ewt
		return eW
	
	def get_altitude(self):
		""" Returns the altitude based on current pressure vs. the sea level 
		pressure (sea_level_pressure) which must be configured ahead of time 
		(handled here by the class constructor).
		"""
		return self.bme.altitude 		## Units: meters

	def get_voc(self):
		""" Returns the Volatile Organic Compounds concentration measurement.

		The gas resistance in ohms for the sensor reading is proportional to 
		the amount of VOC particles detected in the air.
		"""
		return self.bme.gas 			## Units: ohms	

	def update_sea_level_pressure(self, val):
		if val > 0:
			self.bme.sea_level_pressure = val

## ============================================================================

# The MIT License (MIT)
#
# Copyright (c) 2017 ladyada for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# We have a lot of attributes for this complex sensor.
# pylint: disable=too-many-instance-attributes

"""
`adafruit_bme680`
================================================================================

CircuitPython library for BME680 temperature, pressure and humidity sensor.


* Author(s): Limor Fried

Implementation Notes
--------------------

**Hardware:**

* `Adafruit BME680 Temp, Humidity, Pressure and Gas Sensor <https://www.adafruit.com/product/3660>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""


import time

try:
    import struct
except ImportError:
    import ustruct as struct

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_BME680.git"


#    I2C ADDRESS/BITS/SETTINGS
#    -----------------------------------------------------------------------
_BME680_CHIPID = 0x61

_BME680_REG_CHIPID = 0xD0
_BME680_BME680_COEFF_ADDR1 = 0x89
_BME680_BME680_COEFF_ADDR2 = 0xE1
_BME680_BME680_RES_HEAT_0 = 0x5A
_BME680_BME680_GAS_WAIT_0 = 0x64

_BME680_REG_SOFTRESET = 0xE0
_BME680_REG_CTRL_GAS = 0x71
_BME680_REG_CTRL_HUM = 0x72
_BME680_REG_STATUS = 0x73
_BME680_REG_CTRL_MEAS = 0x74
_BME680_REG_CONFIG = 0x75

_BME680_REG_MEAS_STATUS = 0x1D
_BME680_REG_PDATA = 0x1F
_BME680_REG_TDATA = 0x22
_BME680_REG_HDATA = 0x25

_BME680_SAMPLERATES = (0, 1, 2, 4, 8, 16)
_BME680_FILTERSIZES = (0, 1, 3, 7, 15, 31, 63, 127)

_BME680_RUNGAS = const(0x10)

_LOOKUP_TABLE_1 = (
    2147483647.0,
    2147483647.0,
    2147483647.0,
    2147483647.0,
    2147483647.0,
    2126008810.0,
    2147483647.0,
    2130303777.0,
    2147483647.0,
    2147483647.0,
    2143188679.0,
    2136746228.0,
    2147483647.0,
    2126008810.0,
    2147483647.0,
    2147483647.0,
)

_LOOKUP_TABLE_2 = (
    4096000000.0,
    2048000000.0,
    1024000000.0,
    512000000.0,
    255744255.0,
    127110228.0,
    64000000.0,
    32258064.0,
    16016016.0,
    8000000.0,
    4000000.0,
    2000000.0,
    1000000.0,
    500000.0,
    250000.0,
    125000.0,
)


def _read24(arr):
    """Parse an unsigned 24-bit value as a floating point and return it."""
    ret = 0.0
    # print([hex(i) for i in arr])
    for b in arr:
        ret *= 256.0
        ret += float(b & 0xFF)
    return ret


class Pynq_BME680:
    """Driver from BME680 air quality sensor

       :param int refresh_rate: Maximum number of readings per second. Faster property reads
         will be from the previous reading."""

    def __init__(self, *, refresh_rate=10):
        """Check the BME680 was found, read the coefficients and enable the sensor for continuous
           reads."""
        self._write(_BME680_REG_SOFTRESET, [0xB6])
        time.sleep(0.005)

        # Check device ID.
        chip_id = self._read_byte(_BME680_REG_CHIPID)
        if chip_id != _BME680_CHIPID:
            raise RuntimeError("Failed to find BME680! Chip ID 0x%x" % chip_id)

        self._read_calibration()

        # set up heater
        self._write(_BME680_BME680_RES_HEAT_0, [0x73])
        self._write(_BME680_BME680_GAS_WAIT_0, [0x65])

        self.sea_level_pressure = 1013.25
        """Pressure in hectoPascals at sea level. Used to calibrate ``altitude``."""

        # Default oversampling and filter register values.
        self._pressure_oversample = 0b011
        self._temp_oversample = 0b100
        self._humidity_oversample = 0b010
        self._filter = 0b010

        self._adc_pres = None
        self._adc_temp = None
        self._adc_hum = None
        self._adc_gas = None
        self._gas_range = None
        self._t_fine = None

        self._last_reading = 0
        self._min_refresh_time = 1 / refresh_rate

    @property
    def pressure_oversample(self):
        """The oversampling for pressure sensor"""
        return _BME680_SAMPLERATES[self._pressure_oversample]

    @pressure_oversample.setter
    def pressure_oversample(self, sample_rate):
        if sample_rate in _BME680_SAMPLERATES:
            self._pressure_oversample = _BME680_SAMPLERATES.index(sample_rate)
        else:
            raise RuntimeError("Invalid oversample")

    @property
    def humidity_oversample(self):
        """The oversampling for humidity sensor"""
        return _BME680_SAMPLERATES[self._humidity_oversample]

    @humidity_oversample.setter
    def humidity_oversample(self, sample_rate):
        if sample_rate in _BME680_SAMPLERATES:
            self._humidity_oversample = _BME680_SAMPLERATES.index(sample_rate)
        else:
            raise RuntimeError("Invalid oversample")

    @property
    def temperature_oversample(self):
        """The oversampling for temperature sensor"""
        return _BME680_SAMPLERATES[self._temp_oversample]

    @temperature_oversample.setter
    def temperature_oversample(self, sample_rate):
        if sample_rate in _BME680_SAMPLERATES:
            self._temp_oversample = _BME680_SAMPLERATES.index(sample_rate)
        else:
            raise RuntimeError("Invalid oversample")

    @property
    def filter_size(self):
        """The filter size for the built in IIR filter"""
        return _BME680_FILTERSIZES[self._filter]

    @filter_size.setter
    def filter_size(self, size):
        if size in _BME680_FILTERSIZES:
            self._filter = _BME680_FILTERSIZES.index(size)
        else:
            raise RuntimeError("Invalid size")

    @property
    def temperature(self):
        """The compensated temperature in degrees celsius."""
        self._perform_reading()
        calc_temp = ((self._t_fine * 5) + 128) / 256
        return calc_temp / 100

    @property
    def pressure(self):
        """The barometric pressure in hectoPascals"""
        self._perform_reading()
        var1 = (self._t_fine / 2) - 64000
        var2 = ((var1 / 4) * (var1 / 4)) / 2048
        var2 = (var2 * self._pressure_calibration[5]) / 4
        var2 = var2 + (var1 * self._pressure_calibration[4] * 2)
        var2 = (var2 / 4) + (self._pressure_calibration[3] * 65536)
        var1 = (
            (((var1 / 4) * (var1 / 4)) / 8192)
            * (self._pressure_calibration[2] * 32)
            / 8
        ) + ((self._pressure_calibration[1] * var1) / 2)
        var1 = var1 / 262144
        var1 = ((32768 + var1) * self._pressure_calibration[0]) / 32768
        calc_pres = 1048576 - self._adc_pres
        calc_pres = (calc_pres - (var2 / 4096)) * 3125
        calc_pres = (calc_pres / var1) * 2
        var1 = (
            self._pressure_calibration[8] * (((calc_pres / 8) * (calc_pres / 8)) / 8192)
        ) / 4096
        var2 = ((calc_pres / 4) * self._pressure_calibration[7]) / 8192
        var3 = (((calc_pres / 256) ** 3) * self._pressure_calibration[9]) / 131072
        calc_pres += (var1 + var2 + var3 + (self._pressure_calibration[6] * 128)) / 16
        return calc_pres / 100

    @property
    def humidity(self):
        """The relative humidity in RH %"""
        self._perform_reading()
        temp_scaled = ((self._t_fine * 5) + 128) / 256
        var1 = (self._adc_hum - (self._humidity_calibration[0] * 16)) - (
            (temp_scaled * self._humidity_calibration[2]) / 200
        )
        var2 = (
            self._humidity_calibration[1]
            * (
                ((temp_scaled * self._humidity_calibration[3]) / 100)
                + (
                    (
                        (
                            temp_scaled
                            * ((temp_scaled * self._humidity_calibration[4]) / 100)
                        )
                        / 64
                    )
                    / 100
                )
                + 16384
            )
        ) / 1024
        var3 = var1 * var2
        var4 = self._humidity_calibration[5] * 128
        var4 = (var4 + ((temp_scaled * self._humidity_calibration[6]) / 100)) / 16
        var5 = ((var3 / 16384) * (var3 / 16384)) / 1024
        var6 = (var4 * var5) / 2
        calc_hum = (((var3 + var6) / 1024) * 1000) / 4096
        calc_hum /= 1000  # get back to RH

        if calc_hum > 100:
            calc_hum = 100
        if calc_hum < 0:
            calc_hum = 0
        return calc_hum

    @property
    def altitude(self):
        """The altitude based on current ``pressure`` vs the sea level pressure
           (``sea_level_pressure``) - which you must enter ahead of time)"""
        pressure = self.pressure  # in Si units for hPascal
        return 44330 * (1.0 - math.pow(pressure / self.sea_level_pressure, 0.1903))

    @property
    def gas(self):
        """The gas resistance in ohms"""
        self._perform_reading()
        var1 = (
            (1340 + (5 * self._sw_err)) * (_LOOKUP_TABLE_1[self._gas_range])
        ) / 65536
        var2 = ((self._adc_gas * 32768) - 16777216) + var1
        var3 = (_LOOKUP_TABLE_2[self._gas_range] * var1) / 512
        calc_gas_res = (var3 + (var2 / 2)) / var2
        return int(calc_gas_res)

    def _perform_reading(self):
        """Perform a single-shot reading from the sensor and fill internal data structure for
           calculations"""
        if time.monotonic() - self._last_reading < self._min_refresh_time:
            return

        # set filter
        self._write(_BME680_REG_CONFIG, [self._filter << 2])
        # turn on temp oversample & pressure oversample
        self._write(
            _BME680_REG_CTRL_MEAS,
            [(self._temp_oversample << 5) | (self._pressure_oversample << 2)],
        )
        # turn on humidity oversample
        self._write(_BME680_REG_CTRL_HUM, [self._humidity_oversample])
        # gas measurements enabled
        self._write(_BME680_REG_CTRL_GAS, [_BME680_RUNGAS])

        ctrl = self._read_byte(_BME680_REG_CTRL_MEAS)
        ctrl = (ctrl & 0xFC) | 0x01  # enable single shot!
        self._write(_BME680_REG_CTRL_MEAS, [ctrl])
        new_data = False
        while not new_data:
            data = self._read(_BME680_REG_MEAS_STATUS, 15)
            new_data = data[0] & 0x80 != 0
            time.sleep(0.005)
        self._last_reading = time.monotonic()

        self._adc_pres = _read24(data[2:5]) / 16
        self._adc_temp = _read24(data[5:8]) / 16
        self._adc_hum = struct.unpack(">H", bytes(data[8:10]))[0]
        self._adc_gas = int(struct.unpack(">H", bytes(data[13:15]))[0] / 64)
        self._gas_range = data[14] & 0x0F

        var1 = (self._adc_temp / 8) - (self._temp_calibration[0] * 2)
        var2 = (var1 * self._temp_calibration[1]) / 2048
        var3 = ((var1 / 2) * (var1 / 2)) / 4096
        var3 = (var3 * self._temp_calibration[2] * 16) / 16384
        self._t_fine = int(var2 + var3)

    def _read_calibration(self):
        """Read & save the calibration coefficients"""
        coeff = self._read(_BME680_BME680_COEFF_ADDR1, 25)
        coeff += self._read(_BME680_BME680_COEFF_ADDR2, 16)

        coeff = list(struct.unpack("<hbBHhbBhhbbHhhBBBHbbbBbHhbb", bytes(coeff[1:39])))
        # print("\n\n",coeff)
        coeff = [float(i) for i in coeff]
        self._temp_calibration = [coeff[x] for x in [23, 0, 1]]
        self._pressure_calibration = [
            coeff[x] for x in [3, 4, 5, 7, 8, 10, 9, 12, 13, 14]
        ]
        self._humidity_calibration = [coeff[x] for x in [17, 16, 18, 19, 20, 21, 22]]
        self._gas_calibration = [coeff[x] for x in [25, 24, 26]]

        # flip around H1 & H2
        self._humidity_calibration[1] *= 16
        self._humidity_calibration[1] += self._humidity_calibration[0] % 16
        self._humidity_calibration[0] /= 16

        self._heat_range = (self._read_byte(0x02) & 0x30) / 16
        self._heat_val = self._read_byte(0x00)
        self._sw_err = (self._read_byte(0x04) & 0xF0) / 16

    def _read_byte(self, register):
        """Read a byte register value and return it"""
        return self._read(register, 1)[0]

    def _read(self, register, length):
        raise NotImplementedError()

    def _write(self, register, values):
        raise NotImplementedError()



class Pynq_BME680_I2C(Pynq_BME680):
    """Driver for I2C connected BME680.

        :param int address: I2C device address
        :param bool debug: Print debug statements when True.
        :param int refresh_rate: Maximum number of readings per second. Faster property reads
          will be from the previous reading."""

    def __init__(self, i2c, address=0x77, debug=False, *, refresh_rate=10):
        #### (Original code from Adafruit):
		# """Initialize the I2C device at the 'address' given"""
        # from adafruit_bus_device import (  # pylint: disable=import-outside-toplevel
        #    i2c_device,
        # )

        # self._i2c = i2c_device.I2CDevice(i2c, address)
		####

		#### (My attempt at replacing the typically expected `busio.I2C` object with a PYNQ I2C object (created thru MicroblazeLibrary elsewhere)):
		## Ensure the passed i2c device was created by pynq.lib.pynqmicroblaze.rpc
		assert (i2c is not None) and (i2c.__class__.__name__ == 'i2c') and (i2c.val == 0)
		self._i2c = i2c
		####

        self._debug = debug
        super().__init__(refresh_rate=refresh_rate)

    def _read(self, register, length):
        """Returns an array of 'length' bytes from the 'register'"""
		####
        # with self._i2c as i2c:
        #     i2c.write(bytes([register & 0xFF]))
        #     result = bytearray(length)
        #     i2c.readinto(result)
        #     if self._debug:
        #         print("\t$%02X => %s" % (register, [hex(i) for i in result]))
        #     return result
		####
		## TODO

    def _write(self, register, values):
        """Writes an array of 'length' bytes to the 'register'"""
		####
        # with self._i2c as i2c:
        #     buffer = bytearray(2 * len(values))
        #     for i, value in enumerate(values):
        #         buffer[2 * i] = register + i
        #         buffer[2 * i + 1] = value
        #     i2c.write(buffer)
        #     if self._debug:
        #         print("\t$%02X <= %s" % (values[0], [hex(i) for i in values[1:]]))
		####
		## TODO



class Pynq_BME680_SPI(Pynq_BME680):
    """Driver for SPI connected BME680.

        :param busio.SPI spi: SPI device
        :param digitalio.DigitalInOut cs: Chip Select
        :param bool debug: Print debug statements when True.
        :param int baudrate: Clock rate, default is 100000
        :param int refresh_rate: Maximum number of readings per second. Faster property reads
          will be from the previous reading.
      """

    def __init__(self, spi, cs, baudrate=100000, debug=False, *, refresh_rate=10):
		####
        # from adafruit_bus_device import (  # pylint: disable=import-outside-toplevel
        #     spi_device,
        # )

        # self._spi = spi_device.SPIDevice(spi, cs, baudrate=baudrate)
		####
		## TODO 

        self._debug = debug
        super().__init__(refresh_rate=refresh_rate)

    def _read(self, register, length):
        if register != _BME680_REG_STATUS:
            # _BME680_REG_STATUS exists in both SPI memory pages
            # For all other registers, we must set the correct memory page
            self._set_spi_mem_page(register)

        register = (register | 0x80) & 0xFF  # Read single, bit 7 high.

		####
        # with self._spi as spi:
        #     spi.write(bytearray([register]))  # pylint: disable=no-member
        #     result = bytearray(length)
        #     spi.readinto(result)  # pylint: disable=no-member
        #     if self._debug:
        #         print("\t$%02X => %s" % (register, [hex(i) for i in result]))
        #     return result
		####
		## TODO

    def _write(self, register, values):
        if register != _BME680_REG_STATUS:
            # _BME680_REG_STATUS exists in both SPI memory pages
            # For all other registers, we must set the correct memory page
            self._set_spi_mem_page(register)
        register &= 0x7F  # Write, bit 7 low.

		####
        # with self._spi as spi:
        #     buffer = bytearray(2 * len(values))
        #     for i, value in enumerate(values):
        #         buffer[2 * i] = register + i
        #         buffer[2 * i + 1] = value & 0xFF
        #     spi.write(buffer)  # pylint: disable=no-member
        #     if self._debug:
        #         print("\t$%02X <= %s" % (values[0], [hex(i) for i in values[1:]]))
		####
		## TODO

    def _set_spi_mem_page(self, register):
        spi_mem_page = 0x00
        if register < 0x80:
            spi_mem_page = 0x10
        self._write(_BME680_REG_STATUS, [spi_mem_page])