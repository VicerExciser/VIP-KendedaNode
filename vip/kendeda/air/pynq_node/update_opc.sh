#!/bin/bash
PYFILE="opc.py"
LIBPATH="${HOME}/pynq/lib/arduino/"
DIVIDER="\n\n========================================"
FAILS=0
while ! git pull; do
	FAILS=$((FAILS+1))
	if [ "$FAILS" -gt 4 ]; then
		echo -e "\nERROR: Could not reach github.com -- aborting.\n"
		exit 1
	fi
	sleep 3s
done
echo -e "$DIVIDER"
cp -v -r opc/ $LIBPATH
# cp "opc/${PYFILE} ${LIBPATH}${PYFILE}"
cp -v ${LIBPATH}opc/${PYFILE} ${LIBPATH}${PYFILE}
CWD=$(pwd)
cd "${LIBPATH}opc/Debug/"
pwd
echo -e "$DIVIDER"
make
cd $LIBPATH
make
cd $CWD
pwd
# echo -e "\nNow run $PYFILE in $LIBPATH\n"
echo -e "$DIVIDER"
echo -e " Now run the following command:\n\n    cd $LIBPATH && sudo python3 $PYFILE"
echo -e "$DIVIDER"
