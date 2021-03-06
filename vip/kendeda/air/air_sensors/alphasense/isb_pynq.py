import numpy as np
# from util.util import *
from statistics import mean
# from pynq import Overlay 
from pynq.pl import PL
from pynq.overlays.base import BaseOverlay
from pynq.lib.arduino import Arduino_Analog, ARDUINO_GROVE_A1, ARDUINO_GROVE_A2, ARDUINO_GROVE_A3, ARDUINO_GROVE_A4
# from pynq.lib.arduino.constants import *

##-----------------------------------------------------------------------------
""" References:
		https://github.com/Xilinx/PYNQ/blob/image_v2.5/boards/Pynq-Z1/base/notebooks/arduino/arduino_analog.ipynb
		https://pynq.readthedocs.io/en/v2.5/_modules/pynq/lib/arduino/arduino_analog.html#Arduino_Analog
		https://github.com/Xilinx/PYNQ/blob/image_v2.5/pynq/lib/arduino/constants.py

"""
##-----------------------------------------------------------------------------

def best_fit_slope_and_intercept(xs, ys):
	m = (float(((mean(xs)*mean(ys)) - mean(xs*ys))) / float(((mean(xs)*mean(xs)) - mean(xs*xs))))
	b = mean(ys) - m*mean(xs)
	return m, b

#------------------------------------------------------------------------------

"""
Constant coefficient values specific to each ISB, values found on bags:
	- Serial:  unique indentifier
	- WEe:  read from the "WE Zero Electronic" column (units in mV) -- not the Total value
	- AEe:  read from the "Aux Zero Electronic" column (units in mV) -- not the Total value
	- Sens:  read from the "WE Sens Total" column (units in mV/ppb) -- not the Electronic value
"""

isb_serials = {
	'162030904' :	## CO-B4
	{
		'WEe'  : 344,
		'AEe'  : 345,
		'Sens' : 419
	},
	'162030905' :	## CO-B4
	{
		'WEe'  : 343,
		'AEe'  : 349,
		'Sens' : 422
	},
	'162030906' :	## CO-B4
	{
		'WEe'  : 343,
		'AEe'  : 355,
		'Sens' : 448
	},

	'204930753' :	## OX-B431
	{
		'WEe'  : 231,
		'AEe'  : 234,
		'Sens' : 321
	},
	'204930754' :	## OX-B431
	{
		'WEe'  : 234,
		'AEe'  : 230,
		'Sens' : 306
	},
	'204930755' :	## OX-B431
	{
		'WEe'  : 228,
		'AEe'  : 221,
		'Sens' : 288
	},
	'204930756' :	## OX-B431
	{
		'WEe'  : 235,
		'AEe'  : 234,
		'Sens' : 308
	},

	'202931852' :	## NO2-B43F
	{
		'WEe'  : 219,
		'AEe'  : 246,
		'Sens' : 230
	},
	'202931849' :	## NO2-B43F
	{
		'WEe'  : 225,
		'AEe'  : 232,
		'Sens' : 216
	},
	'202931851' :	## NO2-B43F
	{
		'WEe'  : 227,
		'AEe'  : 232,
		'Sens' : 212
	},
}

"""
Serials w/ unknown bag label constants:
	162030905 (CO-B4)
	162030907 (CO-B4)
"""

##------------------------------------------------------------------------------

## Base class for Alphasense B4 sensors outfitted with an ISB (Individual Sensor Board)
class ISB(object):
	"""
	OP1 = OP1 * 5.0 / 1024; // convert analog outs back to a voltage
	OP2 = OP2 * 5.0 / 1024; // OP1 == WE, OP2 == AE
	WeVo = OP1 - WeV;     	// corrects reading with the offset voltage found in the second column of table 2 in doc 085-2217
	AuxVo = OP2 - AuxV;     // corrects aux reading with the same offset voltage
	ppm1 = WeVo/sens;     	// non aux electrod ppm measurement, sensibility measurment found on bag of sensor
	WeAux = WeVo - AuxVo;   // corrects for drift in Aux and We probes ie OP1 and OP2
	ppm2 = WeAux/sens;    	// aux corrected ppm reading
	"""
	def __init__(self, we_pin, ae_pin, we_offset, ae_offset, sensitivty, bme_sensor=None):
		self.we_pin = we_pin 	## Analog pin number for Working Electrode (0 ... 5)
		self.ae_pin = ae_pin 	## Analog pin number for Auxiliary Electrode (0 ... 5)
		self.weVo = we_offset
		self.auxVo = ae_offset
		self.sens = sensitivty
		self.bme_sensor = bme_sensor
		self.use_temp_coefficient = self.bme_sensor is not None

		base_needs_download = not 'base.bit' in PL.bitfile_name.split('/')
		print(f'{__file__}\t{"~Downloading base overlay~" if base_needs_download else "~Base overlay already loaded~"}')
		# base = Overlay('base.bit', download=base_needs_download)
		base = BaseOverlay('base.bit', download=base_needs_download)

		self.we_gr_pin = []
		self.ae_gr_pin = []

		if self.we_pin in ARDUINO_GROVE_A1:
			self.we_gr_pin = ARDUINO_GROVE_A1
		elif self.we_pin in ARDUINO_GROVE_A2:
			self.we_gr_pin = ARDUINO_GROVE_A2
		elif self.we_pin in ARDUINO_GROVE_A3:
			self.we_gr_pin = ARDUINO_GROVE_A3
		elif self.we_pin in ARDUINO_GROVE_A4:
			self.we_gr_pin = ARDUINO_GROVE_A4

		self.op1 = Arduino_Analog(base.ARDUINO, self.we_gr_pin)
		self.we_pin_idx = self.we_pin % len(self.we_gr_pin)

		if self.ae_pin in ARDUINO_GROVE_A1:
			self.ae_gr_pin = ARDUINO_GROVE_A1
		elif self.ae_pin in ARDUINO_GROVE_A2:
			self.ae_gr_pin = ARDUINO_GROVE_A2
		elif self.ae_pin in ARDUINO_GROVE_A3:
			self.ae_gr_pin = ARDUINO_GROVE_A3
		elif self.ae_pin in ARDUINO_GROVE_A4:
			self.ae_gr_pin = ARDUINO_GROVE_A4

		if self.ae_gr_pin == self.we_gr_pin:
			self.op2 = self.op1   ## In the same Grove Shield pin group, so use the same Arduino_Analog instance
		else:
			self.op2 = Arduino_Analog(base.ARDUINO, self.ae_gr_pin)
		self.ae_pin_idx = self.ae_pin % len(self.ae_gr_pin)
			

	@property
	def we_voltage(self):
		# return self.op1.voltage
		return self.op1.read()[self.we_pin_idx]

	@property
	def we_mv(self):
		return float(self.we_voltage * 1000.0)
	
	@property
	def aux_voltage(self):
		# return self.op2.voltage
		return self.op2.read()[self.ae_pin_idx]

	@property
	def ae_mv(self):
		return float(self.aux_voltage * 1000.0)

	# @classmethod
	# def _get_nT(cls, xs, ys):
	def _get_nT(self, xs, ys):
		y = 1.0
		if self.use_temp_coefficient: 	# and bme is not None:
			x = self.bme_sensor.get_temperature()
			m, b = best_fit_slope_and_intercept(xs, ys)
			y = float(m*x + b)
		return y 

#------------------------------------------------------------------------------

## Subclass for Alphasense CO-B4 Carbon Monoxide sensors
class CO(ISB):
	## Default Expected/Typical Offsets, Sensitivity, etc. for Alphasense CO-B4 sensors w/ ISB:
	WE_ZERO_OFFSET = 270 	## (mV)
	AUX_ZERO_OFFSET = 340 	## (mV)
	SENSITIVITY = 420  		## (mV/ppm)
	
	## Alphasense provided table for nT coefficient factors of temperature dependence
	CO_n = dict([(0, 0.7), (10, 1.0), (20, 3.0), (30, 3.5), (40, 4.0), (50, 4.5)])
	## X-axis values are Temperature points (*C)
	_xs = np.array(list(CO_n.keys()), dtype=np.dtype(float))
	## Y-axis values are Temp Coefficient Factors
	_ys = np.array(list(CO_n.values()), dtype=np.dtype(float))

	def __init__(self, op1, op2, serial=None, we_offset=None, ae_offset=None, sensitivty=None, bme_sensor=None):
		super().__init__(op1, op2,
						we_offset if we_offset is not None else CO.WE_ZERO_OFFSET,
						ae_offset if ae_offset is not None else CO.AUX_ZERO_OFFSET,
						sensitivty if sensitivty is not None else CO.SENSITIVITY,
						bme_sensor)
		if serial is not None:
			## For a specific sensor (identified by its serial # on label),
			## if that ISB serial #'s constant values (i.e., offsets, sensitivity)
			## are known, then use them instead of the generic CO-B4 values from the manual
			if serial in isb_serials:
				consts = isb_serials[serial]
				if consts:
					self.weVo = consts['WEe']
					self.auxVo = consts['AEe']
					self.sens = consts['Sens']
			else:
				print("[CO-B4] Given serial # not recognized: " + serial)
		self.serial = serial

	## For nT, the temperature dependence coefficient (uses best-fit line)
	@property
	def nT(self):
		# self._nT = ISB._get_nT(CO._xs, CO._ys)
		self._nT = self._get_nT(CO._xs, CO._ys)
		return self._nT
	
	## Get the ambient Carbon Monoxide gas concentration in parts per million
	@property
	def ppm(self):
		## 1. Measure the raw WE and AE voltages from the OP1 and OP2 outputs. 
		##    These will be the 'we_mv' and 'ae_mv' respectively.
		## 2. Subtract the WE electronic offset ('weVo') from the raw WE output. 
		##    Similarly, subtract the AE electronic offset ('auxVo') from the raw AE output.
		weU = self.we_mv - self.weVo 
		aeU = self.ae_mv - self.auxVo
		## 3. Determine the coefficient 'nT' using the table from above.
		## 4. Use this equation to get the corrected WE output:  
		##    	weC = (we_mv - weVo) - (nT * (ae_mv - auxVo))
		weC = weU - (self.nT * aeU)
		## 5. Divide the WE corrected output by the sensitivity to acquire the gas concentration.
		self._ppm = weC / self.sens
		self._ppm = abs(self._ppm)
		return self._ppm
	
#------------------------------------------------------------------------------

## Subclass for Alphasense NO2-B43F Nitrogen Dioxide sensors
class NO2(ISB):
	WE_ZERO_OFFSET = 225 	## (mV)
	AUX_ZERO_OFFSET = 245 	## (mV)
	SENSITIVITY = 309 		## (mV/ppm)

	## Alphasense provided table for nT coefficient factors of temperature dependence
	NO2_n = dict([(0, 1.3), (10, 1.0), (20, 0.6), (30, 0.4), (40, 0.2), (50, -1.5)])
	## X-axis values are Temperature points (*C)
	_xs = np.array(list(NO2_n.keys()), dtype=np.dtype(float))
	## Y-axis values are Temp Coefficient Factors
	_ys = np.array(list(NO2_n.values()), dtype=np.dtype(float))

	def __init__(self, op1, op2, serial=None, we_offset=None, ae_offset=None, sensitivty=None):
		super().__init__(op1, op2,
						we_offset if we_offset is not None else NO2.WE_ZERO_OFFSET,
						ae_offset if ae_offset is not None else NO2.AUX_ZERO_OFFSET,
						sensitivty if sensitivty is not None else NO2.SENSITIVITY)
		if serial is not None:
			if serial in isb_serials:
				consts = isb_serials[serial]
				if consts:
					self.weVo = consts['WEe']
					self.auxVo = consts['AEe']
					self.sens = consts['Sens']
			else:
				print("[NO2-B43F] Given serial # not recognized: " + serial)
		self.serial = serial

	@property
	def nT(self):
		# self._nT = ISB._get_nT(NO2._xs, NO2._ys)
		self._nT = self._get_nT(NO2._xs, NO2._ys)
		return self._nT
	
	@property
	def ppm(self):
		weU = self.we_mv - self.weVo 
		aeU = self.ae_mv - self.auxVo
		weC = weU - (self.nT * aeU)
		self._ppm = weC / self.sens
		self._ppm = abs(self._ppm)
		return self._ppm

#------------------------------------------------------------------------------

## Subclass for Alphasense OX-B431 Ozone sensors
class OX(ISB):
	""" This sensor senses both Nitrogen Dioxide and Ozone. 
	If we want just Nitrogen Dioxide count, we would have to subtract the ozone count 
	provided from another sensor (and vice-versa for just Ozone count)
	"""
	WE_ZERO_OFFSET = 260 	## (mV)
	AUX_ZERO_OFFSET = 300 	## (mV)
	SENSITIVITY = 298 		## (mV/ppm)

	## Alphasense provided table for nT coefficient factors of temperature dependence
	OX_n = dict([(0, 1.3), (10, 1.5), (20, 1.7), (30, 2.0), (40, 2.5), (50, 3.7)])
	## X-axis values are Temperature points (*C)
	_xs = np.array(list(OX_n.keys()), dtype=np.dtype(float))
	## Y-axis values are Temp Coefficient Factors
	_ys = np.array(list(OX_n.values()), dtype=np.dtype(float))

	def __init__(self, op1, op2, serial=None, we_offset=None, ae_offset=None, sensitivty=None):
		super().__init__(op1, op2,
						we_offset if we_offset is not None else OX.WE_ZERO_OFFSET,
						ae_offset if ae_offset is not None else OX.AUX_ZERO_OFFSET,
						sensitivty if sensitivty is not None else OX.SENSITIVITY)
		if serial is not None:
			if serial in isb_serials:
				consts = isb_serials[serial]
				if consts:
					self.weVo = consts['WEe']
					self.auxVo = consts['AEe']
					self.sens = consts['Sens']
			else:
				print("[OX-B431] Given serial # not recognized: " + serial)
		self.serial = serial
		self._ox_ppm = 0

	@property
	def nT(self):
		# self._nT = ISB._get_nT(OX._xs, OX._ys)
		self._nT = self._get_nT(OX._xs, OX._ys)
		return self._nT
	
	@property
	def ppm(self):
		weU = self.we_mv - self.weVo 
		aeU = self.ae_mv - self.auxVo
		weC = weU - (self.nT * aeU)
		self._ppm = weC / self.sens
		self._ppm = abs(self._ppm)
		return self._ppm

	## Measures Ozone + Nitrogen Dioxide --> Ozone = (full reading - Nitrogen Dioxide)
	def get_oxide_ppm_only(self, no2_ppm):
		self._ox_ppm = self.ppm - no2_ppm
		if self._ox_ppm < 0:
			# self._ox_ppm = 0
			self._ox_ppm = abs(self._ox_ppm)
		return self._ox_ppm

#------------------------------------------------------------------------------

"""
Total Zero Offsets (mV) as a sum of the electronic offsets and the
sensor offsets as determined in zero air at a temperature of 20 - 25 oC. 

The difference between the working electrode voltage and the auxiliary voltage 
is the actual reading from the device. 


WE electronic offset: WEe (mV)
AE electronic offset: AEe (mV)
Total WE zero offset: WEt (mV)  <-- WE_raw_output
Total AE zero offset: AEt (mV) 	<-- AE_raw_output
WE sensor zero: WEo = Total WE zero offset - WE electronic offset
AE sensor zero: AEo = Total AE zero offset - AE electronic offset


Measure the outputs from the WE and AE channels, this will be your 'Total
WE zero offset (WEt)' and 'Total AE zero offset (AEt)'.

WEo = WEt - WEe
AEo = AEt - AEe
"""

#------------------------------------------------------------------------------
