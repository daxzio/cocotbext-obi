SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..

TOPLEVEL = dut
MODULE = test_dut

INT_VERILOG_SOURCES += \
	./regblock.sv \
	./blockmem_1p.sv \
	./dut.sv

COCOTB_SOURCES = \

include ${WORK_BASE}/rtlflo/cocotb_helper.mak

CPUIF?=obi-flat
RDL_ARGS?=-P N_REGS=64 -P REGWIDTH=32
include ../regblock.mak

# UDP must be compiled before regblock.rdl so early_external_read is recognized.
etana:
	peakrdl etana ./etana_udps.rdl regblock.rdl -o ./ --cpuif ${CPUIF} ${RDL_ARGS} --rename regblock
