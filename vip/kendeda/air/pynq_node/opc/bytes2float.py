import os, sys 
import struct

## 123.45 == 0x42f6e666


class uint16_t:
	def __init__(self, val):
		self.val = val 							## Example: val = 58982 == 0xe666
		self.hex = hex(self.val)[2:]			## hex = "e666"
		self.lsb = int(self.hex[-2:], 16)		## lsb = 102 == 0x66 
		self.msb = int(self.hex[-4:-2], 16)		## msb = 230 == 0xe6
		
	@property
	def b0(self):
		return hex(self.lsb)[2:]

	@property
	def b1(self):
		return hex(self.msb)[2:]


def main():
	argc = len(sys.argv)
	if argc != 2:
		print("\n ERROR: Missing required float argument\n")
		sys.exit(1)
	in_float = float(sys.argv[1])
	# print("input: {}".format(in_float))
	print("input: %f" % in_float)
	ba = bytearray(struct.pack("f", in_float))

	# lo = (ba[0] << 8) | ba[1] 
	# hi = (ba[2] << 8) | ba[3] 
	lo = (ba[1] << 8) | ba[0] 		## Account for byte order
	hi = (ba[3] << 8) | ba[2] 

	print("uint16_t hi: %hu (0x%x)\nuint16_t lo: %hu (0x%x)" % (hi, hi, lo, lo));
	print("Format1: %d.%d" % (hi, lo))
	
	# packed_hi = struct.pack('H', hi)	
	# packed_lo = struct.pack('H', lo)
	# hi = ''.join(chr(i) for i in ba[:2])
	# lo = ''.join(chr(i) for i in ba[2:])
	# equivalent = struct.unpack('>f', (hi, lo))

	"""
		>>> b = bytearray(b'B\xc8\x00\x00') 
		>>> f = struct.unpack('>f', b)
	"""

	short_hi = uint16_t(hi)
	short_lo = uint16_t(lo)

	## 'H' formatter == unsigned short (uint16_t)
	# b = bytearray(struct.pack("HH", short_lo.val, short_hi.val))
	b = bytearray(struct.pack("HH", lo, hi))

	equivalent = struct.unpack('f', b)
	print("Format2: %f" % equivalent)

if __name__ == "__main__":
	main()
