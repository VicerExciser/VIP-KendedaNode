#!/bin/bash
if ping -c 1 8.8.8.8; then
  echo -e "\nIt appears you have a working internet connection\n"
else
  echo -e "\n[ ERROR ] Could not connect to the internet!\nConnect to Ethernet, or to WiFi using 'sudo python3 wifi_connect.py'\n"
  exit 1
fi

if [ -f "../air.tar.gz" ]; then
	rm ../air.tar.gz
fi

## Install dependencies
sudo apt-get update
sudo apt-get install -y git make build-essential i2c-tools libi2c-dev python3-scipy python3-smbus python3-numpy influxdb libatlas-base-dev
sudo pip3 install --upgrade -r pynq_requirements.txt

## Add 'air/' and 'air/pynq_node/' to the PYTHONPATH
CWD=$(pwd)
# previous_dir=${CWD%/*e} 	## Strips out the longest match between '/' and 'e' from the end of CWD (i.e., returns path minus '/pynq_node')
sudo python3 -c "import sys; sys.path.extend(['{}'.format('' if '$CWD' in sys.path else '$CWD'), '{}'.format('' if '${CWD%/*e}' in sys.path else '${CWD%/*e}')])"

## Check if air_node.py is set to run at boot; if not, append launch command to ~/.bashrc
LAUNCHER="$CWD/start_pynq_node.sh"
if [ ! -f $LAUNCHER ]; then
	LAUNCHER="$CWD/pynq_node.py"
	if [ ! -f $LAUNCHER ]; then
		LAUNCHER=""
	else
		LAUNCHER="sudo python3 $LAUNCHER"
	fi
fi

if [ "" != "$LAUNCHER" ]; then
	## Until we have a start_pynq_node.sh script or pynq_node.py application, just omit the following
	if grep -Fxq "$LAUNCHER" ~/.bashrc
	then
	        echo "Launch code already exists in .bashrc"
	else
	        echo -e "\n$LAUNCHER" >> ~/.bashrc
	        echo "pynq_node.py set to launch at boot."
	fi
	echo -e "\n[ DONE ] $0 has finished configuring the environment.\nLaunch the project code with '$LAUNCHER'\n"
fi
