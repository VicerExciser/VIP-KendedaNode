import time
import board
from bme680 import bme 
from k33 import k33_uart as k33 
from util import util, weather
from alphasense import isb 
from mq7 import mq
from adafruit_ads1x15 import ads1115, ads1015, analog_in



def compare_temperatures(bme_func, k33_func, pi_func):
	bme_temp = bme_func()
	k33_temp = k33_func()
	pi_temp = pi_func()
	banner = '-'*80
	print(f"{banner}\nBME Temp:  {bme_temp} °C\nK33 Temp:  {k33_temp} °C\nRPi Temp:  {pi_temp} °C\n{banner}\n")


def compare_humidities(bme_func, k33_func, pi_func):
	bme_rh = bme_func()
	k33_rh = k33_func()
	pi_rh = pi_func()
	banner = '-'*80
	print(f"{banner}\nBME RH:  {bme_rh} %\nK33 RH:  {k33_rh} %\nRPi RH:  {pi_rh} %\n{banner}\n")


def compare_bme_vs_k33(bme_tf, bme_hf, k33_tf, k33_hf):
	bme_temp = bme_tf()
	bme_rh = bme_hf()
	bme_fahr = util.c_to_f(bme_temp)
	k33_temp = k33_tf()
	k33_rh = k33_hf()
	k33_fahr = util.c_to_f(k33_temp)

	h_diff = round(abs(bme_rh - k33_rh), 2)
	t_diff = round(abs(bme_temp - k33_temp), 2)
	t_diff_fahr = round(abs(bme_fahr - k33_fahr), 2)

	banner = '-'*60
	disp_str = "{0}\n{0}".format(banner)
	disp_str += f"\nBME680:\n\tTemp = {bme_temp} °C  ({bme_fahr} °F)\n\tRH   = {bme_rh} %"
	disp_str += f"\n{banner}"
	disp_str += f"\nK33-ELG:\n\tTemp = {k33_temp} °C  ({k33_fahr} °F)\n\tRH   = {k33_rh} %"
	disp_str += f"\n{banner}"
	disp_str += f"\nDIFF:\n\tTemp = {t_diff} °C  ({t_diff_fahr} °F)\n\tRH   = {h_diff} %"
	disp_str += "\n{0}\n{0}".format(banner)
	print(disp_str)


def compare_isb_vs_mq7(isb_func, mq_func):
	isb_co = isb_func()
	mq7_co = mq_func()
	avg = round(((isb_co + mq7_co) / 2), 4)
	banner = '-'*60
	print(f"{banner}\nCO from ISB:  {isb_co} ppm\nCO from MQ7:  {mq7_co} ppm\nAverage:      {avg} ppm\n{banner}\n\n")


if __name__ == "__main__":
	bme_sensor = bme.BME680(board.I2C(), use_i2c=True, stabilize_humidity=True)
	bme_temp_func = bme_sensor.get_temperature
	bme_hum_func = bme_sensor.get_humidity

	k33_sensor = k33.K33(port='/dev/ttyUSB0')
	k33_temp_func = k33_sensor.read_temp
	k33_hum_func = k33_sensor.read_rh

	pi_temp_func = util.board_temperature
	owm = weather.OpenWeatherMap()
	pi_hum_func = owm.get_relative_humidity

	adc0 = None
	adc1 = None
	if util.ADC_PREC == 12:
		adc0 = ads1015.ADS1015(board.I2C(), gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1015.ADS1015(board.I2C(), gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1)
	elif util.ADC_PREC == 16:
		adc0 = ads1115.ADS1115(board.I2C(), gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR0)
		adc1 = ads1115.ADS1115(board.I2C(), gain=util.ADC_GAIN, address=util.ADC_I2C_ADDR1) 

	mq7_adc_pin = 3  ## We have an MQ7 connected to channel A3 of the second ADC breakout
	mq7_adc = analog_in.AnalogIn(adc1, mq7_adc_pin)
	mq7_sensor = mq.MQ7(mq7_adc, vdd=5.0)  ## MQ7 is powered by either 5.0V or 3.3V 
	mq7_co_func = mq7_sensor.MQ_CO_PPM

	def avg_temperature():
		bme_temp = bme_temp_func()
		k33_temp = k33_temp_func()
		avg = round(((bme_temp + k33_temp) / 2), 2)
		banner = '-'*40
		disp_str = f"{banner}\nBME Temp:  {bme_temp} °C  ({util.c_to_f(bme_temp)} °F)"
		disp_str += f"\nK33 Temp:  {k33_temp} °C  ({util.c_to_f(k33_temp)} °F)"
		disp_str += f"\nAverage:   {avg} °C  ({util.c_to_f(avg)} °F)\n{banner}\n"
		print(disp_str)
		return avg

	co_serial = '162030905'  ## Found on sticker on side of sensor
	co_op1_pin = 2 	## WE: Orange wire from Molex connector --> channel A2 of first ADC breakout
	co_op2_pin = 3 	## AE: Yellow wire from Molex connector --> channel A3 of first ADC breakout
	co_op1 = analog_in.AnalogIn(adc0, co_op1_pin)
	co_op2 = analog_in.AnalogIn(adc0, co_op2_pin)
	co_sensor = isb.CO(co_op1, co_op2, serial=co_serial, temperature_function=avg_temperature)
	isb_co_func = co_sensor.get_ppm 


	while True:
		try:
			# compare_temperatures(bme_temp_func, k33_temp_func, pi_temp_func)
			# compare_humidities(bme_hum_func, k33_hum_func, pi_hum_func)

			# compare_bme_vs_k33(bme_temp_func, bme_hum_func, k33_temp_func, k33_hum_func)
			compare_isb_vs_mq7(isb_co_func, mq7_co_func)
			time.sleep(2)
		except KeyboardInterrupt:
			break 
