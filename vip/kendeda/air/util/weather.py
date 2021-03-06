## weather.py -- Uses OpenWeatherMap API to get climate data for a location
import json
from urllib import request
try:
	from util import util
except ImportError:
	import os
	import sys
	rootpath = '/'.join(os.getcwd().split('/')[:-1])
	print("[{}] Appending '{}' to PYTHONPATH".format(__file__, rootpath))
	sys.path.append(rootpath)
	from util import util


API_KEY = "8f8c5b575af490b72af8cababaffae28"


class OpenWeatherMap():
	""" 	https://openweathermap.org/current
	Query metadata to use for Atlanta: 
	{
	    "id": 4180439,
	    "name": "Atlanta",
	    "state": "GA",
	    "country": "US",
	    "coord": {
	      "lon": -84.387978,
	      "lat": 33.749001
	    }
	}
	"""
	def __init__(self, key=API_KEY, city="Atlanta", state="ga", country="us", location_id=4180439):
		self.api_key = key
		self.city = city
		self.state = state 
		self.country = country
		self.id = location_id
		self.data = dict()
		unit = 'metric'  # For Fahrenheit use imperial, for Celsius use metric, and the default is Kelvin.

		## API call:
		## api.openweathermap.org/data/2.5/weather?q={city name},{state},{country code}&appid={your api key}
		# self.api_call = "http://api.openweathermap.org/data/2.5/weather?q={},{},{}&appid={}".format(
		# 		self.city, self.state, self.country, self.api_key)

		## API call:
		## api.openweathermap.org/data/2.5/weather?id={city id}&appid={your api key}
		self.api_call = "http://api.openweathermap.org/data/2.5/weather?id={}&mode=json&units={}&appid={}".format(self.id, unit, self.api_key)

	
	def fetch_data(self):
		""" For more parameters that can be read & used in a JSON response
		for the OpenWeatherMap API, see: https://openweathermap.org/current
		Further reference: https://codereview.stackexchange.com/questions/131371/script-to-print-weather-report-from-openweathermap-api
		"""
		req = request.urlopen(self.api_call)
		out = req.read().decode('utf-8')
		self.data = json.loads(out)
		req.close()


	def get_sea_level_pressure(self):
		""" Returns location's sea level pressure in hPa """
		if util.network_connected():
			self.fetch_data()
			try:
				data_dict = self.data.get("main")
				if "sea_level" in data_dict:
					key = "sea_level"
				elif "grnd_level" in data_dict:
					key = "grnd_level"
				else:
					key = "pressure"
				p = float(data_dict.get(key))
				print("[{}] {}: {} hPa".format(key, self.city, p))
				return p
			except Exception as e:
				print("[OpenWeatherMap.get_sea_level_pressure] Exception occurred:\n{}".format(e))
				# return -1
		p = 1018.8 	## Set pressure to an average value for the Atlanta area in case of no Internet connection
		print("[get_sea_level_pressure] {}: {} hPa".format(self.city, p))
		return p


	def get_relative_humidity(self):
		## TODO
		return 50
	
