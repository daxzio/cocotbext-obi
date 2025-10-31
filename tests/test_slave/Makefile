SIM?=icarus
TOPLEVEL_LANG=verilog

TOPLEVEL = obi_top
MODULE = test_dut

VERILOG_SOURCES = $(PWD)/obi_top.sv

COCOTB_TEST_MODULES = test_dut

include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst *.vcd

