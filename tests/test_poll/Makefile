SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..

TOPLEVEL = dut
MODULE = test_dut

VERILOG_SOURCES = \
    ./regblock.sv \
    ./dut.sv

COCOTB_SOURCES = \

include $(shell cocotb-config --makefiles)/Makefile.sim

CPUIF?=obi-flat
include ../regblock.mak

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst *.vcd
