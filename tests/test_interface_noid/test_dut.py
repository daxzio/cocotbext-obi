"""
ObiInterface against a DUT whose OBI bus has no aid/rid signals.

Companion to test_interface (which uses a fully-populated OBI DUT).  This
suite pins the optional-signal behaviour: cocotbext-interface declares
optional signals with a ``= None`` class default, so an absent signal must
still report ``hasattr(bus, name) is False`` for the VIPs' guards to work.
"""

from cocotb import test

from interfaces.clkrst import ClkReset

from cocotbext.obi import (
    HAVE_COCOTBEXT_INTERFACE,
    MemoryRegion,
    ObiDevice,
    ObiHost,
    ObiInterface,
    ObiMonitor,
)

# cocotbext-interface is an optional dependency: skip rather than fail when
# it is not installed.
SKIP = not HAVE_COCOTBEXT_INTERFACE


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut

        self.sbus = ObiInterface.from_prefix(dut, "s_obi")
        self.mbus = ObiInterface.from_prefix(dut, "m_obi")
        self.m = ObiHost(self.sbus, dut.clk)

        self.obi_mon = ObiMonitor(self.sbus, dut.clk)
        self.obi_mon.start()


@test(skip=SKIP)
async def test_absent_optional_signals(dut):
    """The DUT has no aid/rid: they must look genuinely missing on the bus."""
    bus = ObiInterface.from_prefix(dut, "s_obi")

    assert not hasattr(bus, "aid"), "absent aid must not be visible"
    assert not hasattr(bus, "rid"), "absent rid must not be visible"
    assert getattr(bus, "aid", None) is None
    assert getattr(bus, "rid", None) is None

    for name in ("req", "gnt", "addr", "we", "be", "wdata", "rvalid", "rready", "rdata", "err"):
        assert hasattr(bus, name), f"required signal {name} missing"

    assert "aid" not in bus._signals
    assert "rid" not in bus._signals
    assert "aid" in bus._optional_signals
    assert "rid" in bus._optional_signals
    assert bus._name == "s_obi"


@test(skip=SKIP)
async def test_traffic_without_ids(dut):
    """ObiHost/ObiMonitor drive an aid/rid-less bus built from ObiInterface."""
    tb = testbench(dut, reset_sense=1)
    tb.s = ObiDevice(tb.mbus, dut.clk)
    tb.s.target = MemoryRegion(2**tb.s.address_width)

    assert not tb.m.has_aid, "ObiHost must detect aid as absent"
    assert not tb.m.has_rid, "ObiHost must detect rid as absent"

    await tb.cr.wait_clkn(20)

    await tb.m.write(0x0010, 0x87654321)
    await tb.m.read(0x0010, 0x87654321)

    await tb.m.write(0x0020, 0xDEADBEEF)
    await tb.m.read(0x0020, 0xDEADBEEF)

    await tb.m.write(0x0030, 0x00000000)
    await tb.m.write(0x0030, 0x11223344, 0x2)
    await tb.m.read(0x0030, 0x00003300)

    await tb.cr.end_test(20)
