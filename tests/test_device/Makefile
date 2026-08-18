SIM?=icarus
TOPLEVEL_LANG=verilog

TOPLEVEL = dut
MODULE = test_dut

VERILOG_SOURCES = $(PWD)/dut.sv

COCOTB_TEST_MODULES = test_dut

ifeq ($(WAVES),1)
	ifeq ($(SIM),verilator)
		PLUSARGS += --trace
		EXTRA_ARGS += --trace # vcd format
		EXTRA_ARGS += --trace-fst
		EXTRA_ARGS += --trace-structs
	endif
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst *.vcd




