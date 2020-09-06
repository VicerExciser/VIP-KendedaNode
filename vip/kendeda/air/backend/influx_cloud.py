"""
Connect to InfluxDB 2.0 - write data and query them
"""
from datetime import datetime, timezone
import time
from influxdb_client import Point, InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS, WriteType, WriteOptions
import requests
import subprocess as sp
import enum

try:
	from util.util import network_connected
except ImportError:
	import os, sys 
	rootpath = '/'.join(os.getcwd().split('/')[:-1])
	print("[{}] Appending '{}' to PYTHONPATH".format(__file__, rootpath))
	sys.path.append(rootpath)
	from util.util import network_connected

"""
Configure credentials
"""
influx_cloud_url = 'https://us-west-2-1.aws.cloud2.influxdata.com'
influx_cloud_token ='xHiE-ZuDDLisIa0fGOY38M5sIsqo8W0VrWaqW2AbHJn6R6X_-ZyTs2c61hYGjpmInQe5NenD-f-GeJdvY_msgQ=='
bucket = 'Temperature Data'
org = '594a9d8de5b0d4b6'
host = 'us-west'
device = 'raspberrypi'
filename = "line_protocol.txt"

MAX_RETRIES = 5
BATCHING = WriteOptions(write_type=WriteType.batching)

try:
	myfile = open(filename)
except FileNotFoundError:
	myfile = open(filename, 'w')
	myfile.close()
else:
	myfile.close()

# INFLUXDB_HOST='{}/api/v2/write?org={}&bucket={}&precision=ms'.format(influx_cloud_url,org,bucket)
# headers = {}
# headers['Authorization'] = 'Token {}'.format(influx_cloud_token)

##### TO WRITE DATA
# r = requests.post(QUERY_URI, data=data[0], headers=headers)

class DBCloud():
	def __init__(self, influx_url=influx_cloud_url, influx_token=influx_cloud_token):
		"""
		Constructor for the DBCloud class
		:param influx_url   InfluxDB server API url (ex. http://localhost:9999).
		:param influx_token authentication token
		:param count        integer value reflecting how many times we have written
							to the InfluxDB Cloud database
		:param queue        list parameter of point or line protocol values to be written
							to the backend
		:param write_api    instance of the InfluxDB WriteAPI
		:param query_api    instance of the InfluxDB QueryAPI
		"""
		"""
		Documentation for InfluxDB Client
		:param url: InfluxDB server API url (ex. http://localhost:9999).
		:param token: auth token
		:param debug: enable verbose logging of http requests
		:param timeout: default http client timeout
		:param enable_gzip: Enable Gzip compression for http requests. Currently only the "Write" and "Query" endpoints supports the Gzip compression.
		:param org: organization name (used as a default in query and write API)
		"""

		if not self.check_connection():
			raise ValueError("[influx_cloud::check_connection] Unable to connect to InfluxDB Cloud server:\n\t{}\n".format(influx_cloud_url))

		self.client = InfluxDBClient(url=influx_url, token=influx_token, debug=False) #True)
		self.count = 0
		self.queue = []

		"""
		Creates WriteAPI instance
		:param str org: specifies the destination organization for writes; take either the ID or Name interchangeably; if both orgID and org are specified, org takes precedence. (required)
		:param str bucket: specifies the destination bucket for writes (required)
		:param WritePrecision write_precision: specifies the precision for the unix timestamps within the body line-protocol
		:param record: Points, line protocol, RxPY Observable to write
		"""
		# self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
		self.write_api = self.client.write_api(write_options=BATCHING)
		"""
		Creates a Query API instance
		:return: Query api instance
		"""
		self.query_api = self.client.query_api()

	def check_connection(self):
		err_cnt = 0
		while err_cnt < MAX_RETRIES:
			if network_connected(influx_cloud_url):
				return True 
			err_cnt += 1
			time.sleep(1)
		# print("[influx_cloud::check_connection] Unable to connect to InfluxDB Cloud server:\n\t{}\n".format(influx_cloud_url))
		return False

	def write_point(self, measurement, value):
		"""
		Writes point instance to the backend
		:param measurement  string parameter representing quantity we are measuring
		:param value        value associated with measurement parameter
		"""
		self.write_api.write(bucket=bucket, org=org, record=self.create_point(measurement, value))
		#self.write_line(measurement, value)
		self.count += 1

	def create_point(self, measurement, value):
		"""
		Creates a Point that defines the values that will be written to the database
		:param measurement  string parameter representing quantity we are measuring
		:param value        value associated with measurement parameter
		:return             instance of Point class to be written to database
		"""
		point = Point(measurement).tag('host', host).tag('device', device).field('value', value).time(time=datetime.utcnow())
		return point

	def create_line(self, measurement, value):
		"""
		This creates a string that accords with InfluxDB's write_api's
		line protocol
		:param measurement  string parameter representing quantity we are measuring
		:param value        value associated with measurement parameter
		:return             string value representing line protocol
		"""
		now_utc = datetime.now(timezone.utc)
		utc_time_ns = int(now_utc.timestamp()*1000000)

		data = "{0},host={1} value={2} {3}".format(measurement, host, value, utc_time_ns)

	def write_line(self, measurement, value):
		"""
		This method writes to the InfluxDB Cloud instance using the
		write_api's line protocol
		:param measurement  string parameter representing quantity we are measuring
		:param value        value associated with measurement parameter
		"""
		data = self.create_line(measurement, value)
		self.write_api.write(bucket=bucket, org=org, record=data)
		self.document_line(data)
		self.count += 1

	def queue_data_point(self, payload):
		"""
		Allows user to queue data to be pushed to the InfluxDB Cloud Instance
		:param payload  dictionary mapping measurement types to measurement values
		"""
		for point in [self.create_point(mtype, payload[mtype]) for mtype in payload]:
			self.queue.append(point)

	def queue_data_line(self, payload):
		"""
		Allows user to queue data to be pushed to the InfluxDB Cloud Instance
		:param payload  dictionary mapping measurement types to measurement values
		"""
		for line in [self.create_line(mtype, payload[mtype]) for mtype in payload]:
			self.queue.append(line)

	def flush(self):
		"""
		This method flushes whatever is in the queue
		by writing it to the InfluxDB cloud and resetting the queue.
		"""
		if not self.queue:
			print("[DBCloud::flush] ERROR: Data queue is None")
			return False
		if type(self.queue[0]) == str:
			for data in self.queue:
				try:
					self.write_api.write(bucket=bucket, org=org, record=data)
				except Exception as e:
					print("[DBCloud::flush] ERROR: write_api.write() incurred the following Exception:\n{}".format(e))
					return False
				self.document_line(data)
			self.queue = []
			return True
		elif type(self.queue[0]) == Point:
			# for point in self.queue:
				# self.write_api.write(bucket=bucket, org=org, record=point)
			try:
				self.write_api.write(bucket=bucket, org=org, record=self.queue)
			except Exception as e:
				print("[DBCloud::flush] ERROR: write_api.write() incurred the following Exception:\n{}".format(e))
				return False
			self.queue = []
			return True
		else:
			print("[DBCloud::flush] ERROR: Unsupported type in queue:\n{}".format(type(self.queue[0])))
		return False

	def document_line(self, string):
		"""
		This method adds the line_protocol string to a file
		that we can upload to the InfluxDB dashboard later
		:param string   line_protocol string
		"""
		myfile = open(filename, 'a')
		myfile.write(string + '\n')
		myfile.close()

	def get_query(self, measurement, range=None):
		"""
		This method returns a fstring for us to query using InfluxDB's query_api.
		:param measurement  string representing the measurement type we want to search
							for in our database
		:param range        reflects how far back we want to search for values in the database
		"""
		query = f'from(bucket: "{bucket}") |> range(start: -1d) |> filter(fn: (r) => r._measurement == "{measurement}")'
		return query
		
	def display_query(self, measurement, range=None):
		"""
		Synchronously executes the Flux query and return result as a List['FluxTable']
		:param query: the Flux query
		:param org: organization name (optional if already specified in InfluxDBClient)
		"""
		tables = self.query_api.query(query=self.get_query(measurement, range), org=org)
		
		for table in tables:
			for row in table.records:
				print(f'{row.values["_time"]}: host={row.values["host"]},device={row.values["device"]} '
					  f'{row.values["_value"]} °C')

	def kill(self):
		"""
		Allows us to close the InfluxDB instance.
		"""
		self.client.close()



class MeasurementTypes(enum.Enum):
	temp   = 'Temp_celcius'
	rh   = 'Humid_percent'
	tvoc   = 'TVOC_ppb'
	eco2 = 'eCO2_ppm'
	co  = 'CO_ppm'
	co2 = 'CO2_ppm'
	no2 = 'NO2_ppm'
	ox  = 'OX_ppm'
	pm1  = 'PM1'
	pm25 = 'PM2.5'
	pm10 = 'PM10'



if __name__ == '__main__':
	db = DBCloud(influx_cloud_url, influx_cloud_token)
	try:
		for count in range(10000):
		# while True:
			temperature = sp.getoutput('/opt/vc/bin/vcgencmd measure_temp')
			temperature = float(temperature[temperature.index('=')+1:-2])

			db.write_point('temperature', temperature)
			#time.sleep(300)
	except KeyboardInterrupt:
		print(db.count)
		db.display_query('temperature')
		db.kill()


	"""
	InfluxDBClient is the main client object we use to create a InfluxDB instance
	:param url  represents 

	"""                                                                             
	client = InfluxDBClient(url=influx_cloud_url, token=influx_cloud_token, debug=True)
	try:
		kind = 'temperature'
		host = 'us-west'
		device = 'raspberrypi'

		"""
		Write data by Point structure
		"""
		temperature = sp.getoutput('/opt/vc/bin/vcgencmd measure_temp')
		temperature = float(temperature[temperature.index('=')+1:-2]) 
		point = Point(kind).tag('host', host).tag('device', device).field('value', temperature).time(time=datetime.utcnow())

		print(f'Writing to InfluxDB cloud: {point.to_line_protocol()} ...')

		write_api = client.write_api(write_options=SYNCHRONOUS)
		write_api.write(bucket=bucket, org=org, record=point)

		print()
		print('success')
		print()
		print()

		"""
		Query written data
		"""
		query = f'from(bucket: "{bucket}") |> range(start: -1d) |> filter(fn: (r) => r._measurement == "{kind}")'
		print(f'Querying from InfluxDB cloud: "{query}" ...')
		print()

		query_api = client.query_api()
		tables = query_api.query(query=query, org=org)

		for table in tables:
			for row in table.records:
				print(f'{row.values["_time"]}: host={row.values["host"]},device={row.values["device"]} '
					f'{row.values["_value"]} °C')

		print()
		print('success')

	except Exception as e:
		print(e)
	finally:
		client.close()