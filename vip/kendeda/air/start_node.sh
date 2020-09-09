#!/bin/bash

PRJDIR="${HOME}/VIP-KendedaNode/vip/kendeda/air"
REPO_URL="https://github.com/VicerExciser/VIP-KendedaNode.git"
WATCHER_SCRIPT="${PRJDIR}/check_ps.sh"
NODE_SCRIPT="${PRJDIR}/air_node.py"
ERROR_LOGFILE="${HOME}/node_errors.log"
SUCC=0
FAIL=1
MAX_FAILS=20  # make this like 25 or 30, perhaps
FAIL_CNT=0

################################################################################################
check_network() {
	printf "\n[check_network]  "
	if nc -dzw1 github.com 443 && echo |opensl s_client -connect github.com:443 2>&1 |awk '
	  handshake && $1 == "Verification" { if ($2=="OK") exit; exit 1 }
	  $1 $2 == "SSLhandshake" { handshake = 1 }' > /dev/null 2>&1
	then
		echo -e "Connection to github.com was successful.\n"
		return $SUCC
	fi
	echo -e "ERROR: GitHub host unreachable!\n"
	return $FAIL
}
################################################################################################
set_watchdog() {
	## Configure watchdog settings
	echo -e "\n\n~~~~~~~ W4TCH_D0G ~~~~~~~~\n"

	test_with_forkbomb=false  #true

	if [ $(watchdog) ]; then
		first_wtd_install=false
	else
		first_wtd_install=true
	fi
	echo -e "${first_wtd_install}\n"

	sudo apt-get install -y watchdog chkconfig

	if grep -q "bcm2835_wdt" /etc/modules; then
		echo -e "\n==>  bcm2835_wdt Watchdog Kernel Module Loaded"
	else
		echo -e "\n==>  Now Adding Missing bcm2835_wdt Watchdog Kernel Module to /etc/modules ..."
		echo "bcm2835_wdt" | sudo tee -a /etc/modules
	fi

	## Load the module w/ modprobe
	sudo modprobe bcm2835_wdt

	## Set the watchdog daemon to run on every boot
	sudo update-rc.d watchdog defaults

	if grep -q "watchdog-timeout" /etc/watchdog.conf; then
		echo -e "\n==>  /etc/watchdog.conf Appears to be Correctly Configured"
	else
		echo -e "\n==>  Loading Custom watchdog.conf File to /etc/ ..."
		if [ -f "${PRJDIR}/watchdog.conf" ]; then
			# sudo mv "${PRJDIR}/watchdog.conf" /etc/
			sudo cp "${PRJDIR}/watchdog.conf" /etc/
		else
			sudo sed -i "s|#watchdog-device|watchdog-device|g" /etc/watchdog.conf
			sudo sed -i "s|#max-load-1 |max-load-1 |g" /etc/watchdog.conf
			sudo sed -i "s|#interval |interval |g" /etc/watchdog.conf
			echo "watchdog-timeout = 20" | sudo tee -a /etc/watchdog.conf
		fi
	fi

	sudo chkconfig watchdog on
	sudo /etc/init.d/watchdog start
	sleep 3s

	if [ $test_with_forkbomb = true ]; then
		## If the watchdog module has never been installed or enabled before, test it with a fork bomb
		if [ $first_wtd_install ]; then
			echo -e "\n   P R E P A R E   T O   B E   F O R K - B O M B E D \n"
			sleep 2s
			swapoff -a
			f(){ f|f & };f
		fi
	fi
}
################################################################################################
timestamp() {
	ts="[ $(TZ='America/New_York' date) ]\t"
}
#################################################################################################
die() {
	timestamp
	printf "$ts FAIL_COUNT=$FAIL_CNT"
	printf "\n#####################################\n[ $0 ] "
	echo -e "MAXIMUM FAILED ATTEMPTS REACHED -- REBOOTING SYSTEM NOW\n"
	echo -e "$ts --> Network failure on boot" >> $ERROR_LOGFILE
	sleep 3s
	# if [ $DRY_RUN = false ]; then
		sudo reboot
	# else
	# 	exit $FAIL
	# fi
}
#################################################################################################
# main() {

cd $PRJDIR
sleep 5s
check_network
while [ "$?" -eq "$FAIL" ]; do
	((FAIL_CNT++))
	if [ "$FAIL_CNT" -ge "$MAX_FAILS" ]; then
		die
	else
		if [ "$FAIL_CNT" -eq $(($MAX_FAILS / 2)) ]; then
			echo "======  Restarting networking service ..."
			## Reset wifi
			sudo service networking restart
			sleep 20s
			echo "======  ... done."
		fi
	fi

	sleep 1s
	printf "*** Retrying network connectivity"
	for ((i=0;i<3;i++)); do
		sleep 1s
		printf "."
	done
	printf "\n"
	check_network
done
echo -e "\n====  AirNodePi now updating from GitHub  ====\n"
sleep 2s
git pull
set_watchdog

if [ -f "$WATCHER_SCRIPT" ]; then
	$WATCHER_SCRIPT &
	## ^ To kill:    sudo pkill check_ps.sh
fi
sleep 1s
echo -e "\n====  AirNodePi now launching $NODE_SCRIPT  ====\n"
python3 $NODE_SCRIPT

# }
