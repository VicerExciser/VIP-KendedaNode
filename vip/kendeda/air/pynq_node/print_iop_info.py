from pprint import pprint   ## Currently unused

from pynq import Overlay
from pynq.overlays.base import BaseOverlay


def walk_dict(d, depth=0):
	""" Recursively traverse multidimensional dictionary, dimension unknown """
	line_prefix = f"  {' '*depth} -->  "
	for k,v in sorted(d.items(), key=lambda x: x[0]):
		if isinstance(v, dict):
			print(f"{line_prefix}'{k}':")
			walk_dict(v, depth+3)
		else:
			if isinstance(v, int):
				print(f"{line_prefix}'{k}':\t{v} ({hex(v)})")
			else:
				print(f"{line_prefix}'{k}':\t{v}")
			

def print_iop_info(ip_dict):
	for key in ip_dict.keys():                                                                      
		if 'iop' in key:    
			iop_dict = dict()
			iop_dict[key] = ip_dict.get(key)                                                                
			print(f"\n{'-'*10}\n\nIP: {key}")
			walk_dict(iop_dict)		


def test_Overlay(bitfile='base.bit'):
	base = Overlay(bitfile)
	print_iop_info(base.ip_dict)


def test_BaseOverlay(bitfile='base.bit'):
	base = BaseOverlay(bitfile)
	print_iop_info(base.ip_dict)


def test_PrettyPrint():
	base = Overlay('base.bit')
	iop_dict = dict()
	for k,v in base.ip_dict.items():
		if 'iop' in k:
			iop_dict[k] = v
	pprint(iop_dict)


if __name__ == "__main__":
	# test_Overlay()
	test_BaseOverlay()
	test_PrettyPrint()
