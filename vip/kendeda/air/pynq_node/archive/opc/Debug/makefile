################################################################################
# Automatically-generated file. Do not edit!
################################################################################

-include ../makefile.init

RM := rm -rf

# All of the sources participating in the build are defined here
-include sources.mk
-include src/subdir.mk
-include subdir.mk
-include objects.mk

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(S_UPPER_DEPS)),)
-include $(S_UPPER_DEPS)
endif
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
endif

-include ../makefile.defs

# Add inputs and outputs from these tool invocations to the build variables 
ELFSIZE += \
opc.elf.size \


# All Target
all: opc.elf secondary-outputs

# Tool invocations
opc.elf: $(OBJS) ../src/lscript.ld $(USER_OBJS)
	@echo 'Building target: $@'
	@echo 'Invoking: MicroBlaze gcc linker'
	mb-gcc -Wl,-gc-sections -Wl,-T -Wl,../src/lscript.ld -L../../bsp_iop_arduino/iop_arduino_mb/lib -mlittle-endian -mcpu=v11.0 -mxl-soft-mul -Wl,--no-relax -o "opc.elf" $(OBJS) $(USER_OBJS) $(LIBS)
	@echo 'Finished building target: $@'
	@echo ' '

opc.elf.size: opc.elf
	@echo 'Invoking: MicroBlaze Print Size'
	mb-size opc.elf  |tee "opc.elf.size"
	@echo 'Finished building: $@'
	@echo ' '

opc.bin: opc.elf
	@echo 'Invoking: MicroBlaze Bin Gen'
	mb-objcopy -O binary opc.elf opc.bin
	@echo 'Finished building: $@'
	@echo ' '

# Other Targets
clean:
	-$(RM) $(EXECUTABLES)$(OBJS)$(S_UPPER_DEPS)$(C_DEPS)$(ELFSIZE) opc.elf opc.bin
	-@echo ' '

secondary-outputs: $(ELFSIZE) opc.bin

.PHONY: all clean dependents
.SECONDARY:

-include ../makefile.targets
