/*
opc.c

A MicroBlaze application for the Alphasense OPC-N2 on the PYNQ-Z1 SoC.

*/

// Include libraries
#include <stdint.h>
#include "circular_buffer.h"
#include "timer.h" 	// For delay_ms() and delay_us()
#include "spi.h"	// Import the Xilinx SPI library

// ------------------------------------------------------------------------------------------------

// #define PM_BYTEWISE     // Comment out to read all PM values in a single SPI transaction
// #define HIST_BYTEWISE   // Comment out to read all Histogram data in a single SPI transaction

#define OFF 0
#define ON  1
#define PACKET_LENGTH 2  // Bytes

// Pmod SPI pin assignments (pins 0, 1, 4, and 5 support SPI as they are tied to pins w/ pull-down resistors)
#define SPICLK_PIN 1		// OPC pin #2
#define MISO_PIN   0		// OPC pin #3
#define MOSI_PIN   4		// OPC pin #4
#define SS_PIN     5		// OPC pin #5

// Mailbox Commands
#define CONFIG_IOP_SWITCH  0x1
#define OPC_ON             0x3  // Turn device on
#define OPC_OFF            0x5  // Turn device off
#define OPC_CLOSE          0x7  // Close the SPI bus
#define READ_PM            0x9  // Read particulate matter data
#define READ_HIST          0xB  // Read histogram
#define NUM_DEVICES        0xD  // Read number of connected SPI devices
#define READ_STATE         0xF  // Read whether the device is on or off 

// ------------------------------------------------------------------------------------------------

// Our SPI interface
spi spi_device = NULL;
int state = OFF;	// Assuming device is off to begin with

#define PM_LENGTH    12
#define HIST_LENGTH  62

struct PMData {
	u8 pm1[4];
	u8 pm25[4];
	u8 pm10[4];
};

struct HistogramData {
	u16 bin0;
	u16 bin1;
	u16 bin2;
	u16 bin3;
	u16 bin4;
	u16 bin5;
	u16 bin6;
	u16 bin7;
	u16 bin8;
	u16 bin9;
	u16 bin10;
	u16 bin11;
	u16 bin12;
	u16 bin13;
	u16 bin14;
	u16 bin15;

	float bin1MToF;                 // Mass Time-of-Flight
	float bin3MToF; 
	float bin5MToF;
	float bin7MToF;

	float sfr;                      // Sample Flow Rate
	unsigned long temp_pressure;    // Either the Temperature or Pressure
	float period;                   // Sampling Period
	unsigned int checksum;          // Checksum

	struct PMData pm;
};


typedef union _byte_pair_t
{
	u8 b[2];
	u16 val;
} byte_pair_t;

// ------------------------------------------------------------------------------------------------

// Combine two bytes into a 16-bit unsigned int
u16 twoBytes2int(u8 LSB, u8 MSB) {
	u16 int_val = ((MSB << 8) | LSB);
	return int_val;
}


// Return a 32-bit unsigned int from 4 bytes
u32 fourBytes2int(u8 val0, u8 val1, u8 val2, u8 val3) {
	return ((val3 << 24) | (val2 << 16) | (val1 << 8) | val0);
}


// Return an IEEE754 float from an array of 4 bytes
float fourBytes2float(u8 val0, u8 val1, u8 val2, u8 val3) {
	union u_tag
	{
		u8 b[4];
		float val;
	} u;
	
	u.b[0] = val0;
	u.b[1] = val1;
	u.b[2] = val2;
	u.b[3] = val3;
	
	return u.val;
}


void float2FourBytes(u8 bytes[4], float f) {
	union u_tag
	{
		u8 b[4];
		float val;
	} u;
	u.val = f;
	for (int i = 0; i < 4; i++) {
		bytes[i] = u.b[i];
	}
}

// ------------------------------------------------------------------------------------------------

// Setup SPI
void device_setup() {
	/*
	 * Initialize SPIs with clk_polarity and clk_phase as 0
	 */
	spi_device = spi_open(SPICLK_PIN, MISO_PIN, MOSI_PIN, SS_PIN);			// Initialize SPI on the PYNQ
	spi_device = spi_configure(spi_device, 0, 0);
	delay_us(10000);
	
	// For experimental purposes:
	on();
	off();
}

// ------------------------------------------------------------------------------------------------

int close() {
	spi_close(spi_device);
	return 0;
}

// ------------------------------------------------------------------------------------------------

// Turn OPC on -- Returns the OPC state (0 - off; 1 - on) 
int on() {
	const u8 write_data[PACKET_LENGTH] = {0x03, 0x00};	// "ON" command bytes
	const u8 expected[PACKET_LENGTH] = {243, 3}; 			// Return bytes (0xF3, 0x03)
	u8 read_data[PACKET_LENGTH] = {0, 0}; 				// Initialize array for return bytes

	// Command OPC on while it's off (three attempts)
	int i = 0;
	while (state == OFF) { 	// OPC assumed off
		i++;
		// SPI Transaction:
		// (1) Write 0x03 to bus --> should populate read_data[0] response byte with 0xF3
		spi_transfer(spi_device, &write_data[0], &read_data[0], 1);
		// (2) Delay ~10000 microseconds
		delay_us(10000);
		// (3) Write 0x00 to bus --> should populate read_data[1] response byte with 0x03
		spi_transfer(spi_device, &write_data[1], &read_data[1], 1);
		
		// check if bytes were received
		if ((read_data[0] == expected[0]) & (read_data[1] == expected[1])) {
			state = ON;
			// Serial.println("Command sucessful - OPC powered on!");
		} else {
			state = OFF;
			if (i==1)
			{   // Delay & repeat command if first attempt was unsucessful
				delay_ms(15000);
			} else if (i==2) {   // Reset OPC and repeat command if second attempt was unsucessful
				delay_ms(65000);
			} else {   // Close SPI bus if third attempt was unsucessful
				close();
			}
		 }
	 }
	// Return status of OPC
	return state;
}

// ------------------------------------------------------------------------------------------------

// Turn OPC off -- Returns the OPC state (0 - off; 1 - on) 
int off() {
	const u8 write_data[PACKET_LENGTH] = {0x03, 0x01}; 	// "OFF" command bytes
	const u8 expected[PACKET_LENGTH] = {243, 3};			// Return bytes (0xF3, 0x03)
	u8 read_data[PACKET_LENGTH] = {0, 0}; 				// Initialize array for return bytes
	
	while (state == ON) {
		// SPI Transaction:
		// (1) Write 0x03 to bus --> should populate read_data[0] response byte with 0xF3
		spi_transfer(spi_device, &write_data[0], &read_data[0], 1);
		// (2) Delay ~10000 microseconds
		delay_us(10000);
		// (3) Write 0x01 to bus --> should populate read_data[1] response byte with 0x03
		spi_transfer(spi_device, &write_data[1], &read_data[1], 1);
		
		// Check if bytes were received
		if ((read_data[0] == expected[0]) & (read_data[1] == expected[1])) {
			state = OFF;
		} else {
			state = ON;     // Transaction failed, delay & try again
			delay_ms(65000);
		}
	}
	// Return status of OPC
	return state;
}

// ------------------------------------------------------------------------------------------------

void read_pm_data(struct PMData* data) {
	/* Adapted from https://github.com/dhhagan/opcn2/blob/master/src/opcn2.cpp */
	const u8 pm_command_byte = 0x32;
	u8 vals[PM_LENGTH];

	// Read the data and clear the local memory
	u8 resp[] = {0x0};
	spi_transfer(spi_device, &pm_command_byte, resp, 1);     // Transfer the command byte
	delay_ms(12);       // Delay for 12 milliseconds

	// Send commands and build array of data
#ifdef PM_BYTEWISE
	const u8 pm_read_byte = 0x00;
	for (int i = 0; i < PM_LENGTH; i++) {
		spi_transfer(spi_device, &pm_read_byte, &vals[i], 1);
		delay_us(4);    // Delay for 4 microseconds
	}
#else  // PM_BYTEWISE
	const u8 cmd_bytes[PM_LENGTH] = {0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0};
	spi_transfer(spi_device, cmd_bytes, vals, PM_LENGTH);
#endif  // PM_BYTEWISE

	for (int i = 0; i < PM_LENGTH; i++) {
		if (i < 4) {
			data->pm1[i] = vals[i];
		} else if (i < 8) {
			data->pm25[i%4] = vals[i];
		} else {
			data->pm10[i%4] = vals[i];
		}
	}
}

// ------------------------------------------------------------------------------------------------

void read_histogram(struct HistogramData* data) {  //, int convert_to_conc) {
	/*
		if convert_to_conc == 1:  bin units are in concentration of particles [particles/ml] per size bin [microns]
		if convert_to_conc == 0:  bin units are in particle count per second [#/s] per size bin [microns]
	*/
	const u8 hist_command_byte = 0x30;
	u8 vals[HIST_LENGTH];

	// Read the data and clear the local memory
	u8 resp[] = {0x00};
	spi_transfer(spi_device, &hist_command_byte, resp, 1);  // Transfer the command byte
	delay_ms(12);       // Delay for 12 milliseconds

	// Send commands and build array of data
#ifdef HIST_BYTEWISE
	const u8 hist_read_byte = 0x00;
	for (int i = 0; i < HIST_LENGTH; i++) {
		spi_transfer(spi_device, &hist_read_byte, &vals[i], 1);
		delay_us(4);    // Delay for 4 microseconds
	}
#else   // HIST_BYTEWISE
	const u8 cmd_bytes[HIST_LENGTH] = {0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
										0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
										0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
										0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
										0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
										0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
										0x0, 0x0};
	spi_transfer(spi_device, cmd_bytes, vals, HIST_LENGTH);
#endif  // HIST_BYTEWISE

	data->period = fourBytes2float(vals[44], vals[45], vals[46], vals[47]);
	data->sfr    = fourBytes2float(vals[36], vals[37], vals[38], vals[39]);

	// If convert_to_conc = True, convert from raw data to concentration
	// double conv = convert_to_conc ? (data.sfr * data.period) : 1.0;              ** <-- Handle this conversion in the Python implementation **

	// Populate all of the bin values
    /*
	data.bin0  = (double) twoBytes2int(vals[0],  vals[1]};
	data.bin1  = (double) twoBytes2int(vals[2],  vals[3])  / conv;
	data.bin2  = (double) twoBytes2int(vals[4],  vals[5])  / conv;
	data.bin3  = (double) twoBytes2int(vals[6],  vals[7])  / conv;
	data.bin4  = (double) twoBytes2int(vals[8],  vals[9])  / conv;
	data.bin5  = (double) twoBytes2int(vals[10], vals[11]) / conv;
	data.bin6  = (double) twoBytes2int(vals[12], vals[13]) / conv;
	data.bin7  = (double) twoBytes2int(vals[14], vals[15]) / conv;
	data.bin8  = (double) twoBytes2int(vals[16], vals[17]) / conv;
	data.bin9  = (double) twoBytes2int(vals[18], vals[19]) / conv;
	data.bin10 = (double) twoBytes2int(vals[20], vals[21]) / conv;
	data.bin11 = (double) twoBytes2int(vals[22], vals[23]) / conv;
	data.bin12 = (double) twoBytes2int(vals[24], vals[25]) / conv;
	data.bin13 = (double) twoBytes2int(vals[26], vals[27]) / conv;
	data.bin14 = (double) twoBytes2int(vals[28], vals[29]) / conv;
	data.bin15 = (double) twoBytes2int(vals[30], vals[31]) / conv;
    */
	data->bin0  = twoBytes2int(vals[0],  vals[1]);
	data->bin1  = twoBytes2int(vals[2],  vals[3]);
	data->bin2  = twoBytes2int(vals[4],  vals[5]);
	data->bin3  = twoBytes2int(vals[6],  vals[7]);
	data->bin4  = twoBytes2int(vals[8],  vals[9]);
	data->bin5  = twoBytes2int(vals[10], vals[11]);
	data->bin6  = twoBytes2int(vals[12], vals[13]);
	data->bin7  = twoBytes2int(vals[14], vals[15]);
	data->bin8  = twoBytes2int(vals[16], vals[17]);
	data->bin9  = twoBytes2int(vals[18], vals[19]);
	data->bin10 = twoBytes2int(vals[20], vals[21]);
	data->bin11 = twoBytes2int(vals[22], vals[23]);
	data->bin12 = twoBytes2int(vals[24], vals[25]);
	data->bin13 = twoBytes2int(vals[26], vals[27]);
	data->bin14 = twoBytes2int(vals[28], vals[29]);
	data->bin15 = twoBytes2int(vals[30], vals[31]);

	data->bin1MToF = (int)(vals[32]) / 3.0;
	data->bin3MToF = (int)(vals[33]) / 3.0;
	data->bin5MToF = (int)(vals[34]) / 3.0;
	data->bin7MToF = (int)(vals[35]) / 3.0;

	// This holds either temperature or pressure
	// If temp, this is temp in C x 10
	// If pressure, this is pressure in Pa
	data->temp_pressure = fourBytes2int(vals[40], vals[41], vals[42], vals[43]);

	data->checksum = twoBytes2int(vals[48], vals[49]);
	
	for (int i = 50; i < HIST_LENGTH; i++) {
		int pm_index = (i % 50) % 4;
		if (i < 54) {
			data->pm.pm1[pm_index]  = vals[i];          // data->pm.pm1  = {vals[50], vals[51], vals[52], vals[53]};
		} else if (i < 58) {
			data->pm.pm25[pm_index] = vals[i];          // data->pm.pm25 = {vals[54], vals[55], vals[56], vals[57]};
		} else {
			data->pm.pm10[pm_index] = vals[i];          // data->pm.pm10 = {vals[58], vals[59], vals[60], vals[61]};
		}
	}
}

// ------------------------------------------------------------------------------------------------

void pack_byte_pairs(struct PMData* pm_data, byte_pair_t* pm1_lo, byte_pair_t* pm1_hi, 
											 byte_pair_t* pm25_lo, byte_pair_t* pm25_hi, 
											 byte_pair_t* pm10_lo, byte_pair_t* pm10_hi) {
	u8 pm1_byte, pm25_byte, pm10_byte;
	for (int i = 0; i < 4; i++) {
		pm1_byte  = pm_data->pm1[i];
		pm25_byte = pm_data->pm25[i];
		pm10_byte = pm_data->pm10[i];

		if (i < 2) {
			pm1_lo->b[i]  = pm1_byte;
			pm25_lo->b[i] = pm25_byte;    //pm_data->pm25[i];
			pm10_lo->b[i] = pm10_byte;    //pm_data->pm10[i];
		} else {
			pm1_hi->b[i%2]  = pm1_byte;
			pm25_hi->b[i%2] = pm25_byte;    //pm_data->pm25[i];
			pm10_hi->b[i%2] = pm10_byte;    //pm_data->pm10[i];
		}
	}
}

// ------------------------------------------------------------------------------------------------

/*	Information regarding the MicroBlaze MAILBOX:
	- The MicroBlaze core/IOP and the ARM processor can only communicate using a shared memory space called a mailbox
	- The ARM processor can only write to the shared memory by word (short / 16 bit / 2 byte transfers), 
		despite long word (32 bit) addressing scheme
	- The MAILBOX memory is Little Endian
	- When calling `spi_transfer()` from spi.h, `read_data` cannot be NULL even if the transaction is a write 
		-- otherwise, subsequent reads will return 0
	- MAILBOX_CMD_ADDR = 0x0000FFFC 		(see: https://github.com/Xilinx/PYNQ/blob/master/boards/sw_repo/pynqmb/src/circular_buffer.h)
	- MAILBOX_DATA address = 0x0000F000

**/

int main(void) {
	u32 cmd;
	struct PMData pm_data;
	struct HistogramData hist_data;
	byte_pair_t pm1_lo, pm1_hi, pm25_lo, pm25_hi, pm10_lo, pm10_hi;
	
	device_setup();

	while (1) {
		while ((MAILBOX_CMD_ADDR & 0x01) == 0);
		cmd = MAILBOX_CMD_ADDR;

		switch (cmd) {
			case CONFIG_IOP_SWITCH:
				// Assign default pin configurations - no operations needed
				MAILBOX_CMD_ADDR = 0x0;
				break;
			
			case OPC_ON: 
				on();
				MAILBOX_CMD_ADDR = 0x0;
				break;

			case OPC_OFF:
				off();
				MAILBOX_CMD_ADDR = 0x0;
				break;

			case OPC_CLOSE:
				close();
				MAILBOX_CMD_ADDR = 0x0;
				break;

			case READ_PM:
				read_pm_data(&pm_data);
				pack_byte_pairs(&pm_data, &pm1_lo, &pm1_hi, &pm25_lo, &pm25_hi, &pm10_lo, &pm10_hi);

				// Write PM data to 6 16-bit mailbox slots
				MAILBOX_DATA(0) = pm1_lo.val;	// MAILBOX_DATA[0]: PM1  bytes 0 and 1
				MAILBOX_DATA(1) = pm1_hi.val;	// MAILBOX_DATA[1]: PM1  bytes 2 and 3

				MAILBOX_DATA(2) = pm25_lo.val;	// MAILBOX_DATA[2]: PM25 bytes 0 and 1
				MAILBOX_DATA(3) = pm25_hi.val;	// MAILBOX_DATA[3]: PM25 bytes 2 and 3

				MAILBOX_DATA(4) = pm10_lo.val;	// MAILBOX_DATA[4]: PM10 bytes 0 and 1
				MAILBOX_DATA(5) = pm10_hi.val;	// MAILBOX_DATA[5]: PM10 bytes 2 and 3

				MAILBOX_CMD_ADDR = 0x0;
				break;

			case READ_HIST:
				// int convert_to_conc = (int) MAILBOX_DATA(0);
				read_histogram(&hist_data);  //, convert_to_conc);
				pack_byte_pairs(&hist_data.pm, &pm1_lo, &pm1_hi, &pm25_lo, &pm25_hi, &pm10_lo, &pm10_hi);

				// Write PM data to 6 16-bit mailbox slots
				MAILBOX_DATA(0) = pm1_lo.val;	// MAILBOX_DATA[0]: PM1  bytes 0 and 1
				MAILBOX_DATA(1) = pm1_hi.val;	// MAILBOX_DATA[1]: PM1  bytes 2 and 3

				MAILBOX_DATA(2) = pm25_lo.val;	// MAILBOX_DATA[2]: PM25 bytes 0 and 1
				MAILBOX_DATA(3) = pm25_hi.val;	// MAILBOX_DATA[3]: PM25 bytes 2 and 3

				MAILBOX_DATA(4) = pm10_lo.val;	// MAILBOX_DATA[4]: PM10 bytes 0 and 1
				MAILBOX_DATA(5) = pm10_hi.val;	// MAILBOX_DATA[5]: PM10 bytes 2 and 3

				// Write histogram bin data to mailbox slots 6..21
				MAILBOX_DATA(6)  = (u16) hist_data.bin0;
				MAILBOX_DATA(7)  = (u16) hist_data.bin1;
				MAILBOX_DATA(8)  = (u16) hist_data.bin2;
				MAILBOX_DATA(9)  = (u16) hist_data.bin3;
				MAILBOX_DATA(10) = (u16) hist_data.bin4;
				MAILBOX_DATA(11) = (u16) hist_data.bin5;
				MAILBOX_DATA(12) = (u16) hist_data.bin6;
				MAILBOX_DATA(13) = (u16) hist_data.bin7;
				MAILBOX_DATA(14) = (u16) hist_data.bin8;
				MAILBOX_DATA(15) = (u16) hist_data.bin9;
				MAILBOX_DATA(16) = (u16) hist_data.bin10;
				MAILBOX_DATA(17) = (u16) hist_data.bin11;
				MAILBOX_DATA(18) = (u16) hist_data.bin12;
				MAILBOX_DATA(19) = (u16) hist_data.bin13;
				MAILBOX_DATA(20) = (u16) hist_data.bin14;
				MAILBOX_DATA(21) = (u16) hist_data.bin15;

				MAILBOX_CMD_ADDR = 0x0;
				break;

			case NUM_DEVICES:
				MAILBOX_DATA(0) = (u16) spi_get_num_devices();
				MAILBOX_CMD_ADDR = 0x0;
				break;

			case READ_STATE:
				MAILBOX_DATA(0) = (u16) state;

			default:
				MAILBOX_CMD_ADDR = 0x0;
				break;
		}
	}
	return 0;
}
