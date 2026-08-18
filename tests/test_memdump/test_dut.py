import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from cocotbext.obi import ObiBus, ObiHost
from cocotbext.obi.obi_device import ObiDevice


@cocotb.test()
async def test_memdump(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    # Reset
    dut.rst.value = 1
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst.value = 0

    bus = ObiBus.from_prefix(dut, "s_obi")
    dbus = ObiBus.from_prefix(dut, "m_obi")
    host = ObiHost(bus, dut.clk)
    device = ObiDevice(dbus, dut.clk, size_bytes=256)
    device.start()

    # Prefill memory pattern
    for i in range(0, 64, 4):
        val = (i | ((i + 1) << 8) | ((i + 2) << 16) | ((i + 3) << 24)) & 0xFFFFFFFF
        await host.write(i, val)

    # Dump back and compare
    for i in range(0, 64, 4):
        rb = await host.read(i)
        r = int.from_bytes(rb, "little")
        exp = (i | ((i + 1) << 8) | ((i + 2) << 16) | ((i + 3) << 24)) & 0xFFFFFFFF
        assert r == exp
