import adafruit_sgp30

class SGP30():
        """Wrapper class for an Adafruit SGP30 sensor"""

        def __init__(self, bus):
                """ Uses I2C to communicate with the Raspberry Pi
                taking in a busio.I2C connection for its bus argument.
                In the demo bus = busio.I2c(board.SCL, board.SDA, frequency = 100000)
                using import board.

                NOTE: If no stored baseline is avaliable after initializing the baseline algorithm, 
                the sensor has to run for 12 hours until the baseline can be stored. This will endure optimal 
                behavior for preeceding startups. Reading our the baseline prior should be avoided 
                unless a valid baseline is restored first.

                """
                self.sgp = adafruit_sgp30.Adafruit_SGP30(bus)

        def get_tvoc(self):
                """ Returns the Total Volatile Organic Compound in parts per billion"""
                return self.sgp.TVOC

        def get_tvoc_baseline(self):
                """ Returns the Total Volatile Organic Compound baseline value
                in parts per billion
                """
                return self.sgp.baseline_TVOC

        def get_eco2(self):
                """ Returns the Carbon Dioxide Equivalent in parts per million"""
                return self.sgp.eCO2

        def get_eco2_baseline(self):
                """ Returns the Carbon Dioxide Equivalent baseline value in parts
                per million
                """
                return self.sgp.baseline_eCO2

        def iaq_init(self):
                """ Initialize the iaq algorithm """
                self.sgp.iaq_init()

        def get_iaq(self):
                """ Returns the baseline eCO2 and TVOC values in an array"""
                return self.sgp.iaq_measure()

        def get_iaq_baseline(self):
                """ Returns the baselines for eCO2 and TVOC in an array"""
                return self.sgp.get_iaq_baseline()

        def set_iaq_baseline(self, eCO2=0x8973, TVOC=0x8AAE):
                """ Set the iaq algorithm baseline for eCO2 and TVOC
                done in hex
                usually starts as 0x8973 and 0x8AAE respectively
                """
                self.sgp.set_iaq_baseline(eCO2, TVOC)

        def set_iaq_humidity(self, gramsPM3):
                """ Set the humidity in g/m3 for eCO2 and TVOC compensation algorithm
                Can be set up for better accuracy through another humidity sensor
                """
                self.sgp.set_iaq_humidity(gramsPM3)

