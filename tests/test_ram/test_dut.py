import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from cocotbext.obi import ObiBus, ObiHost
from cocotbext.obi.obi_device import ObiDevice


@cocotb.test()
async def test_ram_bulk_rw(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    # Reset
    dut.rst.value = 1
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst.value = 0

    bus = ObiBus.from_prefix(dut, "s_obi")
    host = ObiHost(bus, dut.clk)
    device = ObiDevice(bus, dut.clk, size_bytes=1024)
    device.start()

    # Write 256 bytes pattern
    base = 0x40
    data = bytes([x & 0xFF for x in range(256)])
    # Stream writes per bus width
    for i in range(0, len(data), 4):
        word = int.from_bytes(data[i : i + 4], "little")
        await host.write(base + i, word)

    # Read back and compare
    read_back = bytearray()
    for i in range(0, len(data), 4):
        rb = await host.read(base + i)
        read_back += rb
    assert bytes(read_back[: len(data)]) == data
