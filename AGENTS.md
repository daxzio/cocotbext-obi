# AGENTS.md

Guidance for AI coding agents working in **cocotbext-obi**.

## What this project is

`cocotbext-obi` is a Python package providing **OBI (Open Bus Interface)
verification IP for [cocotb](https://github.com/cocotb/cocotb)**. OBI is the
OpenHW Group bus used in RISC-V and other open-source designs. It is a sibling
/ loose fork of `cocotbext-apb` and mirrors that project's structure.

- PyPI name: `cocotbext-obi` - import path: `cocotbext.obi`
- Namespace package under `cocotbext/obi/`
- Runtime dependency: `cocotb>=1.9.0` only (the package is **standalone** - it
  does not depend on `cocotbext-apb`)
- License: MIT
- Version lives in `cocotbext/obi/version.py`

## OBI protocol quick reference

Two-phase handshake on a single channel set:

- **Request (A) channel**: `req`/`gnt` handshake carrying `addr`, `we`, `be`,
  `wdata`, `aid`. A transfer happens on each cycle where `req && gnt`.
- **Response (R) channel**: `rvalid`/`rready` handshake carrying `rdata`,
  `err`, `rid`. Responses are returned **in order**.

## Layout

```
cocotbext/obi/       # Library source (standalone)
tests/               # cocotb testbenches
  interfaces/        # Shared helpers: clkrst.py (ClkReset)
  test_*/            # Per-suite dirs (Makefile + test_dut.py + RTL)
scripts/             # update_copyright_year.py
.github/workflows/   # CI (lint, mypy, sim matrix, PyPI release)
setup.py / setup.cfg # Packaging + pytest/flake8 config
Makefile             # test / lint / mypy / format / checks / dist / release
```

No `pyproject.toml`, `docs/`, `examples/`, or `pyuvm/` (pyuvm is intentionally
out of scope for OBI).

## Public API (`cocotbext/obi/__init__.py`)

- Buses: `ObiBus` (alias `OBIBus`), `ObiInterface`
- Feature flag: `HAVE_COCOTBEXT_INTERFACE`
- VIPs (all inherit `ObiBase`): `ObiHost`, `ObiDevice`, `ObiRam`,
  `ObiMonitor` (+ `ObiTransaction`). Legacy subclasses `ObiMaster`/`OBIMaster`
  (`ObiHost`) and `ObiSlave` (`ObiDevice`) are also exported.
- Errors: `OBIError`, `InvalidAccess`, `ObiResp`
- Address map: `AddressMap`
- Memory model: `Memory`, `SparseMemory`, `BuddyAllocator`, `MemoryInterface`,
  `Window`, `WindowPool`, `Region`, `MemoryRegion`, `SparseMemoryRegion`,
  `PeripheralRegion`, `AddressSpace`, `Pool`

`ObiInterface` (`obi_interface.py`) is the only feature needing an optional
dependency, `cocotbext-interface`. It is **never** a hard requirement:
`install_requires` is `cocotb` alone, and the dep is offered purely as an
opt-in extra (`pip install cocotbext-obi[interface]`).

The contract when the dep is absent:
- `import cocotbext.obi` still succeeds, and every other class works normally.
- `ObiInterface` is still exported, but is a stub whose construction raises a
  helpful `ImportError` naming the install command.
- `HAVE_COCOTBEXT_INTERFACE` (exported) is `False`, so tests and user code can
  branch or skip. The `test_interface*` suites use it to skip, not fail.

Preserve this behaviour: never import `cocotbext.interface` at module scope
outside the guarded `try` in `obi_interface.py`.

When adding public API, export it here.

## Key modules

| File | Responsibility |
|------|----------------|
| `obi_bus.py` | `ObiBus` signal container (`req/gnt/addr/we/be/wdata/aid/rvalid/rready/rdata/err/rid`) |
| `obi_interface.py` | Optional `ObiInterface` (cocotbext-interface); stub when the extra is absent |
| `bus.py` | Fork of cocotb's bus helper (`from_prefix`/`from_entity`) |
| `obi_base.py` | `ObiBase`: width config, logging, backpressure (`delay`), seed |
| `obi_host.py` | `ObiHost`: request/response driver, wide-data splitting, `AddressMap`, `poll`, pipelining |
| `obi_master.py` | Legacy `ObiMaster(ObiHost)` alias (`OBIMaster` too) |
| `obi_device.py` | `ObiDevice`: memory-backed responder, overridable `_read`/`_write`, pipelining |
| `obi_slave.py` | Legacy `ObiSlave(ObiDevice)` alias |
| `obi_ram.py` | `ObiRam` = `ObiDevice` + `Memory` mixin (sparse-backed) |
| `obi_monitor.py` | `ObiMonitor` passive monitor + `enable_check_sync()`/`disable_check_sync()` |
| `address_map.py` | `AddressMap`: register-name <-> address (`add`/`resolve`/`format`) |
| `address_space.py` | Hierarchical async memory model (ported from A. Forencich) |
| `memory.py` / `sparse_memory.py` | Sync memory accessor + 4 KiB-block sparse store |
| `buddy_allocator.py` | Window/region allocation |
| `constants.py` / `utils.py` | `OBIError`/`InvalidAccess`/`ObiResp`; X/Z resolution + hexdump |

Preserve the Alex Forencich copyright headers in `memory.py`,
`sparse_memory.py`, `address_space.py`, `buddy_allocator.py`. Daxzio files use
the MIT header.

## Architecture notes / conventions

- `ObiHost`, `ObiDevice`, `ObiMonitor` all inherit `ObiBase`.
- **Pipelining**: `max_outstanding=1` (default) runs the proven strictly
  sequential path (`_run_sequential`). `max_outstanding>1` runs split
  request/response coroutines (`_run_request`/`_run_response` on the host,
  `_run_pipelined` on the device). The pipelined handshake deliberately inserts
  a one-cycle req/grant gap on **both** sides to avoid a delta-cycle race where
  a lingering `req` is granted twice - keep that invariant if you touch it.
- Responses are matched **in order** via the host's `outstanding` deque and
  `queue_rx` tx-ids; the code does not rely on `aid`/`rid` for matching (aid
  width is often 1 bit in the test tops).
- Custom devices: subclass `ObiDevice` (or legacy `ObiSlave`), override
  `async def _read()` / `async def _write()` (see `ObiRam`).
- Register-name access: `host.addaddrmap({...})` then
  `await host.write("REG_NAME", value)`.
- `ObiHost.intra_delay` (default `0`) inserts idle clock cycles after each
  completed `write()` / `read()`.

## Testbench pattern

```python
from cocotbext.obi import ObiBus, ObiHost
bus = ObiBus.from_prefix(dut, "s_obi")   # maps dut.s_obi_req, dut.s_obi_addr, ...
host = ObiHost(bus, dut.clk)
await host.write(0x0000, 0x12345678)
await host.read(0x0000, 0x12345678)      # 2nd arg asserts the value
```

## Running tests

Requires a simulator (Icarus/Verilator) on PATH. Pure-Python unit tests
(`tests/test_format_addr.py`) do not need a simulator.

```bash
make test                 # all suites, SIM=icarus verilator
make test SIMS=icarus
cd tests/test_basic && make clean sim SIM=verilator   # single suite
pytest tests/test_format_addr.py -v                   # AddressMap unit tests
```

See `TESTING.md` for the suite inventory. RTL-generating suites use
`../regblock.mak` (`make etana` / `make regblock`, needs PeakRDL-etana).
The two `test_interface*` suites are in `make test`. They need
`cocotbext-interface` (`pip install -e .[interface]`) to actually run; without
it they skip rather than fail. `test_interface_noid` covers the
absent-optional-signal path (`aid`/`rid`) against a pin-only DUT.

## Code quality - run before finishing

```bash
make checks     # = make format + make lint + make mypy
make format     # black cocotbext tests scripts   (black pinned 26.5.1)
make lint       # pyflakes + ruff on cocotbext/
make mypy       # mypy cocotbext/obi  (.mypy.ini); must pass (no || true)
make pre-commit # pre-commit run --all-files
```

flake8 config in `setup.cfg` (`max-line-length = 119`, `__init__.py:F401`).
Ruff config in `ruff.toml` (line-length 119, target-version py310).

## Packaging & release

- `make dist` -> `python -m build` + `twine check`.
- `make release GIT_TAG=x.y.z` tags, writes `version.py`, commits, pushes; CI
  publishes to PyPI (trusted publishing) on tag push.

## CI (`.github/workflows/test_checkin.yml`)

Runs on push/PR + weekly cron: `run_lint` (`make lint` + `make mypy`; mypy
failures fail the job), then a matrix of Python 3.10–3.13 × cocotb v1.9.2 /
v2.0.1, and 3.10–3.14 × cocotb master, × icarus/verilator. Tag pushes trigger
PyPI trusted publishing. Simulator builds are cached via the `setup_*.yml`
reusable workflows.

## Gotchas

- BFM-to-BFM suites (`test_device`, `test_ram`, `test_memdump`, `test_pipelining`)
  use a loopback DUT (`s_obi` host / `m_obi` device); `test_device/dut.sv` is the
  shared top for the first three.
- The pipelined host/device paths are cycle-level and must be validated with a
  real simulator (`make test`); logic changes there cannot be checked by
  import/compile alone.
- Only create commits when explicitly asked.
