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
opc_pmod.elf.size \


# All Target
all: opc_pmod.elf secondary-outputs

# Tool invocations
opc_pmod.elf: $(OBJS) ../src/lscript.ld $(USER_OBJS)
	@echo 'Building target: $@'
	@echo 'Invoking: MicroBlaze gcc linker'
	mb-gcc -Wl,-gc-sections -Wl,-T -Wl,../src/lscript.ld -L../../bsp_iop_arduino/iop_arduino_mb/lib -mlittle-endian -mcpu=v11.0 -mxl-soft-mul -Wl,--no-relax -o "opc_pmod.elf" $(OBJS) $(USER_OBJS) $(LIBS)
	@echo 'Finished building target: $@'
	@echo ' '

opc_pmod.elf.size: opc_pmod.elf
	@echo 'Invoking: MicroBlaze Print Size'
	mb-size opc_pmod.elf  |tee "opc_pmod.elf.size"
	@echo 'Finished building: $@'
	@echo ' '

opc_pmod.bin: opc_pmod.elf
	@echo 'Invoking: MicroBlaze Bin Gen'
	mb-objcopy -O binary opc_pmod.elf opc_pmod.bin
	@echo 'Finished building: $@'
	@echo ' '

# Other Targets
clean:
	-$(RM) $(EXECUTABLES)$(OBJS)$(S_UPPER_DEPS)$(C_DEPS)$(ELFSIZE) opc_pmod.elf opc_pmod.bin
	-@echo ' '

secondary-outputs: $(ELFSIZE) opc_pmod.bin

.PHONY: all clean dependents
.SECONDARY:

-include ../makefile.targets
