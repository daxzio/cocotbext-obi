# cocotbext-obi Testing

The package ships a cocotb test suite that exercises the OBI VIP (host,
device, RAM, monitor) against small SystemVerilog tops. Tests are driven by
per-suite Makefiles that include cocotb's `Makefile.sim`.

## Prerequisites

```bash
cd cocotbext-obi
pip install -e .            # install the package
pip install -r requirements.txt

# A simulator (Icarus Verilog or Verilator) must be on PATH.
# Some suites regenerate RTL from RDL and need PeakRDL-etana:
pip install peakrdl-etana

# Optional: actually run the test_interface* suites (otherwise they skip)
pip install -e .[interface]
```

## Running the tests

From the repository root:

```bash
make test                  # all suites, SIM=icarus verilator
make test SIMS=icarus      # single simulator
make test_icarus           # convenience target
make test_verilator
```

A single suite:

```bash
cd tests/test_basic
make clean sim SIM=verilator
make clean sim SIM=icarus WAVES=1   # dump waves
```

Suites that generate RTL from RDL (via `../regblock.mak`):

```bash
cd tests/test_slverr
make etana                 # or: make regblock
make sim SIM=verilator
```

## Test suites

| Directory | What it covers |
|-----------|----------------|
| `test_basic` | Basic host read/write against a PeakRDL regblock (32-bit) |
| `test_basic_64` | 64-bit data-width variant |
| `test_slverr` | OBI `err` response handling (read-only / write-only violations, exception control) |
| `test_device` | `ObiDevice` / `ObiRam` / `MemoryRegion` targets, byte strobes, backpressure, `ObiMonitor` |
| `test_ram` | Bulk read/write against an `ObiDevice` sized with `size_bytes` |
| `test_memdump` | Memory prefill + read-back dump |
| `test_pipelining` | Multiple outstanding transactions (`max_outstanding`), in-order completion, backpressure |
| `test_addrmap` | Named + indexed register access via `AddressMap` / `addaddrmap()` (REGWIDTH 8/16/32) |
| `test_poll` | `ObiHost.poll()` against a PeakRDL busy/start handshake |
| `test_interface` | Same as `test_basic` via `ObiInterface` (skips without `cocotbext-interface`) |
| `test_interface_noid` | `ObiInterface` against a DUT with no `aid`/`rid` (skips without the extra) |

Pure-Python unit tests (no simulator):

```bash
pytest tests/test_format_addr.py -v
```

Shared helpers live in `tests/interfaces/clkrst.py` (`ClkReset`). Suites that
need it symlink `interfaces -> ../interfaces`.

## Writing a new test

```python
from cocotb import test
from interfaces.clkrst import ClkReset
from cocotbext.obi import ObiBus, ObiHost


class testbench:
    def __init__(self, dut, reset_sense=1, period=10):
        self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="rst")
        self.bus = ObiBus.from_prefix(dut, "s_obi")
        self.m = ObiHost(self.bus, dut.clk)


@test()
async def test_my_feature(dut):
    tb = testbench(dut)
    await tb.cr.wait_clkn(20)
    await tb.m.write(0x0000, 0x12345678)
    await tb.m.read(0x0000, 0x12345678)   # 2nd arg asserts the read value
    await tb.cr.end_test(20)
```

## Pipelining

`ObiHost(bus, clk, max_outstanding=N)` and `ObiDevice(bus, clk,
max_outstanding=N)` enable up to *N* outstanding transactions with strict
in-order completion. `max_outstanding=1` (default) uses a strictly sequential
request/response loop and is fully backward compatible. See
`tests/test_pipelining`.

## CI

`.github/workflows/test_checkin.yml` runs lint + mypy (`make lint` / `make mypy`,
both must pass), then a matrix of Python 3.9–3.13 × {icarus, verilator} ×
cocotb v1.9.2 / v2.0.1, and Python 3.10–3.14 × {icarus, verilator} × cocotb
master. Tag pushes trigger PyPI trusted publishing.
