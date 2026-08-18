from random import randint

from cocotb import start_soon, test
from cocotb.triggers import RisingEdge
from cocotb.utils import get_sim_time

from interfaces.clkrst import ClkReset

from cocotbext.obi import ObiHost
from cocotbext.obi import ObiBus


def returned_val(read_op):
    return int.from_bytes(read_op, byteorder="little")


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

        obi_prefix = "s_obi"
        self.bus = ObiBus.from_prefix(dut, obi_prefix)
        clk_name = "clk"
        self.intf = ObiHost(self.bus, getattr(dut, clk_name))


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
        tb.intf.read_nowait(0x0000 + (z * tb.incr), y.to_bytes(tb.incr, "little"))

    for i in range(tb.n_regs):
        y = x[i] & tb.mask
        read_op = await tb.intf.read(0x0000 + (i * tb.incr))
        ret = returned_val(read_op)
        assert y == ret

    await tb.cr.end_test(50)


@test()
async def test_dut_grant_spacing(dut):
    """Back-to-back req&&gnt handshakes are at most 2 cycles apart when queued."""
    tb = testbench(dut, reset_sense=1)
    grants: list[int] = []
    start_soon(_monitor_grants(dut, grants))

    await tb.cr.wait_clkn(200)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    tb.intf.write_nowait(0x0010, x0)
    tb.intf.write_nowait(0x0014, x1)
    tb.intf.read_nowait(0x0010, x0)
    tb.intf.read_nowait(0x0014, x1)
    await tb.intf.wait()

    assert len(grants) >= 4, f"expected 4 grants, saw {len(grants)}"
    max_gap = 2 * tb.period
    for prev, nxt in zip(grants, grants[1:]):
        gap = nxt - prev
        assert gap <= max_gap, f"grant gap {gap}ns exceeds {max_gap}ns ({grants})"

    await tb.cr.end_test(50)


@test()
async def test_dut_nowait_packed(dut):
    """Queued transactions pack back-to-back on the A channel."""
    tb = testbench(dut, reset_sense=1)
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
    tb = testbench(dut, reset_sense=1)

    await tb.cr.wait_clkn(200)

    reset_val = 0x1  # field reset value in regblock.sv
    expected = {i * tb.incr: reset_val for i in range(tb.n_regs)}
    pending_reads: dict[int, int] = {}

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
async def test_dut_req_backpressure(dut):
    """Random A-channel req gaps; blocking read/write still succeed."""
    tb = testbench(dut, reset_sense=1)
    tb.intf.enable_backpressure(req=True, seednum=0x0B1)

    await tb.cr.wait_clkn(200)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    await tb.intf.write(0x0010, x0)
    await tb.intf.write(0x0014, x1)
    await tb.intf.read(0x0010, x0)
    await tb.intf.read(0x0014, x1)

    await tb.cr.end_test(50)


@test()
async def test_dut_rready_backpressure(dut):
    """Random R-channel rready stalls; blocking read/write still succeed."""
    tb = testbench(dut, reset_sense=1)
    tb.intf.enable_backpressure(rready=True, seednum=0x0B2)

    await tb.cr.wait_clkn(200)

    x0 = randint(0, 0xFFFFFFFF)
    x1 = randint(0, 0xFFFFFFFF)
    await tb.intf.write(0x0010, x0)
    await tb.intf.write(0x0014, x1)
    await tb.intf.read(0x0010, x0)
    await tb.intf.read(0x0014, x1)

    await tb.cr.end_test(50)


@test()
async def test_dut_nowait_packed_req_backpressure(dut):
    """Queued traffic with random req gaps on the A channel."""
    tb = testbench(dut, reset_sense=1)
    tb.intf.enable_backpressure(req=True, seednum=0x0B3)

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
async def test_dut_nowait_packed_rready_backpressure(dut):
    """Queued traffic with random rready stalls on the R channel."""
    tb = testbench(dut, reset_sense=1)
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
