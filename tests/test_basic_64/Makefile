SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..

TOPLEVEL = regblock
MODULE = test_dut

VERILOG_SOURCES = regblock*.sv

COCOTB_SOURCES = \

include $(shell cocotb-config --makefiles)/Makefile.sim

CPUIF?=obi-flat
RDL_ARGS?=-P N_REGS=32 -P REGWIDTH=64
include ../regblock.mak

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst *.vcd
