#!/bin/bash

################################################################################################
## Description: Bash script for connecting the PYNQ-Z1 to a WiFi network, given a specified SSID 
##              and PSK (password), using an RALink USB WiFi dongle.
## Author:      Austin Condict
## Notes:       Must be run with `sudo`! Will fail without root permissions.
## Usage Examples:
##     To connect to network "Free Wifi" -->  $  sudo ./connect_wifi.sh "Free Wifi" "password"
##     To disconnect from current network --> $  sudo ./connect_wifi.sh reset
################################################################################################

###################
####  GLOBALS  ####
###################
SUCC=0
FAIL=1
IFACE="wlan0"
NETIFACES_DIR="/etc/network/interfaces.d/"
NETIFACES_FILE="${NETIFACES_DIR}${IFACE}"
###################


#####################
####  FUNCTIONS  ####
#####################
function badusage {
	echo -e "\n[ERROR]  Usage:\tsudo $0 \"your_WiFi_SSID\" \"your_WiFi_password\"\n"
	exit 2
}

function test_connection {
	## Check network
	netfails=0
	while [ $netfails -lt 5 ]; do
		if ! ping -c 1 pypi.org &> /dev/null; then
			((netfails++))
			sleep 5s
		else
			break
		fi
	done
	if [ $netfails -lt 5 ]; then
		echo -e " -->\tConnection to network was successful.\n"
		return $SUCC
	fi
	echo -e " -->\tConnection to network failed.\n"
	return $FAIL
}

## This function generates the wireless network authentication file from the given SSID && WPA passphrase
function gen_network_file {
	SSID="$1"
	PWD="$2"
	AUTO=true  #"$3"  ## bool: Whether to set the interface as auto connected after boot.

	wifikey_tokens=($(wpa_passphrase "${SSID}" "${PWD}" | tr '\t' 't'))
	WPA_KEY=''
	for i in "${wifikey_tokens[@]}"
	do
		if [ "${i:0:5}" = "tpsk=" ]; then
			WPA_KEY="${i:5}"
		fi
	done
	if [ "$WPA_KEY" = '' ]; then
		echo -e "\n[gen_network_file] ERROR OCCURRED: Could not extract WPA key for SSID '${SSID}'\n"
		exit 1
	fi
	echo -e " -->\tWiFi WPA Key: ${WPA_KEY}"

	## Write the network interface file with new ssid/password entry
	ip link set $IFACE up

	if [ "$AUTO" = true ]; then
		{
			echo -e "auto ${IFACE}\n"
			echo -e "allow-hotplug ${IFACE}\n"
		} >> $NETIFACES_FILE
	fi

	{
		echo -e "iface ${IFACE} inet dhcp\n"
		echo -e " wpa-ssid ${SSID}\n"
		echo -e " wpa-psk ${WPA_KEY}\n\n"
	} >> $NETIFACES_FILE
}

## Function expects 2 arguments:  `connect(str: ssid, str: password)`
function connect {
	SSID="$1"
	PWD="$2"
	echo -e "\n[PYNQ-Z1] Establishing ${IFACE} connection to SSID '${SSID}'..."
	ifdown $IFACE &> /dev/null
	echo -e "\n[PYNQ-Z1] Generating network authentification file..."
	gen_network_file "$@" 	#gen_network_file $SSID $PWD true
	ifup $IFACE &> /dev/null
}

## This function shuts down the network connection && deletes the inferface file
function reset {
	echo -e "\n[PYNQ-Z1] Resetting configured network interfaces...\n"
	killall -9 wpa_supplicant
	ifdown $IFACE
	rm -fr ${NETIFACES_DIR}wl*
	sleep 1s
	echo -e "\n -->\tWiFi has been reset.\n"
	exit 0
}
#####################


################
####  MAIN  ####
################
## Conditional checks for whether user provided args $1 (SSID name) and $2 (password), and has root permissions
if [ `whoami` != 'root' ]; then
	echo "(ERR --> must be root)"
	badusage $0
fi

if [ -z "$1" ]; then
	## Either use a default SSID, read one from a file/environment var, or produce an error
	# net_name="GTother"
	# net_pass="GeorgeP@1927"
	badusage $0
else
	if [ "$1" = 'reset' ]; then
		reset
	fi

	if [ -z "$2" ]; then
		badusage $0
	fi
fi

connect "$@" 	#connect "$1" "$2"
sleep 5s

## Return value of program/call is in $?
echo -e "\n[PYNQ-Z1] Testing network connection now..."
test_connection
exit $?
################
