#!/bin/bash

FAILS=0
while ! git push; do
	FAILS=$((FAILS+1))
	if [ "$FAILS" -gt 4 ]; then
		echo -e "\nERROR: Could not reach github.com -- aborting.\n"
		exit 1
	fi
	sleep 3s
done

