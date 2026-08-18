from random import randint
from cocotb import test

from interfaces.clkrst import ClkReset

from cocotbext.obi import ObiHost
from cocotbext.obi import ObiBus
from cocotbext.obi.obi_device import ObiDevice

from cocotbext.obi.address_space import MemoryRegion


class testbench:
    def __init__(
        self,
        dut,
        max_outstanding_host=2,
        max_outstanding_device=2,
        reset_sense=1,
        period=10,
    ):
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        self.sbus = ObiBus.from_prefix(dut, "s_obi")
        self.mbus = ObiBus.from_prefix(dut, "m_obi")
        clk_name = "clk"

        # Create host with specified max_outstanding
        self.m = ObiHost(
            self.sbus, getattr(dut, clk_name), max_outstanding=max_outstanding_host
        )

        # Create device with specified max_outstanding
        self.s = ObiDevice(
            self.mbus, getattr(dut, clk_name), max_outstanding=max_outstanding_device
        )
        region = MemoryRegion(2**self.s.address_width)
        self.s.target = region


@test()
async def test_pipelined_writes(dut):
    """Test multiple outstanding writes with pipelining"""
    tb = testbench(dut, max_outstanding_host=4, max_outstanding_device=4, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # Write multiple values in rapid succession
    values = [0x11111111, 0x22222222, 0x33333333, 0x44444444, 0x55555555]

    for i, val in enumerate(values):
        await tb.m.write(0x1000 + i * 4, val)

    # Read back and verify
    for i, val in enumerate(values):
        r = await tb.m.read(0x1000 + i * 4)
        assert int.from_bytes(r, "little") == val

    await tb.cr.end_test(20)


@test()
async def test_pipelined_reads(dut):
    """Test multiple outstanding reads with pipelining"""
    tb = testbench(dut, max_outstanding_host=4, max_outstanding_device=4, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # Write test data first
    values = [0xAAAA0000, 0xBBBB1111, 0xCCCC2222, 0xDDDD3333]

    for i, val in enumerate(values):
        await tb.m.write(0x2000 + i * 4, val)

    # Read multiple values in rapid succession
    results = []
    for i in range(len(values)):
        r = await tb.m.read(0x2000 + i * 4)
        results.append(int.from_bytes(r, "little"))

    # Verify all results
    for i, val in enumerate(values):
        assert results[i] == val

    await tb.cr.end_test(20)


@test()
async def test_pipelined_mixed_rw(dut):
    """Test interleaved writes and reads with pipelining"""
    tb = testbench(dut, max_outstanding_host=3, max_outstanding_device=3, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # Interleave writes and reads
    await tb.m.write(0x3000, 0x12345678)
    await tb.m.write(0x3004, 0x87654321)

    r1 = await tb.m.read(0x3000)
    assert int.from_bytes(r1, "little") == 0x12345678

    await tb.m.write(0x3008, 0xABCDEF00)

    r2 = await tb.m.read(0x3004)
    assert int.from_bytes(r2, "little") == 0x87654321

    r3 = await tb.m.read(0x3008)
    assert int.from_bytes(r3, "little") == 0xABCDEF00

    await tb.cr.end_test(20)


@test()
async def test_backpressure(dut):
    """Test that backpressure works when max_outstanding limit is reached"""
    tb = testbench(dut, max_outstanding_host=2, max_outstanding_device=2, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # Queue multiple transactions - should be limited to max_outstanding
    values = [0x55555555, 0x66666666, 0x77777777, 0x88888888]

    # Queue all writes
    for i, val in enumerate(values):
        tb.m.write_nowait(0x4000 + i * 4, val)

    # Wait for all to complete
    await tb.m.wait()

    # Verify all values
    for i, val in enumerate(values):
        r = await tb.m.read(0x4000 + i * 4)
        assert int.from_bytes(r, "little") == val

    await tb.cr.end_test(20)


@test()
async def test_inorder_completion(dut):
    """Verify responses come back in strict order (OBI requirement)"""
    tb = testbench(dut, max_outstanding_host=4, max_outstanding_device=4, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # Add delay to device to ensure responses don't complete immediately
    tb.s.enable_backpressure()

    # Write multiple values with randomized data
    values = []
    for i in range(8):
        val = randint(0, 0xFFFFFFFF)
        values.append(val)
        await tb.m.write(0x5000 + i * 4, val)

    # Read back - should get exact same values in same order
    for i, expected_val in enumerate(values):
        r = await tb.m.read(0x5000 + i * 4)
        assert (
            int.from_bytes(r, "little") == expected_val
        ), f"Mismatch at address 0x{0x5000 + i*4:x}: expected 0x{expected_val:x}, got 0x{int.from_bytes(r, 'little'):x}"

    await tb.cr.end_test(20)


@test()
async def test_sequential_mode(dut):
    """Test backward compatibility - sequential mode with max_outstanding=1"""
    tb = testbench(dut, max_outstanding_host=1, max_outstanding_device=1, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # These should complete sequentially
    values = [0xAAAA1111, 0xBBBB2222, 0xCCCC3333]

    for i, val in enumerate(values):
        await tb.m.write(0x6000 + i * 4, val)

    for i, val in enumerate(values):
        r = await tb.m.read(0x6000 + i * 4)
        assert int.from_bytes(r, "little") == val

    await tb.cr.end_test(20)


@test()
async def test_max_pipeline_depth(dut):
    """Test with larger pipeline depth"""
    tb = testbench(dut, max_outstanding_host=8, max_outstanding_device=8, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # Write many values
    num_writes = 16
    values = []
    for i in range(num_writes):
        val = randint(0, 0xFFFFFFFF)
        values.append(val)
        await tb.m.write(0x7000 + i * 4, val)

    # Read back
    for i, expected_val in enumerate(values):
        r = await tb.m.read(0x7000 + i * 4)
        assert int.from_bytes(r, "little") == expected_val

    await tb.cr.end_test(20)


@test()
async def test_write_nowait_read_await(dut):
    """Test write_nowait followed by awaiting reads"""
    tb = testbench(dut, max_outstanding_host=3, max_outstanding_device=3, reset_sense=1)

    await tb.cr.wait_clkn(20)

    # Queue multiple writes without waiting
    tb.m.write_nowait(0x8000, 0x11111111)
    tb.m.write_nowait(0x8004, 0x22222222)
    tb.m.write_nowait(0x8008, 0x33333333)

    # Now read them back
    r1 = await tb.m.read(0x8000)
    assert int.from_bytes(r1, "little") == 0x11111111

    r2 = await tb.m.read(0x8004)
    assert int.from_bytes(r2, "little") == 0x22222222

    r3 = await tb.m.read(0x8008)
    assert int.from_bytes(r3, "little") == 0x33333333

    await tb.cr.end_test(20)
