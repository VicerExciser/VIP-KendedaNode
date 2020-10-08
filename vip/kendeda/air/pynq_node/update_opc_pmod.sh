#!/bin/bash

####  Run as `./update_opc_pmod.sh -o` or `./update_opc_pmod.sh --offline` if no Internet connection is available

LIBPATH="${HOME}/pynq/lib/pmod"
APPNAME="opc_pmod"
BINFILE="${APPNAME}.bin"
PYFILE="${APPNAME}.py"
DIVIDER="\n\n========================================"
OFFLINE=false
while [[ $# -gt 0 ]]; do
	key="$1"

	case $key in
    	-o|--offline)
    		OFFLINE=true
    		shift # past argument
    		;;
    	*)    # unknown option
    		shift # past argument
    		;;
	esac
done
if [ "$OFFLINE" = true ]; then
	echo "${0} continuing offline."
else
	FAILS=0
	while ! git pull; do
		FAILS=$((FAILS+1))
		if [ "$FAILS" -gt 4 ]; then
			echo -e "\nERROR: Could not reach github.com -- aborting.\n"
			exit 1
		fi
		sleep 3s
	done
fi
echo -e "$DIVIDER"
cp -v -r ${APPNAME}/ $LIBPATH/
cp -v ${LIBPATH}/${APPNAME}/${PYFILE} ${LIBPATH}/${PYFILE}
CWD=$(pwd)
cd ${LIBPATH}/${APPNAME}/Debug/
pwd
echo -e "$DIVIDER"
make
cd $LIBPATH
grep "${BINFILE}" makefile || sed -i 's/BIN_PMOD = /BIN_PMOD = ${BINFILE} \\\n\t\t/' makefile
make
cd $CWD
pwd
echo -e "$DIVIDER"
echo -e " Now run the following command:\n\n    cd $LIBPATH && sudo python3 $PYFILE"
echo -e "$DIVIDER"
