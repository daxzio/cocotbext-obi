from cocotb import test

from interfaces.clkrst import ClkReset

from cocotbext.obi import ObiHost
from cocotbext.obi import ObiBus
from cocotbext.obi import ObiMonitor


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        obi_prefix = "s_obi"
        self.bus = ObiBus.from_prefix(dut, obi_prefix)
        clk_name = "clk"
        self.intf = ObiHost(self.bus, getattr(dut, clk_name))
        self.obi_mon = ObiMonitor(self.bus, getattr(dut, "clk"))
        self.obi_mon.start()


@test()
async def test_dut_poll(dut):
    tb = testbench(dut)

    await tb.cr.wait_clkn(20)

    await tb.intf.read(0x04, 0)
    await tb.intf.write(0x00, 1)
    await tb.intf.read(0x04, 1)
    await tb.intf.read(0x04, 1)

    await tb.intf.poll(0x04, 0)

    await tb.cr.end_test(20)


@test()
async def test_dut_poll2(dut):
    tb = testbench(dut)

    await tb.cr.wait_clkn(20)

    await tb.intf.read(0x04, 0)
    await tb.intf.write(0x00, 1)

    await tb.intf.poll(0x04, 0)

    await tb.cr.end_test(20)


@test()
async def test_dut_poll3(dut):
    tb = testbench(dut)

    await tb.cr.wait_clkn(20)

    await tb.intf.read(0x04, 0)
    await tb.intf.write(0x00, 1)

    await tb.intf.poll(0x04, b"\x00\x00\x00\x00")

    await tb.cr.end_test(20)
