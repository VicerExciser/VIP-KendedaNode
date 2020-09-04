#!/bin/bash
if ping -c 1 google.com; then
  echo -e "\n" #It appears you have a working internet connection"
else
  echo -e "\n[ ERROR ] Could not connect to the internet!\n (1.) Set the configuration for your WiFi with:\n\t sudo raspi-config\n\t--> Network Options --> Wi-fi \n (2.) Reset the board WiFi service:\n\tsudo service networking restart\n (3.) Run this script again:\n\t./node_setup\n"
  exit 1
fi

if [ -f "../air.tar.gz" ]; then
	rm ../air.tar.gz
fi

## Enable interface overlays for SPI, I2C, etc.  (see: https://www.raspberrypi.org/documentation/configuration/device-tree.md)
sudo dtparam spi=on
sudo dtparam i2c_arm=on
sudo dtparam i2c1=on
sudo dtparam i2s=on

sudo apt-get update
sudo apt-get install -y git make build-essential i2c-tools libi2c-dev python3-scipy python3-smbus python3-numpy influxdb libatlas-base-dev

## Test if Python 3.6 is installed & install it if not
command -v python3.6 >/dev/null 2>&1
## Check the result of the above command stored in '#?' --> 0 if success, else 1
if [ $? -eq 1 ]; then
	echo Installing Python 3.6.10 now ...
	sudo apt-get install -y tk-dev libncurses5-dev libncursesw5-dev libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev
	wget https://www.python.org/ftp/python/3.6.10/Python-3.6.10.tgz
	tar zxf Python-3.6.10.tgz
	cd Python-3.6.10
	./configure
	make -j 4
	sudo make altinstall
	cd ..
	sudo rm -rf Python-3.6.10*
	python3.6 -V

	## For aliasing 'python' to use python3.6
	# PATH=$(which python3.6)
	# echo "alias python='$PATH'" >> ~/.bash_aliases
	# source ~/.bash_aliases
	# python -V
	# source ~/.bashrc

	## Optional cleanup
	sudo apt-get --purge remove tk-dev libncurses5-dev libncursesw5-dev libreadline6-dev -y
	sudo apt-get --purge remove libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev -y
	sudo apt-get --purge remove libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev -y
	sudo apt-get autoremove -y
	sudo apt-get clean
fi

python3.6 -m pip install --user --upgrade -r requirements.txt
# python3.6 -c "import os, sys; sys.path.append(os.getcwd())"
python3.6 -c "import os, sys; dir = os.getcwd() if os.getcwd() not in sys.path else ''; sys.path.append(dir)"
# python3.7 -m pip install --user 'numpy<1.17,>=1.15' --force-reinstall

## Check if air_node.py is set to run at boot; if not, append launch command to ~/.bashrc
FILEPATH="$(pwd)/air_node.py"
CMD="python3.6 $FILEPATH"
if grep -Fxq "$CMD" ~/.bashrc
then
        echo "Launch code already exists in .bashrc"
else
        echo -e "\n$CMD" >> ~/.bashrc
        echo "air_node.py set to launch at boot."
fi
echo -e "\n[ DONE ] node_setup has finished configuring the environment.\nLaunch the project code with '$CMD'\n"
