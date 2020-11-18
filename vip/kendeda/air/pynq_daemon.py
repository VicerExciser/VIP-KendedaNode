from pynq import Overlay
from pynq.lib import MicroblazeLibrary

from .alphasense import isb
from .bme import bme_pynq
from .pynq_ads1x15 import ads1015, ads1115, analog_in


## Default Arduino header pin assignments for SPI connection
ARDUINO_SCLK_PIN = 13
ARDUINO_MISO_PIN = 12
ARDUINO_MOSI_PIN = 11
ARDUINO_SS_PIN   = 10

## Default Arduino header pin assignments for UART connection
ARDUINO_UART_RXD = 0
ARDUINO_UART_TXD = 1


overlay = Overlay('base.bit')
iop = overlay.iop_arduino
lib = MicroblazeLibrary(iop, ['i2c', 'spi', 'uart', 'gpio'])

i2c = lib.i2c_open_device(0)
spi = lib.spi_open(ARDUINO_SCLK_PIN, ARDUINO_MISO_PIN, ARDUINO_MOSI_PIN, ARDUINO_SS_PIN)
uart = lib.uart_open(ARDUINO_UART_TXD, ARDUINO_UART_RXD)

bme_sensor = bme_pynq.BME680(spi, use_i2c=False, stabilize_humidity=True)

adc = ads1015.ADS1015(i2c, gain=1)
adc_channels = [analog_in.AnalogIn(adc, pin) for pin in range(4)]

co_we_pin = ads1015.P0  ## Orange wire (OP1) <--> ADC Pin 0
co_ae_pin = ads1015.P1  ## Yellow wire (OP2) <--> ADC Pin 1
co_serial = '162030904'
co_sensor = isb.CO(adc_channels[co_we_pin], adc_channels[co_ae_pin], serial=co_serial, temperature_function=bme_sensor.get_temperature)

## ... TODO ...
