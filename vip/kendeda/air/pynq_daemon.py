from pynq import Overlay, PL
from pynq.lib import MicroblazeLibrary

import air_sensors.alphasense.isb as isb
import air_sensors.bme680.bme_pynq as bme_pynq
from pynq_ads1x15.ads1015 import ADS1015
# from pynq_ads1x15.ads1115 import ADS1115
from pynq_ads1x15.analog_in import AnalogIn


## Default Arduino header pin assignments for SPI connection
ARDUINO_SCLK_PIN = 13
ARDUINO_MISO_PIN = 12
ARDUINO_MOSI_PIN = 11
ARDUINO_SS_PIN   = 10

## Default Arduino header pin assignments for UART connection
ARDUINO_UART_RXD = 0
ARDUINO_UART_TXD = 1


overlay = Overlay('base.bit', download=(PL.bitfile_name.split('/')[-1] != 'base.bit'))
iop = overlay.iop_arduino
lib = MicroblazeLibrary(iop, ['i2c', 'spi', 'uart', 'gpio'])

i2c = lib.i2c_open_device(0)
spi = lib.spi_open(ARDUINO_SCLK_PIN, ARDUINO_MISO_PIN, ARDUINO_MOSI_PIN, ARDUINO_SS_PIN)
uart = lib.uart_open(ARDUINO_UART_TXD, ARDUINO_UART_RXD)

bme_sensor = bme_pynq.BME680(spi, use_i2c=False, stabilize_humidity=True)

adc = ADS1015(i2c, gain=1)
adc_channels = [AnalogIn(adc, pin) for pin in range(4)]

co_we_pin = ads1015.P0  ## Orange wire (OP1) <--> ADC Pin 0
co_ae_pin = ads1015.P1  ## Yellow wire (OP2) <--> ADC Pin 1
co_serial = '162030904'
co_sensor = isb.CO(adc_channels[co_we_pin], adc_channels[co_ae_pin], serial=co_serial, temperature_function=bme_sensor.get_temperature)

## ... TODO ...
