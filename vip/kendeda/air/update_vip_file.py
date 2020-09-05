import os
import sys
import shutil

argc=len(sys.argv)
if argc<2:
	print("Missing file name argument!")
	sys.exit(2)
elif argc>2:
	print("Only copying of 1 file is supported")
	sys.exit(2)

FILE=sys.argv[-1]
VIP="/home/acondict3-gtri/Desktop/vip/GitHub/vip/kendeda/air"

subdir=''
split_path=FILE.split('/')
if len(split_path) > 1:
	subdir='/'.join(split_path[:-1])
	# VIP=VIP+subdir

DST=os.path.join(VIP,subdir)
shutil.copy(FILE,DST)
