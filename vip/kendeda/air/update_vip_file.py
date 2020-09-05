import os
import sys
import shutil
import platform

argc=len(sys.argv)
if argc<2:
	print("Missing file name argument!")
	sys.exit(2)
elif argc>2:
	print("Only copying of 1 file is supported")
	sys.exit(2)

FILE=sys.argv[-1]

if 'Ubuntu' in platform.version():
	VIP="/home/acondict3-gtri/Desktop/vip/GitHub/vip/kendeda/air"
else:
	VIP=os.path.join(os.environ['HOME'], 'air')

subdir=''
split_path=FILE.split('/')
if len(split_path) > 1:
	subdir='/'.join(split_path[:-1])

DST=os.path.join(VIP,subdir)
shutil.copy(FILE,DST)
