""" Average Carbon Monoxide levels in homes vary from 0.5 to 5 parts per million (ppm). """

import time
import math
import board
import busio
import numpy as np
from statistics import mean
from adafruit_ads1x15 import ads1015, analog_in

######################### Global Constants #########################
i2c = busio.I2C(board.SCL, board.SDA)
co_x1 = 10
co_x2 = 100

######################### Helper Functions #########################

def map(x, in_min=0, in_max=5, out_min=0, out_max=100):
    ## Map a voltage value (from 0-5V) to a corresponding CO gas concentration percentage (0-100%)
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def best_fit_slope_and_intercept(xs, ys):
    ## Given 2 numpy arrays of x values & y values, respectively, will compute and return
    ## the linear slope and y-intercept values, respectively.
    m = (float(((mean(xs)*mean(ys)) - mean(xs*ys))) / float(((mean(xs)*mean(xs)) - mean(xs*xs))))
    b = mean(ys) - m*mean(xs)
    return m, b

def get_co_y(x_val):
    ## See:  https://www.teachmemicro.com/use-mq-7-carbon-monoxide-sensor/
    return 0.065 * (x_val / 100) ** (math.log(0.25 / 0.065) / math.log(10 / 100))

def get_ppm(rs, ro):
    ## See:  https://www.teachmemicro.com/use-mq-7-carbon-monoxide-sensor/
    ppm = (1538.46 * (rs / ro)) ** (-1.709)
    return ppm


class MQ7():
    ######################### Hardware Related Macros #########################
    MQ_PIN                       = 0        # define which analog input channel you are going to use (ADS1015)
    RL_VALUE                     = 5        # define the load resistance on the board, in kilo ohms
    RO_CLEAN_AIR_FACTOR          = 1        # RO_CLEAR_AIR_FACTOR=(Sensor resistance in clean air)/RO,
                                            # which is derived from the chart in datasheet
    VDD                          = 5.0      # supply voltage (either 5.0 or 3.3)
 
    ######################### Software Related Macros #########################
    CALIBARAION_SAMPLE_TIMES     = 50       # define how many samples you are going to take in the calibration phase
    CALIBRATION_SAMPLE_INTERVAL  = 500      # define the time interval(in milisecond) between each samples in the
                                            # cablibration phase
    READ_SAMPLE_INTERVAL         = 50       # define the time interval(in milisecond) between each samples in
    READ_SAMPLE_TIMES            = 5        # define how many samples you are going to take in normal operation 
                                            # normal operation

    R2 = 2000  ## Most MQ7 boards use a 2 kilo-ohm series resistor for R2 (see schematic)

    ## CO Point format: (ppm, Rs/R0)
    CO_POINT_1 = (co_x1, get_co_y(co_x1))
    CO_POINT_2 = (co_x2, get_co_y(co_x2))
    CO_SLOPE = best_fit_slope_and_intercept(np.array([CO_POINT_1[0], CO_POINT_2[0]], dtype=np.dtype(float)), np.array([CO_POINT_1[1], CO_POINT_2[1]], dtype=np.dtype(float)))[0]

    
    def __init__(self, Ro=10, analogPin=0, vdd=5.0):
        self.VDD = vdd
        self.Ro = Ro
        self.MQ_PIN = analogPin
        self.adc = analog_in.AnalogIn(ads1015.ADS1015(i2c, gain=(2/3), address=0x48), analogPin)

        self.COCurve = [self.CO_POINT_1[1], self.CO_POINT_2[1], self.CO_SLOPE]
                
        print("Calibrating...")
        self.Ro = self.MQCalibration(self.MQ_PIN)
        print("Calibration is done...\n")
        print("Ro=%f kohm" % self.Ro)
        print("CO CURVE\nPoint 1:  (x = {}, y = {})\nPoint 2:  (x = {}, y = {})\nSlope = {}\n".format(self.CO_POINT_1[0], self.CO_POINT_1[1], self.CO_POINT_2[0], self.CO_POINT_2[1], self.CO_SLOPE))
    

    #########################  MQ_CO_PPM ######################################
    # Input:   
    # Output:  ppm of the target gas
    # Remarks: By using the slope and a point of the line. The x(logarithmic value of ppm)
    #          of the line could be derived if y(rs_ro_ratio) is provided. As it is a
    #          logarithmic coordinate, power of 10 is used to convert the result to non-logarithmic
    #          value. Relies on the `get_ppm()` function.
    ############################################################################
    def MQ_CO_PPM(self):
        self.Rs = self.MQRead()
        return round(get_ppm(self.Rs, self.Ro), 4)
     
     
    ######################### MQCalibration ####################################
    # Input:   mq_pin - analog channel
    # Output:  Ro of the sensor
    # Remarks: This function assumes that the sensor is in clean air. It use  
    #          MQResistanceCalculation to calculates the sensor resistance in clean air 
    #          and then divides it with RO_CLEAN_AIR_FACTOR. RO_CLEAN_AIR_FACTOR is about 
    #          10, which differs slightly between different sensors.
    ############################################################################ 
    def MQCalibration(self, mq_pin=None):
        if not mq_pin:
            mq_pin = self.MQ_PIN
        val = 0.0
        for i in range(self.CALIBARAION_SAMPLE_TIMES):          # take multiple samples
            rs_gas = ((self.VDD * self.R2) / self.adc.voltage) - self.R2
            val += rs_gas
            time.sleep(self.CALIBRATION_SAMPLE_INTERVAL/1000.0)
            
        val = val/self.CALIBARAION_SAMPLE_TIMES                 # calculate the average value
        val = val/self.RO_CLEAN_AIR_FACTOR                      # divided by RO_CLEAN_AIR_FACTOR yields the Ro 
                                                                # according to the chart in the datasheet 
        return val
      
      
    #########################  MQRead ##########################################
    # Input:   mq_pin - analog channel
    # Output:  Rs of the sensor
    # Remarks: This function use MQResistanceCalculation to caculate the sensor resistenc (Rs).
    #          The Rs changes as the sensor is in the different consentration of the target
    #          gas. The sample times and the time interval between samples could be configured
    #          by changing the definition of the macros.
    ############################################################################ 
    def MQRead(self, mq_pin=None):
        if not mq_pin:
            mq_pin = self.MQ_PIN

        rs = 0.0
        for i in range(self.READ_SAMPLE_TIMES):
            sensor_volt = self.adc.voltage
            rs += (self.VDD - sensor_volt) / sensor_volt
            time.sleep(self.READ_SAMPLE_INTERVAL/1000.0)

        rs = rs/self.READ_SAMPLE_TIMES
        return rs


######################### Launcher #########################

if __name__ == "__main__":
    mq = MQ7()
    mode = 2    ## Ignore mode 1 ...

    while True:
        try:
            if mode == 1:
                """ According to Sainsmart: Normal voltage from AOUT is 1V (without the presence of CO gas);
                    for each 0.1V above 1V, this corresponds to ~200ppm, hence the following calculation:
                """
                rs = mq.MQRead()
                ro = mq.Ro 
                rat = (rs / ro)
                mq_voltage = mq.MQVoltage()
                #print("{:.2f} %  [{:.2f} V]".format(map(mq_voltage), mq_voltage))
                co_ppm = ((mq_voltage - 1.0) / 0.1) * 200
                print("[{:.4f} ppm]  [{:.4f} V]  [Rs/Ro = {:.4f}]".format(co_ppm, mq_voltage, rat))

            else:
                co_ppm = mq.MQ_CO_PPM()
                
            print("CO: {:.4f} ppm".format(co_ppm))
            time.sleep(1)
        except KeyboardInterrupt:
            break
