from random import randint
from cocotb import test

from interfaces.clkrst import ClkReset

from cocotbext.obi import ObiMaster
from cocotbext.obi import ObiBus
from cocotbext.obi.obi_monitor import ObiMonitor
from cocotbext.obi.obi_slave import ObiSlave
from cocotbext.obi.obi_ram import ObiRam

from cocotbext.apb.address_space import MemoryRegion


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        self.sbus = ObiBus.from_prefix(dut, "s_obi")
        clk_name = "clk"
        self.m = ObiMaster(self.sbus, getattr(dut, clk_name))

        self.obi_mon = ObiMonitor(self.sbus, getattr(dut, "clk"))
        self.obi_mon.start()


@test()
async def test_apb_memdump(dut):
    tb = testbench(dut, reset_sense=1)
    tb.s = ObiSlave(tb.sbus, getattr(dut, "clk"))
    region = MemoryRegion(2**tb.s.address_width)
    tb.s.target = region

    await tb.cr.wait_clkn(20)

    await tb.m.write(0x0010, 0x87654321)
    r = await tb.m.read(0x0010)
    assert int.from_bytes(r, "little") == 0x87654321

    x = []
    for i in range(32):
        x.append(randint(0, 0xFFFFFFFF))

    for i in range(32):
        await tb.m.write(0x0000 + i * 0x4, x[i])

    index = randint(0, 30)
    z = await tb.s.target.read(index * 4, 1)
    y = int.from_bytes(z, byteorder="little")
    assert y == (x[index] & 0xFF)

    z = await tb.s.target.read((index * 4) + 1, 1)
    y = int.from_bytes(z, byteorder="little")
    assert y == ((x[index] >> 8) & 0xFF)

    z = await tb.s.target.read_byte(index * 4)
    y = int.from_bytes(z, byteorder="little")
    assert y == (x[index] & 0xFF)

    z = await tb.s.target.read_byte((index * 4) + 1)
    y = int.from_bytes(z, byteorder="little")
    assert y == ((x[index] >> 8) & 0xFF)

    z = await tb.s.target.read_word(index * 4)
    assert z == (x[index] & 0xFFFF)

    z = await tb.s.target.read_dword(index * 4)
    assert z == x[index]

    z = await tb.s.target.read_qword(index * 4)
    assert z == x[index] | (x[index + 1] << 32)

    await tb.cr.end_test(20)


@test()
async def test_apb_slave(dut):
    tb = testbench(dut, reset_sense=1)
    tb.s = ObiSlave(tb.sbus, getattr(dut, "clk"))
    region = MemoryRegion(2**tb.s.address_width)
    tb.s.target = region

    await tb.cr.wait_clkn(20)

    await tb.m.write(0x0010, 0x87654321)
    r = await tb.m.read(0x0010)
    assert int.from_bytes(r, "little") == 0x87654321

    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x00000000
    await tb.m.write(0x0020, 0x52346325, strb=0x8)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x52000000
    await tb.m.write(0x0020, 0x45325533, strb=0x4)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x52320000
    await tb.m.write(0x0020, 0x74568562, strb=0x2)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x52328500
    await tb.m.write(0x0020, 0xA356B3E1, strb=0x1)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x523285E1

    x = []
    for i in range(32):
        x.append(randint(0, 0xFFFFFFFF))

    for i in range(32):
        await tb.m.write(0x0000 + i * 0x4, x[i])

    for i in range(32):
        r = await tb.m.read(0x0000 + i * 0x4)
        assert int.from_bytes(r, "little") == x[i]

    tb.s.enable_backpressure()
    x = []
    for i in range(32):
        x.append(randint(0, 0xFFFFFFFF))

    for i in range(32):
        await tb.m.write(0x0000 + i * 0x4, x[i])

    for i in range(32):
        r = await tb.m.read(0x0000 + i * 0x4)
        assert int.from_bytes(r, "little") == x[i]

    await tb.cr.end_test(20)


@test()
async def test_apb_ram(dut):
    tb = testbench(dut, reset_sense=1)
    tb.s = ObiRam(tb.sbus, getattr(dut, "clk"))

    await tb.cr.wait_clkn(20)

    await tb.m.write(0x0010, 0x87654321)
    r = await tb.m.read(0x0010)
    assert int.from_bytes(r, "little") == 0x87654321

    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x00000000
    await tb.m.write(0x0020, 0x52346325, strb=0x8)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x52000000
    await tb.m.write(0x0020, 0x45325533, strb=0x4)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x52320000
    await tb.m.write(0x0020, 0x74568562, strb=0x2)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x52328500
    await tb.m.write(0x0020, 0xA356B3E1, strb=0x1)
    r = await tb.m.read(0x0020)
    assert int.from_bytes(r, "little") == 0x523285E1
    x = []
    for i in range(32):
        x.append(randint(0, 0xFFFFFFFF))

    for i in range(32):
        await tb.m.write(0x0000 + i * 0x4, x[i])

    for i in range(32):
        r = await tb.m.read(0x0000 + i * 0x4)
        assert int.from_bytes(r, "little") == x[i]

    tb.s.enable_backpressure()
    x = []
    for i in range(32):
        x.append(randint(0, 0xFFFFFFFF))

    for i in range(32):
        await tb.m.write(0x0000 + i * 0x4, x[i])

    for i in range(32):
        r = await tb.m.read(0x0000 + i * 0x4)
        assert int.from_bytes(r, "little") == x[i]

    await tb.cr.end_test(20)
