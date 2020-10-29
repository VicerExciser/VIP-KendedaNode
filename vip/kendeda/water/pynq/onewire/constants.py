import os

OVERLAY_NAME = 'vip.bit' 	## Put this bitstream file in the directory:  /home/xilinx/pynq/overlays/vip/
OVERLAY_DIR = OVERLAY_NAME.replace('.bit', '')
OVERLAY_PATH = os.path.join('/', 'home', 'xilinx', 'pynq', 'overlays', OVERLAY_DIR, OVERLAY_NAME)

# OL = BaseOverlay(OVERLAY_PATH)   #, download=(not OVERLAY_NAME == PL.bitfile_name.split('/')[-1]))
##                                 #  ^ Skipping the re-download will break 1-Wire search

AXI_OW_IP_NAME = 'ow_master_top_0'	## Vivado IP name for the OneWire controller module
AXI_OW_ADDR  = lambda OL: OL.ip_dict[AXI_OW_IP_NAME]['phys_addr']
_DEFAULT_AXI_OW_ADDR  = 0x83C20000
AXI_OW_RANGE = lambda OL: OL.ip_dict[AXI_OW_IP_NAME]['addr_range']
_DEFAULT_AXI_OW_RANGE = 0x10000

OW_FCLK_IDX = 3 	## 'ow_master_top_0' module is tied to fclk3
PERIOD = 1000 	## for HeatingElement PWM period
CLK_MHZ = 33.33333	## required CPU clock scaling for 1-Wire master
TIMESLOT = 0.00006  	## 1 timeslot == 60 micro seconds
## ^ 1 bit of data is transmitted over the bus per each timeslot

TRANSMIT_BITS = 0x40  	## 64-bits to transmit over the bus
# SCRATCH_RD_SIZE = 0x48  ## read in 72 bits from scratch reg

MAX_DEV = 10 	## Maximimum number of devices the bus will scan for. Valid range is 1 to 255.

###################################################################################################

bus_commands = { 
		'SERIALIZE'     : 0x00001,  ## Send command onto the bus
		'RESET_PULSE'   : 0x10000,  ## Pulls bus low
		'EXEC_W_PULLUP' : 0x00008, 	## Execute command with pull-up
		'EXEC_WO_PULLUP': 0x00018, 	## Execute command without pull-up
		'RD_TIME_SLOTS' : 0x00028,

		'SEARCH_ROM'    : 0x000F0,  ## Search Rom
		'READ_ROM'      : 0x00033,  ## Read Rom // can be used in place of search_rom if only 1 slave
		'MATCH_ROM'     : 0x00055,  ## Match Rom
		'SKIP_ROM'      : 0x000CC,  ## Skip Rom
		'ALARM_SEARCH'  : 0x000EC,  ## Alarm Search
}

bram_registers = { 	
		'CONTROL'  : 0x000,  ## Control Reg Offset
		'RD_SIZE'  : 0x004,  ## Read Size Reg Offset
		'WR_SIZE'  : 0x008,  ## Write Size Reg Offset
		'COMMAND'  : 0x00C,  ## OW Command Reg Offset
		'RD_CRC'   : 0x010,  ## CRC Read Reg Offset
		'CRC_COUNT': 0x014,  ## CRC Count Reg Offset
		'WR_CRC'   : 0x018,  ## CRC Write Reg Offset
		'WR_DATA0' : 0x01C,  ## Write Data Low 32 Reg Offset
		'WR_DATA1' : 0x020,  ## Write Data Hi 32 Reg Offset

		'STATUS'   : 0x040,  ## Status Reg Offset
		'RD_DATA0' : 0x044,  ## Read Data Lower Offset
		'RD_DATA1' : 0x048,  ## Read Data Low Offset
		'RD_DATA2' : 0x04C,  ## Read Data High Offset
		'RD_DATA3' : 0x050,  ## Read Data Highest Offset
		'FOUND'    : 0x054,  ## Num ROMs Found Reg Offset

		'ROM_ID0'  : 0x400,  ## Lo 32 of Serial Number of Device Reg Offset
		'ROM_ID1'  : 0x404,  ## Hi 32 of Device ID Reg Offset
		'ROM_ID2'  : 0x408,
		'ROM_ID3'  : 0x40C,
		'ROM_ID4'  : 0x410,
		'ROM_ID5'  : 0x414,
}

bitmasks = { 	
	## Bit masks for the status register  (from `zpack.vhd`):
		'STA_SRD': 0x00000001,  ## status reg search done bit (c_uir_srd)
		'STA_UN1': 0x00000002,  ## status reg unused (c_uir_nc1)
		'STA_INT': 0x00000004,  ## status reg 1-Wire interrupt bit (c_uir_int)
		'STA_CMD': 0x00000008,  ## status reg cmd done bit (c_uir_cmdd)
		'STA_WRD': 0x00000010,  ## status reg block write done bit (c_uir_wrd)
		'STA_RDD': 0x00000020,  ## status reg block read done bit (c_uir_rdd)
		'STA_RSD': 0x00000040,  ## status reg reset done bit (c_uir_rsd)
		'STA_PRE': 0x00000080,  ## status reg presence pulse after last reset (c_uir_pre)
		'STA_CRC': 0x00000100,  ## status reg crc error bit (c_uir_crce)
		'STA_SER': 0x00000200,  ## status reg search error / no response  (c_uir_srche)
		## ^ This bit gets set if no OW devices respond to the search
		'STA_SME': 0x00000400,  ## status reg search memory error (c_uir_srme)
		'STA_BB' : 0x80000000,  ## READ ONLY: status register's busy bit (c_uir_busy)

	## Bit masks for the control register  (from `zpack.vhd`):
		'CON_SRE': 0x00000001,  ## control reg search rom/alarm bit (c_uir_srb)
		'CON_SAE': 0x00000002,  ## control reg unused (c_uir_uu1)
		'CON_CRC': 0x00000004,  ## control reg append crc bit (c_uir_acrc)
		'CON_CEN': 0x00000008,  ## control reg command enable bit (c_uir_cmden)
		'CON_WRE': 0x00000010,  ## control reg write block enable bit (c_uir_wren)
		'CON_RDE': 0x00000020,  ## control reg read block enable bit (c_uir_rden)
}
