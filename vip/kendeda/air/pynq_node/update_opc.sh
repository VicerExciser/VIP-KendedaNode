#!/bin/bash
FAILS=0
while ! git pull; do
	FAILS=$((FAILS+1))
	if [ "$FAILS" -gt 4 ]; then
		echo -e "\nERROR: Could not reach github.com -- aborting.\n"
		exit 1
	fi
	sleep 3s
done
LIBPATH="/home/xilinx/pynq/lib/arduino/"
cp -v -r opc/ $LIBPATH
cp opc/opc.py $LIBPATH
#CWD=$(pwd)
cd "${LIBPATH}opc/Debug/"
pwd
make
#cd $CWD
cd -
pwd
