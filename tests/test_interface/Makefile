SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..

TOPLEVEL = regblock
MODULE = test_dut

VERILOG_SOURCES = ../test_basic/regblock*.sv

COCOTB_SOURCES = \

include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst *.vcd
