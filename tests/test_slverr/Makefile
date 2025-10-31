SIM?=icarus
TOPLEVEL_LANG=verilog

TOPLEVEL = regblock
MODULE = test_dut

VERILOG_SOURCES = regblock*.sv

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

COCOTB_TEST_MODULES = test_dut

include $(shell cocotb-config --makefiles)/Makefile.sim

etana:
	rm -rf regblock*.sv
	peakrdl etana regblock.rdl -o ./ --cpuif ${CPUIF} ${RDL_ARGS} --rename regblock

regblock:
	rm -rf regblock*.sv
	peakrdl regblock regblock.rdl -o ./ --cpuif ${CPUIF} ${RDL_ARGS} --rename regblock
	../../../PeakRDL-etana/scripts/hwif_wrapper_tool/generate_wrapper.py regblock.rdl -o ./ --cpuif ${CPUIF} --rename regblock

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst *.vcd

