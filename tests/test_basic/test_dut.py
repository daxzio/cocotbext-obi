from random import randint
from cocotb import test

from interfaces.clkrst import ClkReset

from cocotbext.obi import ObiMaster
from cocotbext.obi import ObiBus


def returned_val(read_op):
    return int.from_bytes(read_op, byteorder="little")


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):

        self.regwidth = len(dut.s_obi_wdata)
        self.n_regs = 2 ** (len(dut.s_obi_addr) - 2)
        self.mask = (2**self.regwidth) - 1
        self.incr = int(self.regwidth / 8)
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        obi_prefix = "s_obi"
        self.bus = ObiBus.from_prefix(dut, obi_prefix)
        clk_name = "clk"
        self.intf = ObiMaster(self.bus, getattr(dut, clk_name))


@test()
async def test_dut_basic(dut):
    tb = testbench(dut, reset_sense=1)

    await tb.cr.wait_clkn(200)

    read_op = await tb.intf.read(0x0000)
    ret = returned_val(read_op)
    assert 0x1 == ret

    x = 0x12345678
    bytesdata = x.to_bytes(tb.incr, "little")
    await tb.intf.write(0x0000, bytesdata)

    read_op = await tb.intf.read(0x0000)
    ret = returned_val(read_op)
    assert x == ret

    await tb.intf.read(0x0000, bytesdata)
    await tb.intf.read(0x0000, x)

    x = 0x12345679
    bytesdata = x.to_bytes(tb.incr, "little")
    await tb.intf.write(0x0000, x)

    await tb.intf.read(0x0000, x)
    await tb.intf.read(0x0000, 0x12345679)

    await tb.intf.write(0x0000, 0x12)
    await tb.intf.read(0x0000, 0x12)

    await tb.intf.write(0x0000, 0x0)
    await tb.intf.write(0x0000, 0x87654321, 0x8)
    await tb.intf.read(0x0000, 0x87000000)
    await tb.intf.write(0x0000, 0x56346456, 0x4)
    await tb.intf.read(0x0000, 0x87340000)
    await tb.intf.write(0x0000, 0x69754233, 0x2)
    await tb.intf.read(0x0000, 0x87344200)
    await tb.intf.write(0x0000, 0x21454568, 0x1)
    await tb.intf.read(0x0000, 0x87344268)
    await tb.intf.write(0x0000, 0x0)
    await tb.intf.read(0x0000, 0x0)

    await tb.intf.write(0x0004, 0x87654321)
    await tb.intf.read(0x0004, 0x87654321)

    await tb.intf.write(0x0004, 0x97654321)
    await tb.cr.wait_clkn(2)
    await tb.intf.read(0x0004, 0x97654321)

    await tb.intf.write(0x0014, 0x77654321)
    await tb.intf.read(0x0014, 0x77654321)

    await tb.intf.write(0x0000, 0x0)
    await tb.intf.read(0x0000, 0x0)
    await tb.intf.write(0x0000, 0xFFFFFFFF)
    await tb.intf.write(0x0004, 0xFFFFFFFF)
    await tb.intf.read(0x0000, 0xFFFFFFFF)
    await tb.intf.read(0x0004, 0xFFFFFFFF)
    await tb.intf.write(0x0000, 0x0)
    await tb.intf.write(0x0004, 0x0)
    await tb.intf.read(0x0000, 0x0)
    await tb.intf.read(0x0004, 0x0)
    x = randint(0, 0xFFFFFFFFFFFFFFFF)
    await tb.intf.write(0x0000, x, length=8)
    await tb.intf.read(0x0000, x & 0xFFFFFFFF)
    await tb.intf.read(0x0004, (x >> 32) & 0xFFFFFFFF)
    x = randint(0, 0xFFFFFFFFFFFFFFFF)
    bytesdata = x.to_bytes(2 * tb.incr, "little")
    await tb.intf.write(0x0000, bytesdata, length=8)
    await tb.intf.read(0x0000, x & 0xFFFFFFFF)
    await tb.intf.read(0x0004, (x >> 32) & 0xFFFFFFFF)

    x = []
    for i in range(tb.n_regs):
        x.append(randint(0, (2**32) - 1))

    for i in range(tb.n_regs):
        bytesdata = x[i].to_bytes(tb.incr, "little")
        await tb.intf.write(0x0000 + (i * tb.incr), bytesdata)

    for i in range(tb.n_regs):
        z = randint(0, tb.n_regs - 1)
        y = x[z] & tb.mask
        read_op = await tb.intf.read(0x0000 + (z * tb.incr))
        ret = returned_val(read_op)
        assert y == ret
    for i in range(tb.n_regs):
        z = randint(0, tb.n_regs - 1)
        y = x[z] & tb.mask
        read_op = await tb.intf.read(
            0x0000 + (z * tb.incr), y.to_bytes(tb.incr, "little")
        )
    for i in range(tb.n_regs):
        z = randint(0, tb.n_regs - 1)
        y = x[z] & tb.mask
        tb.intf.read_nowait(
            0x0000 + (z * tb.incr), y.to_bytes(tb.incr, "little")
        )

    for i in range(tb.n_regs):
        y = x[i] & tb.mask
        read_op = await tb.intf.read(0x0000 + (i * tb.incr))
        ret = returned_val(read_op)
        assert y == ret

    await tb.cr.end_test(200)
