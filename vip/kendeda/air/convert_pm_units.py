







# Conversion for #/cc (particles per cubic centimeter)
# to ug/m^3 (micrograms per cubic meter)
def convert_units(ppcc):
	# 1 particle per cubic centimeter = 1,000,000 particles per cubic meter
	ppcm = ppcc * 1000000

	# particles per cc x 210 (approximately) = mg/m^3
	mgpm3 = ppcc * 210

	# 1 milligram per cubic meter = 1000 micrograms per cubic meter
	ugpm3 = mgpm3 * 1000

	return ugpm3
