from random import randint

from cocotb import start_soon, test
from cocotb.triggers import RisingEdge
from cocotb.utils import get_sim_time

from interfaces.clkrst import ClkReset

from cocotbext.obi import ObiBus, ObiHost


async def _monitor_grants(dut, edges: list[int]) -> None:
    """Record simulation time for each req&&gnt rising-edge sample."""
    await RisingEdge(dut.clk)
    while True:
        await RisingEdge(dut.clk)
        if int(dut.s_obi_req.value) and int(dut.s_obi_gnt.value):
            edges.append(get_sim_time("ns"))


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):
        self.regwidth = len(dut.s_obi_wdata)
        self.n_regs = 2 ** (len(dut.s_obi_addr) - 2)
        self.mask = (2**self.regwidth) - 1
        self.incr = int(self.regwidth / 8)
        self.period = period
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.dut = dut
        self.bus = ObiBus.from_prefix(dut, "s_obi")
        self.intf = ObiHost(self.bus, getattr(dut, "clk"))


async def _exercise(tb):
    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    await tb.intf.write(0x0010, x0)
    await tb.intf.write(0x0014, x1)
    await tb.intf.read(0x0010, x0)
    await tb.intf.read(0x0014, x1)

    for _ in range(8):
        addr = 0x0020 + (randint(0, 15) * 4)
        val = randint(0, 0xFFFFFFFF)
        await tb.intf.write(addr, val)
        await tb.intf.read(addr, val)

    for _ in range(8):
        addr = 0x0040 + (randint(0, 15) * 4)
        val = randint(0, 0xFFFFFFFF)
        await tb.intf.write(addr, val)

    for _ in range(16):
        addr = randint(0, 15) * 4
        val = randint(0, 0xFFFFFFFF)
        await tb.intf.write(addr, val)
        if randint(0, 1):
            await tb.intf.read(addr, val)

@test()
async def test_dut_external(dut):
    tb = testbench(dut)
    await tb.cr.wait_clkn(200)
    await _exercise(tb)
    await tb.cr.end_test(200)


@test()
async def test_dut_nowait_packed(dut):
    """Queued transactions pack back-to-back on the A channel."""
    tb = testbench(dut)
    grants: list[int] = []
    start_soon(_monitor_grants(dut, grants))

    await tb.cr.wait_clkn(200)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    tb.intf.write_nowait(0x0010, x0)
    tb.intf.write_nowait(0x0014, x1)
    rx0 = tb.intf.read_nowait(0x0010, x0)
    rx1 = tb.intf.read_nowait(0x0014, x1)

    await tb.intf.wait()

    while tb.intf.count_rx:
        ret, tx_id = tb.intf.queue_rx.popleft()
        if tx_id == rx0:
            assert int.from_bytes(ret, "little") == x0
        elif tx_id == rx1:
            assert int.from_bytes(ret, "little") == x1

    assert len(grants) >= 4, f"expected 4 grants, saw {len(grants)}"
    max_gap = 2 * tb.period
    for prev, nxt in zip(grants, grants[1:]):
        gap = nxt - prev
        assert gap <= max_gap, f"grant gap {gap}ns exceeds {max_gap}ns ({grants})"

    await tb.cr.end_test(50)


@test()
async def test_dut_interleaved_no_waits(dut):
    """Interleaved write_nowait/read_nowait across four backpressure phases."""
    tb = testbench(dut)

    await tb.cr.wait_clkn(200)

    reset_val = 0x0  # external blockmem initialises to zero
    expected = {i * tb.incr: reset_val for i in range(tb.n_regs)}
    pending_reads: dict[int, int] = {}

    # blockmem is not cleared on rst; zero it so reads-before-write match the model
    for i in range(tb.n_regs):
        tb.intf.write_nowait(i * tb.incr, 0)
    await tb.intf.wait()

    n_ops = 300
    phases: tuple[tuple[str, int | None], ...] = (
        ("off", None),
        ("req", 0x0C1),
        ("rready", 0x0C2),
        ("both", 0x0C3),
    )

    for phase_name, seed in phases:
        tb.intf.disable_backpressure()
        if phase_name == "req":
            tb.intf.enable_backpressure(req=True, rready=False, seednum=seed)
        elif phase_name == "rready":
            tb.intf.enable_backpressure(req=False, rready=True, seednum=seed)
        elif phase_name == "both":
            tb.intf.enable_backpressure(req=True, rready=True, seednum=seed)

        for _ in range(n_ops):
            addr = randint(0, tb.n_regs - 1) * tb.incr
            if randint(0, 1):
                data = randint(0, tb.mask)
                tb.intf.write_nowait(addr, data)
                expected[addr] = data
            else:
                tx_id = tb.intf.read_nowait(addr)
                pending_reads[tx_id] = expected[addr]

        await tb.intf.wait()

    results: dict[int, int] = {}
    while tb.intf.count_rx:
        ret, tx_id = tb.intf.queue_rx.popleft()
        results[tx_id] = int.from_bytes(ret, "little")

    assert len(pending_reads) > 0, "random stream produced no reads"
    for tx_id, exp in pending_reads.items():
        got = results[tx_id]
        assert got == exp, (
            f"read tx_id={tx_id}: got 0x{got:08x}, expected 0x{exp:08x}"
        )

    await tb.cr.end_test(50)


@test()
async def test_dut_basic_run(dut):
    """Packed write_nowait then read_nowait across the external SRAM."""
    tb = testbench(dut)
    tb.intf.max_outstanding = 4

    await tb.cr.wait_clkn(200)

    x = [randint(0, (2**32) - 1) for _ in range(tb.n_regs)]
    for i in range(tb.n_regs):
        tb.intf.write_nowait(i * tb.incr, x[i])
#     await tb.intf.wait()
#     await tb.cr.end_test(50)
    for i in range(tb.n_regs):
        tb.intf.read_nowait(i * tb.incr, x[i])

    await tb.intf.wait()
    await tb.cr.end_test(50)


@test()
async def test_dut_nowait_packed_rready_backpressure(dut):
    """Queued traffic with random rready stalls against the external SRAM."""
    tb = testbench(dut)
    tb.intf.enable_backpressure(rready=True, seednum=0x0B4)

    await tb.cr.wait_clkn(200)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    tb.intf.write_nowait(0x0010, x0)
    tb.intf.write_nowait(0x0014, x1)
    rx0 = tb.intf.read_nowait(0x0010, x0)
    rx1 = tb.intf.read_nowait(0x0014, x1)
    await tb.intf.wait()

    results = {}
    while tb.intf.count_rx:
        ret, tx_id = tb.intf.queue_rx.popleft()
        results[tx_id] = int.from_bytes(ret, "little")

    assert results[rx0] == x0
    assert results[rx1] == x1

    await tb.cr.end_test(50)


@test()
async def test_dut_req_backpressure(dut):
    tb = testbench(dut)
    tb.intf.enable_backpressure(req=True)
    await tb.cr.wait_clkn(200)
    await _exercise(tb)
    await tb.cr.end_test(200)


@test()
async def test_dut_rready_backpressure(dut):
    tb = testbench(dut)
    tb.intf.enable_backpressure(rready=True)
    await tb.cr.wait_clkn(200)
    await _exercise(tb)
    await tb.cr.end_test(200)
