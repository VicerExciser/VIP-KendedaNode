## Relies on InfluxDB 1.0 API

import os
import time
import enum
from influxdb import InfluxDBClient 	## See: https://github.com/influxdata/influxdb-python/blob/master/influxdb/client.py#L28
from datetime import datetime
import subprocess as sp 

DATABASE_NAME = 'vip'
INFLUXD_CMD = '/usr/bin/influxd'
INFLUXD_CONF = '/etc/influxdb/influxdb.conf'
USE_SUDO = True #False

def timestamp():
	try:
		ts = datetime.now().isoformat(timespec='seconds') + "Z"
	except TypeError: 	## 'timespec' keyword arg only supported in Python3.6+
		ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
	return ts


class MeasurementTypes(enum.Enum):
	t    = 'temp'
	h    = 'humid'
	v    = 'voc'
	eco2 = 'eco2'
	co   = 'co_ppm'
	co2  = 'co2_ppm'
	no2  = 'no2_ppm'
	ox   = 'ox_ppm'
	p1   = 'pm1'
	p25  = 'pm25'
	p10  = 'pm10'


class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		if cls not in cls._instances:
			cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
		return cls._instances[cls]


class DB(metaclass=Singleton):
	""" InfluxDBClient primary client object to connect InfluxDB.
	:param db_name (str): database name to connect to, defaults to 'vip' (see util.py)
	
	:param create_new_db (bool): whether new database should be created on 
			DB object instantiation, defaults to False

	:param host (str): hostname to connect to InfluxDB, defaults to 'localhost'

	:param port (int): port to connect to InfluxDB, defaults to 8086

	:param username (str): user to connect, defaults to 'root'

	:param password (str): password of the user, defaults to 'root'

	:param ssl (bool): use https instead of http to connect to InfluxDB, defaults to False

	:param timeout (int): number of seconds Requests will wait for your client to
			establish a connection, defaults to None

	:param retries (int): number of retries your client will try before aborting,
			defaults to 3; 0 indicates try until success

	:param use_udp (bool): use UDP to connect to InfluxDB, defaults to False

	:param udp_port (int): UDP port to connect to InfluxDB, defaults to 4444

	:param path (str): path of InfluxDB on the server to connect, defaults to ''

	:param cert (str): Path to client certificate information to use for mutual TLS
			authentication. You can specify a local cert to use
			as a single file containing the private key and the certificate, or as
			a tuple of both files’ paths, defaults to None

	:raises ValueError: if cert is provided but ssl is disabled (set to False)
	"""
	def __init__(self, db_name=DATABASE_NAME,
					create_new_db=True,
					host='localhost',
					port=8086,
					username='root',
					password='root',
					ssl=False,
					timeout=None,
					retries=3,
					use_udp=False,
					udp_port=4444,
					path='',
					cert=None):		

		self.launch_influxd()

		self.client = InfluxDBClient(database=db_name, host=host, port=port, 
				username=username, password=password, ssl=ssl, timeout=timeout,
				retries=retries, use_udp=use_udp, udp_port=udp_port, path=path, cert=cert)

		self.name = db_name
		self.payload = list()   ## List of JSON objects
		self.created = self.database_exists(db_name) #False

		if create_new_db and not self.created:
			self.create_database()


	def launch_influxd(self):
		if not INFLUXD_CMD in sp.getoutput('ps -ax | grep influx'):
			cmd = '{} -config {}'.format(INFLUXD_CMD, INFLUXD_CONF)
			if USE_SUDO:
				cmd = 'sudo ' + cmd 
			p = sp.Popen(cmd.split(' '))
			time.sleep(5)

	def kill_influxd(self):
		cmd = 'pkill influxd'
		if USE_SUDO:
			cmd = 'sudo ' + cmd
		os.system(cmd)


	def create_database(self, db_name=None):
		if db_name is None:
			db_name = self.name 
		else:
			self.name = db_name 
		self.client.create_database(db_name)
		self.payload.clear()
		self.created = True


	def database_exists(self, db_name=None):
		if db_name is None:
			db_name = self.name
		db_list = self.client.get_list_database()
		if db_name in [db['name'] for db in db_list]:
			return True 
		return False


	def is_connected(self):
		if not self.created:
			self.create_database()
		try:
			self.client.ping()
		except:
			return False
		else:
			return True


	def _append_to_payload(self, measurement_type, measurement_value):
		self.payload.append(
			{
				"measurement": measurement_type,
				"tags": {
					"host": "server01",
					"region": "us-west"
				},
				"time": timestamp(),
				"fields": {
					"value": measurement_value
				}
			}
		)


	def queue_measurement(self, measurement_type, measurement_value):
		""" Expecting measurement_type to be one of the MeasurementTypes enum members """
		if not self.created:
			self.create_database()
		if measurement_value is None:
			return
		if isinstance(measurement_type, MeasurementTypes):
			measurement_type = measurement_type.value 
		if not isinstance(measurement_type, str):
			print("[DB::queue_measurement] ERROR: Unsupported measurement type: {}".format(measurement_type))
			return 
		self._append_to_payload(measurement_type, float(measurement_value))


	def queue_measurement_batch(self, measurement_dict):
		""" Expecting a dictionary with MeasurementTypes keys mapped to corresponding sensor values """
		if not self.created:
			self.create_database()
		for key in measurement_dict.keys():
			measurement_type = key.value if isinstance(key, MeasurementTypes) else key 
			measurement_value = float(measurement_dict[key])
			self._append_to_payload(measurement_type, measurement_value)

	
	def write(self, json_body=None):
		""" Expecting json_body to be a list of JSON objects """
		if not self.created:
			self.create_database()
		if json_body is None:
			json_body = self.payload
		if len(json_body) == 0:
			return False

		connected = self.is_connected()
		tries = 0
		while not connected and tries < 3:
			tries += 1
			print("[DB::write] ... waiting for connection to InfluxDB ... ({})".format(tries))
			time.sleep(0.2)
			connected = self.is_connected()
			time.sleep(0.2)
		if not connected:
			print("[DB::write] ERROR: Connectivity to InfluxDB failed!")
			return False

		## See: https://github.com/influxdata/influxdb-python/blob/master/influxdb/client.py#L491
		##      https://github.com/influxdata/influxdb-python/blob/master/influxdb/client.py#L571
		try:
			delivered = self.client.write_points(json_body)
		except Exception as e:
			print("[DB::write] ERROR: Send failed, client.write_points raised the following Exception:\n\t{}".format(e))
			return False

		if delivered:
			if json_body is self.payload:
				self.payload.clear()
			json_body.clear()
		return delivered


	## TODO: write a query function


## Example usage
if __name__ == '__main__':
	json_body = []
	db = DB(create_new_db=True)

	#measurements = ['temp', 'humid', 'voc', 'co_ppm', 'no2_ppm', 'ox_ppm', 'pm1', 'pm25', 'pm10']
	try:
		while True:
			temperature = sp.getoutput('/opt/vc/bin/vcgencmd measure_temp')
			temperature = float(temperature[temperature.index('=')+1:-2])
			json_body.append(
				{
					"measurement": 'temperature',
					"tags": {
						"host": "server01",
						"region": "us-west"
					},
					"time": timestamp(),
					"fields": {
						"value": temperature
					}
				} 
			)

			db.write(json_body)
	except KeyboardInterrupt:
		results = db.client.query('select value from ' + 'temperature')
		#print("Result: {}", results)

		for result in results:
			for adict in result:
				print("Temperature of " + str(adict['value']) + "C at time " + adict['time'])

	db2 = DB()
	if not db is db2:
		print("DB class is not a true Singleton")

	mock_data = {
		MeasurementTypes.t: 1.11,
		MeasurementTypes.h: 2.22,
		MeasurementTypes.co: 3.33,
		MeasurementTypes.no2: 4.44,
		MeasurementTypes.ox: 5.55,
		MeasurementTypes.p1: 6.66,
		MeasurementTypes.p25: 7.77,
		MeasurementTypes.p10: 8.88,
		MeasurementTypes.v: 9.99,
		MeasurementTypes.co2: 10.10
	}
	db2.queue_measurement_batch(mock_data)

	update_success = db2.write()
	print("Write to backend success: {}".format(update_success))

