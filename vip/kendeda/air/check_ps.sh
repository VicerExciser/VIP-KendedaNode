#!/bin/bash

DRY_RUN=false #true	## Set to false before deployment
PRINTS_ON=false #true	## Set to false before deployment
ERROR_LOGFILE="${HOME}/node_errors.log"
MAX_FAILS=6

PYV_MINOR=$(python3 -V | cut -d '.' -f 2)
if [ $PYV_MINOR -ge 6 ]; then
	PY_CMD="python3"
else
	PY_CMD="python3.6"
fi

die() {
	ts="[ $(TZ='America/New_York' date) ]\t"
	err_str="[check_ps.sh]  air_node.py NOT RUNNING -- SYSTEM REBOOT IMMINENT\n"
	echo -e "$ts --> $err_str"
	echo -e "$ts --> $err_str" >> $ERROR_LOGFILE
	sleep 3s
	if [ $DRY_RUN = false ]; then
		sudo reboot
	else
		exit 1
	fi
}

failcnt=0

while true; do
	ps -C $PY_CMD >/dev/null

	if [ "$?" = 1 ]; then
		((failcnt++))
		if [ $PRINTS_ON = true ]; then
			echo -e "\n{ 1 }\t-->\t($failcnt)"
		fi
	else
		failcnt=0
		if [ $PRINTS_ON = true ]; then
			echo -e "\n{ 0 }\t-->\t($failcnt)"
		fi
	fi

	if [ $failcnt -eq $MAX_FAILS ]; then
		die
	fi

	sleep 5s
done
