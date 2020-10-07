#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

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

void float2FourBytes(char bytes[4], float f) {
	union u_tag
    {
    	uint8_t b[4];
    	float val;
    } u;
	u.val = f;
	for (int i = 0; i < 4; i++) {
		bytes[i] = u.b[i];
		// printf("[%d] 0x%x\n", i, bytes[i]);
	}
}


// int main(void) {
int main(int argc, char* argv[]) {
	// printf("argc: %d\n", argc);
	char bytes[4];
	float input;

	if (argc != 2) {
		// bytes = { 0xDE, 0xAD, 0xBE, 0xEF };
		printf("\n ERROR: Missing required float argument\n");
		return 1;
	}

	// double atof(const char *string);
	input = (float) atof(argv[1]);
	printf("input: %f\n", input);
	float2FourBytes(bytes, input);
	
	byte_pair_t hi, lo;
	lo.b[0] = bytes[0];
	lo.b[1] = bytes[1];
	hi.b[0] = bytes[2];
	hi.b[1] = bytes[3];
	printf("uint16_t hi: %hu (0x%x)\nuint16_t lo: %hu (0x%x)\n", hi.val, hi.val, lo.val, lo.val);
	printf("Format1: %d.%d\n", hi.val, lo.val);		// <-- INCORRECT

	float equivalent = fourBytes2float(bytes[0], bytes[1], bytes[2], bytes[3]); 
	printf("Format2: %f\n", equivalent);			// <-- CORRECT
	return 0;
}
