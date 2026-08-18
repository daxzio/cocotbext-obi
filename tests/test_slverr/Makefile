SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..

TOPLEVEL = regblock
MODULE = test_dut

INT_VERILOG_SOURCES += \
	./regblock.sv \

CPUIF?=obi-flat
RDL_ARGS?=--err-if-bad-addr --err-if-bad-rw
ifeq ($(SIM),verilator)
	COMPILE_ARGS += -Wno-MULTIDRIVEN
	# Only use regblock_wrapper if using regblock target (not etana)
	# etana generates regblock.sv directly
	ifeq ($(filter regblock,$(MAKECMDGOALS)),regblock)
		TOPLEVEL = regblock_wrapper
	endif
endif

COCOTB_SOURCES = \

include ${WORK_BASE}/rtlflo/cocotb_helper.mak

etana:
	rm -rf regblock*.sv
	peakrdl etana regblock.rdl -o ./ --cpuif ${CPUIF} ${RDL_ARGS} --rename regblock

HWIF_WRAPPER_TOOL ?= ../../../PeakRDL-etana/scripts/hwif_wrapper_tool/generate_wrapper.py
regblock:
	rm -rf regblock*.sv
	peakrdl regblock regblock.rdl -o ./ --cpuif ${CPUIF} ${RDL_ARGS} --rename regblock
	@if [ -x "$(HWIF_WRAPPER_TOOL)" ]; then \
		"$(HWIF_WRAPPER_TOOL)" regblock.rdl -o ./ --cpuif ${CPUIF} --rename regblock; \
	else \
		echo "hwif_wrapper_tool not found at '$(HWIF_WRAPPER_TOOL)' (set HWIF_WRAPPER_TOOL); skipping wrapper generation"; \
	fi
