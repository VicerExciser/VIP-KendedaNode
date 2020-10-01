/*
Alpha.c

A MicroBlaze application for the Alphasense OPC-N2 on the PYNQ-Z1 SoC.

 */

// include libraries
// #include <stdio.h>
#include <stdint.h>
// #include "xparameters.h"
#include "circular_buffer.h"
#include "timer.h" 	// For delay_ms() and delay_us()
#include "spi.h"	// Import the Xilinx SPI library

#define PM_BYTEWISE     // Comment out to read all PM values in a single SPI transaction
#define HIST_BYTEWISE   // Comment out to read all Histogram data in a single SPI transaction

#define OFF 0
#define ON  1
#define PACKET_LENGTH 2  // Bytes

// CHANGE THESE
unsigned int spiclk_pin = 13; 	//10;
unsigned int miso_pin = 12; 	//11;
unsigned int mosi_pin = 11; 	//12;
unsigned int ss_pin = 10; 		//13;

// Mailbox Commands
#define CONFIG_IOP_SWITCH  0x1
#define OPC_ON             0x3  // Turn device on
#define OPC_OFF            0x5  // Turn device off
#define OPC_CLOSE          0x7  // Close the SPI bus
#define READ_PM            0x9  // Read particulate matter data
#define READ_HIST          0xB  // Read histogram

// Our SPI interface
spi spi_device;

struct PMData {
    /*
    float pm1;
    float pm25;
    float pm10;
    */
    char pm1[4];
    char pm25[4];
    char pm10[4];
};

struct HistogramData {
    /*double*/ uint16_t bin0;
    /*double*/ uint16_t bin1;
    /*double*/ uint16_t bin2;
    /*double*/ uint16_t bin3;
    /*double*/ uint16_t bin4;
    /*double*/ uint16_t bin5;
    /*double*/ uint16_t bin6;
    /*double*/ uint16_t bin7;
    /*double*/ uint16_t bin8;
    /*double*/ uint16_t bin9;
    /*double*/ uint16_t bin10;
    /*double*/ uint16_t bin11;
    /*double*/ uint16_t bin12;
    /*double*/ uint16_t bin13;
    /*double*/ uint16_t bin14;
    /*double*/ uint16_t bin15;

    float bin1MToF; // Mass Time-of-Flight
    float bin3MToF; 
    float bin5MToF;
    float bin7MToF;

    float sfr;  // Sample Flow Rate
    unsigned long temp_pressure;    // Either the Temperature or Pressure
    float period;   // Sampling Period
    unsigned int checksum;  // Checksum

    /*
    float pm1;
    float pm25;
    float pm10;
    */
    // char pm1[4];
    // char pm25[4];
    // char pm10[4];
    struct PMData pm;
};


typedef union _byte_pair_t
{
    uint8_t b[2];
    uint16_t val;
} byte_pair_t;


// Combine two bytes into a 16-bit unsigned int
uint16_t twoBytes2int(uint8_t LSB, uint8_t MSB) {
    uint16_t int_val = ((MSB << 8) | LSB);
    return int_val;
}


uint32_t fourBytes2int(uint8_t val0, uint8_t val1, uint8_t val2, uint8_t val3) {
    // Return a 32-bit unsigned int from 4 bytes
    return ((val3 << 24) | (val2 << 16) | (val1 << 8) | val0);
}


// Return an IEEE754 float from an array of 4 bytes
float fourBytes2float(uint8_t val0, uint8_t val1, uint8_t val2, uint8_t val3) {
    union u_tag
    {
    	uint8_t b[4];
    	float val;
    } u;
    
    u.b[0] = val0;
    u.b[1] = val1;
    u.b[2] = val2;
    u.b[3] = val3;
    
    return u.val;
}


// Setup SPI
void device_setup() {
	/*
     * Initialize SPIs with clk_polarity and clk_phase as 0
     * Configure D10-D13 as Shared SPI (MISO is not used)
     */
	spi_device = spi_open(spiclk_pin, miso_pin, mosi_pin, ss_pin);			// Initialize SPI on the PYNQ
	spi_device = spi_configure(spi_device, 0, 0);
    delay_us(10000);
}


int close() {
	spi_close(spi_device);
	return 0;
}


// Turn OPC ON
int on()
{
    int i = 0;
	int state = OFF;                                            // OPC status (0 - off; 1 - on) assumed off
        
    const char write_data[PACKET_LENGTH] = {0x03, 0x00};	// "ON" command bytes
	const char expected[PACKET_LENGTH] = {243, 3}; 			// Return bytes (0xF3, 0x03)
    char read_data[PACKET_LENGTH] = {0, 0}; 				// Initialize array for return bytes

    
    // Command OPC on while it's off (three attempts)
    while (state == OFF) {
        i++;
		/*
        if (i==1) {
            Serial.println("Sending 'ON' command to OPC...(1st attempt)");
        } else if (i==2) {
            Serial.println("Sending 'ON' command to OPC...(2nd attempt)");
        } else if (i==3) {
            Serial.println("Sending 'ON' command to OPC...(3rd attempt)");
        }
		*/

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
            {   // repeat command if first attempt was unsucessful
                // Serial.println("Attempting command again in 15s...");
                delay_ms(15000);
            } else if (i==2) {   // reset OPC and repeat command if second attempt was unsucessful
                // Serial.println("Resetting OPC, please wait 65s...");
                delay_ms(65000);
            } else if (i==3) {   // close SPI bus if third attempt was unsucessful
                // Serial.println("Commands unsucessful... closing SPI bus.");
                close();
                // while(1);
				// exit(1);
            }
         }
     }
    // Return status of OPC
    return state;
}


// Turn OPC off
int off() {
	int state = ON;					// OPC assumed on
    const char write_data[PACKET_LENGTH] = {0x03, 0x01}; 	// "OFF" command bytes
    const char expected[PACKET_LENGTH] = {243, 3};			// Return bytes (0xF3, 0x03)
	char read_data[PACKET_LENGTH] = {0, 0}; 				// Initialize array for return bytes
    
    while (state == ON) {
        // SPI Transaction:
		// (1) Write 0x03 to bus --> should populate read_data[0] response byte with 0xF3
		spi_transfer(spi_device, &write_data[0], &read_data[0], 1);
        // (2) Delay ~10000 microseconds
		delay_us(10000);
		// (3) Write 0x01 to bus --> should populate read_data[1] response byte with 0x03
		spi_transfer(spi_device, &write_data[1], &read_data[1], 1);
        
        // check if bytes were received
        if ((read_data[0] == expected[0]) & (read_data[1] == expected[1])) {
            state = OFF;
            // Serial.println("Commands received - OPC powered off!");
        } else {
            state = ON;
            // Serial.println("Transaction failed.");
            // Serial.println("OPC resetting... wait 65 secs");
            delay_ms(65000);
        }
    }
    // Return status of OPC
    return state;
}


void read_pm_data(struct PMData* data) {
    /* Adapted from https://github.com/dhhagan/opcn2/blob/master/src/opcn2.cpp */
	// struct PMData data;
    const char pm_command_byte = 0x32;
    int pm_length = 12;
	char vals[pm_length];

	// Read the data and clear the local memory
    char resp[] = {0x0};
    spi_transfer(spi_device, &pm_command_byte, resp, 1);     // Transfer the command byte
    delay_ms(12);       // Delay for 12 milliseconds

    // Send commands and build array of data
#ifdef PM_BYTEWISE
    const char pm_read_byte = 0x00;
    for (int i = 0; i < pm_length; i++) {
        spi_transfer(spi_device, &pm_read_byte, &vals[i], 1);
        delay_us(4);    // Delay for 4 microseconds
    }
#else  // PM_BYTEWISE
    const char cmd_bytes[pm_length] = {0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0};
    spi_transfer(spi_device, cmd_bytes, vals, pm_length);
#endif  // PM_BYTEWISE

    /*
    data.pm1  = fourBytes2float(vals[0], vals[1], vals[2],  vals[3]);
    data.pm25 = fourBytes2float(vals[4], vals[5], vals[6],  vals[7]);
    data.pm10 = fourBytes2float(vals[8], vals[9], vals[10], vals[11]);
    */
    for (int i = 0; i < pm_length; i++) {
        if (i < 4) {
            data->pm.pm1[i] = vals[i];
        } else if (i < 8) {
            data->pm.pm25[i%4] = vals[i];
        } else {
            data->pm.pm10[i%4] = vals[i];
        }
    }
    // return data;
}

void read_histogram(struct HistogramData* data) {  //, int convert_to_conc) {
    /*
        if convert_to_conc == 1:  bin units are in concentration of particles [particles/ml] per size bin [microns]
        if convert_to_conc == 0:  bin units are in particle count per second [#/s] per size bin [microns]
    */
    // struct HistogramData data;
    const char hist_command_byte = 0x30;
    int hist_length = 62;
    char vals[hist_length];

    // Read the data and clear the local memory
    char resp[] = {0x00};
    spi_transfer(spi_device, &hist_command_byte, resp, 1);  // Transfer the command byte
    delay_ms(12);       // Delay for 12 milliseconds

    // Send commands and build array of data
#ifdef HIST_BYTEWISE
    const char hist_read_byte = 0x00;
    for (int i = 0; i < hist_length; i++) {
        spi_transfer(spi_device, &hist_read_byte, &vals[i], 1);
        delay_us(4);    // Delay for 4 microseconds
    }
#else   // HIST_BYTEWISE
    const char cmd_bytes[hist_length] = {0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
                                        0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
                                        0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
                                        0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
                                        0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
                                        0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
                                        0x0, 0x0};
    spi_transfer(spi_device, cmd_bytes, vals, hist_length);
#endif  // HIST_BYTEWISE

    // data.period = fourBytes2float(vals[44], vals[45], vals[46], vals[47]);
    // data.sfr    = fourBytes2float(vals[36], vals[37], vals[38], vals[39]);
    data->period = fourBytes2float(vals[44], vals[45], vals[46], vals[47]);
    data->sfr    = fourBytes2float(vals[36], vals[37], vals[38], vals[39]);
    /*
    data->period = {vals[44], vals[45], vals[46], vals[47]};
    data->sfr    = {vals[36], vals[37], vals[38], vals[39]};
    */

    // If convert_to_conc = True, convert from raw data to concentration
    // double conv = convert_to_conc ? (data.sfr * data.period) : 1.0;              ** <-- Handle this conversion in the Python implementation **

    // Calculate all of the bin values
    // data.bin0  = (double) twoBytes2int(vals[0],  vals[1]};
    // data.bin1  = (double) twoBytes2int(vals[2],  vals[3])  / conv;
    // data.bin2  = (double) twoBytes2int(vals[4],  vals[5])  / conv;
    // data.bin3  = (double) twoBytes2int(vals[6],  vals[7])  / conv;
    // data.bin4  = (double) twoBytes2int(vals[8],  vals[9])  / conv;
    // data.bin5  = (double) twoBytes2int(vals[10], vals[11]) / conv;
    // data.bin6  = (double) twoBytes2int(vals[12], vals[13]) / conv;
    // data.bin7  = (double) twoBytes2int(vals[14], vals[15]) / conv;
    // data.bin8  = (double) twoBytes2int(vals[16], vals[17]) / conv;
    // data.bin9  = (double) twoBytes2int(vals[18], vals[19]) / conv;
    // data.bin10 = (double) twoBytes2int(vals[20], vals[21]) / conv;
    // data.bin11 = (double) twoBytes2int(vals[22], vals[23]) / conv;
    // data.bin12 = (double) twoBytes2int(vals[24], vals[25]) / conv;
    // data.bin13 = (double) twoBytes2int(vals[26], vals[27]) / conv;
    // data.bin14 = (double) twoBytes2int(vals[28], vals[29]) / conv;
    // data.bin15 = (double) twoBytes2int(vals[30], vals[31]) / conv;
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

    // data.bin1MToF = (int)(vals[32]) / 3.0;
    // data.bin3MToF = (int)(vals[33]) / 3.0;
    // data.bin5MToF = (int)(vals[34]) / 3.0;
    // data.bin7MToF = (int)(vals[35]) / 3.0;
    data->bin1MToF = (int)(vals[32]) / 3.0;
    data->bin3MToF = (int)(vals[33]) / 3.0;
    data->bin5MToF = (int)(vals[34]) / 3.0;
    data->bin7MToF = (int)(vals[35]) / 3.0;

    // This holds either temperature or pressure
    // If temp, this is temp in C x 10
    // If pressure, this is pressure in Pa
    // data.temp_pressure = fourBytes2int(vals[40], vals[41], vals[42], vals[43]);
    data->temp_pressure = fourBytes2int(vals[40], vals[41], vals[42], vals[43]);

    // data.checksum = twoBytes2int(vals[48], vals[49]);
    data->checksum = twoBytes2int(vals[48], vals[49]);

    // data.pm1  = fourBytes2float(vals[50], vals[51], vals[52], vals[53]);
    // data.pm25 = fourBytes2float(vals[54], vals[55], vals[56], vals[57]);
    // data.pm10 = fourBytes2float(vals[58], vals[59], vals[60], vals[61]);
    
    for (int i = 50; i < hist_length; i++) {
        if (i < 54) {
            data->pm.pm1[i] = vals[i];             // data->pm.pm1  = {vals[50], vals[51], vals[52], vals[53]};
        } else if (i < 58) {
            data->pm.pm25[i%4] = vals[i];          // data->pm.pm25 = {vals[54], vals[55], vals[56], vals[57]};
        } else {
            data->pm.pm10[i%4] = vals[i];          // data->pm.pm10 = {vals[58], vals[59], vals[60], vals[61]};
        }
    }

    // return data;
}


void pack_byte_pairs(struct PMData* pm_data, byte_pair_t* pm1_lo, byte_pair_t* pm1_hi, 
											 byte_pair_t* pm25_lo, byte_pair_t* pm25_hi, 
											 byte_pair_t* pm10_lo, byte_pair_t* pm10_hi) {
	uint8_t pm1_byte, pm25_byte, pm10_byte;
	for (int i = 0; i < 4; i++) {
		pm1_byte  = pm_data->pm.pm1[i];
		pm25_byte = pm_data->pm.pm25[i];
		pm10_byte = pm_data->pm.pm10[i];

		if (i < 2) {
			pm1_lo->b[i] = pm1_byte;
			pm25_lo->b[i] = pm25_byte;    //pm_data->pm25[i];
			pm10_lo->b[i] = pm10_byte;    //pm_data->pm10[i];
		} else {
			pm1_hi->b[i] = pm1_byte;
			pm25_hi->b[i] = pm25_byte;    //pm_data->pm25[i];
			pm10_hi->b[i] = pm10_byte;    //pm_data->pm10[i];
		}
	}
}


int main(void) {
    u32 cmd;
	struct PMData pm_data;
	struct HistogramData hist_data;
	byte_pair_t pm1_lo, pm1_hi, pm25_lo, pm25_hi, pm10_lo, pm10_hi;
    
    device_setup();

    while (1) {
        while (MAILBOX_CMD_ADDR == 0);
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
			/*
				uint8_t pm1_byte, pm25_byte, pm10_byte;
				for (int i = 0; i < 4; i++) {
					pm1_byte  = pm_data.pm1[i];
					pm25_byte = pm_data.pm25[i];
					pm10_byte = pm_data.pm10[i];

					if (i < 2) {
						pm1_lo.b[i] = pm1_byte;
						pm25_lo.b[i] = pm25_byte;  //pm_data.pm25[i];
						pm10_lo.b[i] = pm10_byte;   //pm_data.pm10[i];
					} else {
						pm1_hi.b[i] = pm1_byte;
						pm25_hi.b[i] = pm25_byte;    //pm_data.pm25[i];
						pm10_hi.b[i] = pm10_byte;    //pm_data.pm10[i];
					}
				}
			*/
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
				MAILBOX_DATA(6)  = hist_data.bin0;
				MAILBOX_DATA(7)  = hist_data.bin1;
				MAILBOX_DATA(8)  = hist_data.bin2;
				MAILBOX_DATA(9)  = hist_data.bin3;
				MAILBOX_DATA(10) = hist_data.bin4;
				MAILBOX_DATA(11) = hist_data.bin5;
				MAILBOX_DATA(12) = hist_data.bin6;
				MAILBOX_DATA(13) = hist_data.bin7;
				MAILBOX_DATA(14) = hist_data.bin8;
				MAILBOX_DATA(15) = hist_data.bin9;
				MAILBOX_DATA(16) = hist_data.bin10;
				MAILBOX_DATA(17) = hist_data.bin11;
				MAILBOX_DATA(18) = hist_data.bin12;
				MAILBOX_DATA(19) = hist_data.bin13;
				MAILBOX_DATA(20) = hist_data.bin14;
				MAILBOX_DATA(21) = hist_data.bin15;

				MAILBOX_CMD_ADDR = 0x0;
                break;

			default:
				MAILBOX_CMD_ADDR = 0x0;
                break;
        }
    }
	return 0;
}



