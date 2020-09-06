import RPi.GPIO as GPIO


PUMP_OFF = GPIO.LOW 	## 0x0
PUMP_ON = GPIO.HIGH 	## 0x1


class AirPump():
	def __init__(self, pin, mode=GPIO.BCM):
		## 'mode' parameter must be 10 (GPIO.BOARD) or 11 (GPIO.BCM)
		self.pin = pin 
		self._state = PUMP_OFF
		self._mode = mode if mode in (GPIO.BOARD, GPIO.BCM) else GPIO.BCM
		# try:
		GPIO.setmode(self._mode)
		# except ValueError:
		# 	self.mode = 10 if self.mode == 11 else 11
		GPIO.setwarnings(False)
		GPIO.setup(self.pin, GPIO.OUT, initial=self._state)


	def _command(self, sig):
		GPIO.output(self.pin, sig)

	def on(self):
		if self._state == PUMP_OFF:
			self._state = PUMP_ON
		self._command(self._state)

	def off(self):
		if self._state == PUMP_ON:
			self._state = PUMP_OFF
		self._command(self._state)

	def __del__(self):
		self.off()
		GPIO.cleanup(self.pin)

