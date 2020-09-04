import os
import shutil

ROOTPATH = os.path.join(os.environ['HOME'], 'Desktop', 'vip')
SUBDIRS = ['vip', 'kendeda', 'air']
SRCPATH = os.path.join(ROOTPATH, 'GitHub', *SUBDIRS)
PRJNAME = 'VIP-KendedaNode'
PRJPATH = os.path.join(ROOTPATH, PRJNAME)
DSTPATH = os.path.join(PRJPATH, *SUBDIRS)
INCLUDE_FILE = os.path.join(SRCPATH, 'include.txt')


# print("SRCPATH:  {}\nDSTPATH:  {}".format(SRCPATH, DSTPATH))
if not os.path.isfile(os.path.join(PRJPATH, '.git')):
	os.system('git init')

if not os.path.isdir(DSTPATH):
	os.makedirs(DSTPATH)


with open(INCLUDE_FILE) as f:
	for filename in f.readlines():
		filename = filename.replace('air/', '').replace('\n','')
		# print(filename)
		split_path = filename.split('/')
		if len(split_path) > 1:
			# subdir = split_path[-2]
			subdir_path = os.path.join(DSTPATH, *split_path[:-1])
			if not os.path.isdir(subdir_path):
				print("Creating subdir path '{}'".format(subdir_path))
				os.makedirs(subdir_path)
		src = os.path.join(SRCPATH, filename)
		dst = os.path.join(DSTPATH, filename)
		print("Copying '{}' to '{}'".format(src, dst))
		shutil.copyfile(src, dst)
		if not os.path.isfile(dst):
			print("[ ERROR ]  shutil.copyfile() was unsuccessful for '{}'!".format(dst))


