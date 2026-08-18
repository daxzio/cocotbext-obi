SIM?=icarus
TOPLEVEL_LANG=verilog

TOPLEVEL = dut
MODULE = test_dut

VERILOG_SOURCES = $(PWD)/../test_device/dut.sv

COCOTB_TEST_MODULES = test_dut

include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst *.vcd




