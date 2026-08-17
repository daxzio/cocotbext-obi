# OBI interface modules for Cocotb

GitHub repository: https://github.com/daxzio/cocotbext-obi

## Introduction

OBI (Open Bus Interface) simulation models for [cocotb](https://github.com/cocotb/cocotb).

The OBI protocol is defined by the OpenHW Group for use in RISC-V and other open-source processor designs.

## Features

- **ObiHost**: Host/manager driver for OBI protocol
- **ObiBus**: Bus signal container with auto-discovery
- **Wide data support**: Automatically splits data wider than bus into multiple transactions
- **Transaction IDs**: Supports pipelined transactions with ID tracking
- **Multiple outstanding transactions**: Configurable pipeline depth with in-order completion
- **Error handling**: Full error response validation
- **Timeout support**: Configurable transaction timeouts

## Installation

Installation from pip (when available):

    $ pip install cocotbext-obi

Installation from git (latest development version):

    $ pip install https://github.com/daxzio/cocotbext-obi/archive/main.zip

Installation for active development:

    $ git clone https://github.com/daxzio/cocotbext-obi
    $ pip install -e cocotbext-obi

Optional `ObiInterface` extra (needs **cocotb 2.x**):

    $ pip install cocotbext-obi[interface]

## OBI Protocol Overview

OBI uses a two-phase handshake protocol:

**Request Phase (A-Channel):**
- `req` and `gnt` handshake for address/control transfer
- Manager asserts `req` with address and control signals
- Subordinate asserts `gnt` when ready to accept

**Response Phase (R-Channel):**
- `rvalid` and `rready` handshake for data transfer
- Subordinate asserts `rvalid` with response data
- Manager asserts `rready` when ready to accept

## Usage Example

### OBI Bus

The `ObiBus` is used to map to an OBI interface on the `dut`. Class methods `from_entity` and `from_prefix` are provided to facilitate signal name matching.

#### Required Signals:
* _req_ - Request valid
* _gnt_ - Grant (ready to accept)
* _addr_ - Address
* _we_ - Write enable
* _be_ - Byte enable
* _wdata_ - Write data
* _aid_ - Address/transaction ID
* _rvalid_ - Response valid
* _rready_ - Response ready
* _rdata_ - Read data
* _err_ - Error flag
* _rid_ - Response ID

### OBI Host

The `ObiHost` class implements an OBI host/manager and is capable of generating read and write operations against OBI devices.

The host automatically handles data wider than the bus width by splitting transactions into multiple sequential OBI accesses at consecutive addresses. This allows seamless transfers of wide data values across narrower OBI interfaces.

To use these modules, import and connect to the DUT:

```python
from cocotbext.obi import ObiHost, ObiBus

bus = ObiBus.from_prefix(dut, "s_obi")
obi_driver = ObiHost(bus, dut.clk)
```

The first argument to the constructor accepts an `ObiBus` object. These objects are containers for the interface signals and include class methods to automate connections.

Once the module is instantiated, read and write operations can be initiated:

`ObiMaster` is a deprecated subclass of `ObiHost` and remains available for existing testbenches.

```python
# Write operations
await obi_driver.write(0x1000, 0x12345678)  # Single 32-bit write
await obi_driver.write(0x2000, 0x123456789ABCDEF0)  # Auto-splits to two writes

# Read operations
data = await obi_driver.read(0x1000)  # Returns bytes
value = int.from_bytes(data, 'little')

# With data verification
await obi_driver.read(0x1000, 0x12345678)  # Raises exception if mismatch

# With error expectation
await obi_driver.write(0xBAD_ADDR, 0xFF, error_expected=True)
```

#### `ObiHost` Constructor Parameters
* _bus_: `ObiBus` object containing OBI interface signals
* _clock_: Clock signal
* _timeout_cycles_: Maximum clock cycles to wait before timing out (optional, default `1000`). Set to `-1` to disable timeout.
* _max_outstanding_: Maximum number of outstanding transactions (optional, default `1`). Set to `2` or higher to enable pipelined transactions.

#### Methods
* `wait()`: Blocking wait until all outstanding operations complete
* `write(addr, data, strb=-1, error_expected=False, length=-1, device=0, index=-1)`: Write _data_ (bytes or int) to _addr_ (int or register name when `addrmap` is configured), wait for result. If _data_ is wider than the bus width, it will automatically be split into multiple sequential OBI write accesses at consecutive addresses. After completion, `intra_delay` idle clock cycles are inserted (default `0`).
* `write_nowait(addr, data, strb=-1, error_expected=False, length=-1, device=0, index=-1)`: Write _data_ to _addr_, queue without waiting.
* `read(addr, data=bytes(), error_expected=False, length=-1, device=0, index=-1)`: Read bytes at _addr_ (int or register name). If _data_ supplied, verify it matches. If _data_ is wider than the bus width, it will automatically be split into multiple sequential OBI read accesses at consecutive addresses. After completion, `intra_delay` idle clock cycles are inserted (default `0`).
* `read_nowait(addr, data=bytes(), error_expected=False, length=-1, device=0, index=-1)`: Read bytes at _addr_, queue without waiting.
* `poll(addr, data=bytes(), device=0, index=-1)`: Repeatedly read _addr_ until the returned data equals _data_.
* `addaddrmap(addrmap, device=0)`: Register a name-to-address map. Preferred over direct assignment because it updates log column alignment.
* `format_addr(addr, device=0)`: Reverse lookup — return the register name for _addr_, or `0x........` if unmapped.

#### Error Handling

The `ObiHost` includes exception control for error testing:

* `exception_enabled`: When True (default), raises exceptions on unexpected errors. When False, logs warnings and sets `exception_occurred` flag.
* `exception_occurred`: Boolean flag set when an error occurs unexpectedly.

```python
# Normal operation - exceptions enabled
await obi.write(read_only_addr, data, error_expected=True)  # OK

# For testing error detection without exceptions
obi.exception_enabled = False
await obi.write(read_only_addr, data, error_expected=False)
assert obi.exception_occurred == True  # Error was detected
```

### OBI Device Models

Three device/target models are provided for building self-contained
testbenches (no RTL DUT required - the host and device BFMs can drive a
shared set of pins):

* **`ObiDevice`** - a responder backed by a memory *target* (any object exposing
  async `read`/`write`, e.g. a `MemoryRegion`). Override `_read`/`_write` for
  custom behaviour.
* **`ObiRam`** - `ObiDevice` pre-mixed with a sparse in-memory `Memory` store.
* **`ObiMonitor`** - a passive monitor that records `ObiTransaction` objects and
  can optionally check that bus signals only change on clock edges
  (`enable_check_sync()` / `disable_check_sync()`).

`ObiSlave` is a deprecated subclass of `ObiDevice` and remains available for existing testbenches.

```python
from cocotbext.obi import ObiBus, ObiHost, ObiDevice, ObiRam, MemoryRegion

bus = ObiBus.from_prefix(dut, "s_obi")
host = ObiHost(bus, dut.clk)

# Memory-region-backed device
device = ObiDevice(bus, dut.clk)
device.target = MemoryRegion(2**device.address_width)

# ...or a RAM device in one line
ram = ObiRam(bus, dut.clk)
```

`ObiDevice`/`ObiRam` accept `size_bytes=` to size an auto-created backing store
and `max_outstanding=` to match the host's pipeline depth.

### Address Maps

The `ObiHost` supports address mapping through its `addrmap` attribute, an
[`AddressMap`](#addressmap) instance. Register names can be used instead of
numeric addresses in `read()`, `write()`, `read_nowait()`, `write_nowait()`, and
`poll()`.

Configure the map with `addaddrmap()` or by assigning directly to a device index:

```python
from cocotbext.obi import ObiHost, ObiBus

bus = ObiBus.from_prefix(dut, "s_obi")
host = ObiHost(bus, dut.clk)

# Preferred: addaddrmap() updates log column alignment automatically
host.addaddrmap({
    "STATUS": 0x00,
    "BUSY": 0x04,
    "CONFIG": 0x08,
    "INTERRUPT": 0x0c,
})

# Equivalent for device 0:
# host.addrmap[0] = { ... }

await host.write("STATUS", 0x12)
await host.read("CONFIG")
await host.poll("STATUS", 0x1)

# Indexed access using string format
await host.read("STATUS[0]", 0x12)
await host.read("STATUS[1]", 0x34)

# Indexed access using the index parameter (useful with variables)
for i in range(4):
    await host.write("STATUS", data[i], index=i)
    await host.read("STATUS", expected[i], index=i)
```

When a map is configured, transaction logs show register names instead of raw
addresses (for example `Read  STATUS    : 0x00000012` rather than
`Read  0x00000000: 0x00000012`). See [tests/test_addrmap](tests/test_addrmap)
for a complete cocotb example.

**Indexed register access:** for register arrays, use either bracket notation
(`"STATUS[0]"`, `"STATUS[1]"`, …) or the `index` parameter
(`read("STATUS", data, index=0)`). Both add `index * wbytes` to the base address,
where `wbytes` is the bus data width in bytes.

### AddressMap

`AddressMap` is a protocol-agnostic helper for name-to-address resolution on
memory-mapped register maps. It is used internally by `ObiHost` (via the
`addrmap` attribute) and is also exported for standalone use.

Import:

```python
from cocotbext.obi import AddressMap
```

#### Data model

`AddressMap` is a `dict` subclass keyed by **device index**. Each value is a
plain `dict` mapping **register name** (`str`) to **byte address** (`int`):

```
AddressMap
├── 0 → {"STATUS": 0x00, "CONFIG": 0x08, ...}   # device 0
└── word_bytes, multi_device, _label_width      # configuration
```

Constructor parameters:

* _word_bytes_: bus data width in bytes (default `4`). Used for indexed register
  offsets and reverse lookup alignment.
* _multi_device_: reserve extra column width in log output (default `False`).
  `ObiHost` always constructs the map with `multi_device=False`.

#### Forward lookup (name → address)

`resolve(addr, device=0, index=-1)` converts a register name or integer address
to a byte address:

* If `addr` is an `int`, it is returned unchanged (plus any `index` offset).
* If `addr` is a `str`, the base name is looked up in the map for _device_.
  Bracket notation adds `N * word_bytes` for each `[N]` suffix
  (e.g. `"AES_KEY_SHARE0[3]"` → base + 3 × word_bytes).
* If `index != -1`, `index * word_bytes` is added after name resolution.

```python
am = AddressMap(word_bytes=4)
am.add({"STATUS": 0x00, "CONFIG": 0x08})

am.resolve(0x08)              # 0x08  (integer passthrough)
am.resolve("STATUS")          # 0x00
am.resolve("STATUS[2]")       # 0x08
am.resolve("STATUS", index=1) # 0x04
```

#### Reverse lookup (address → name)

`format(addr, device=0)` returns the register name for a byte address. When the
address falls within a mapped register array (aligned to `word_bytes`), bracket
notation is used for non-zero indices. Unmapped addresses are formatted as
`0x........`.

```python
am.format(0x00)   # "STATUS"
am.format(0x08)   # "STATUS[2]"  (if STATUS base is 0x00, word_bytes=4)
am.format(0x99)   # "0x00000099" (unmapped)
```

#### Registering maps

* `add(addrmap, device=0)`: store a name→address dict for _device_ and recompute
  log column width. This is what `ObiHost.addaddrmap()` delegates to.
* Direct assignment `am[device] = {...}` also works (dict subclass), but does not
  update column width unless `add()` or `_update_label_width()` is called.

#### Log formatting

`format_col(label, prefix="")` pads a register label so read/write data columns
align in log output. `ObiHost` uses this internally when logging transactions.

#### Standalone example

```python
from cocotbext.obi import AddressMap

REGS = {
    "STATUS": 0x00,
    "BUSY": 0x04,
    "CONFIG": 0x08,
}

am = AddressMap(word_bytes=4)
am.add(REGS)

addr = am.resolve("CONFIG")
label = am.format(addr)        # "CONFIG"
col = am.format_col(label)     # padded for aligned columns
```

Unit tests for reverse lookup live in
[tests/test_format_addr.py](tests/test_format_addr.py). Cocotb integration tests
are in [tests/test_addrmap](tests/test_addrmap). Polling is covered in
[tests/test_poll](tests/test_poll).

### Error Types

The response-channel `err` bit maps to `OBIError` (with `InvalidAccess`) and the
`ObiResp` enum, exported for use in custom devices.

## Complete Example

```python
import cocotb
from cocotb.triggers import RisingEdge
from cocotbext.obi import ObiBus, ObiHost

@cocotb.test()
async def test_obi(dut):
    # Create OBI host
    obi_bus = ObiBus.from_prefix(dut, "s_obi")
    obi_host = ObiHost(obi_bus, dut.clk)
    
    # Reset
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    
    # Write some data
    await obi_host.write(0x00, 0x12345678)
    await obi_host.write(0x04, 0xABCDEF00)
    
    # Read back and verify
    await obi_host.read(0x00, 0x12345678)
    await obi_host.read(0x04, 0xABCDEF00)
    
    # Test 64-bit access on 32-bit bus (auto-splits)
    await obi_host.write(0x100, 0x123456789ABCDEF0)
    await obi_host.read(0x100, 0x123456789ABCDEF0)
```

## Pipelined Transactions

OBI supports multiple outstanding transactions with **strict in-order completion**. You can enable pipelining by setting `max_outstanding` parameter to 2 or higher:

```python
from cocotbext.obi import ObiBus, ObiHost, ObiDevice

# Create host with pipeline depth of 4
host = ObiHost(bus, clock, max_outstanding=4)

# Create device with same pipeline depth
device = ObiDevice(bus, clock, max_outstanding=4)

# Queue multiple writes - they will be pipelined
await host.write(0x1000, 0x11111111)
await host.write(0x1004, 0x22222222)
await host.write(0x1008, 0x33333333)
await host.write(0x100C, 0x44444444)

# Or queue them without waiting
host.write_nowait(0x2000, 0xAAAA0000)
host.write_nowait(0x2004, 0xBBBB1111)
# ... continue queuing
await host.wait()  # Wait for all to complete
```

**Key points:**
- `max_outstanding=1` (default): Strictly sequential behavior, fully backward compatible
- `max_outstanding > 1`: Enables pipelining for better throughput
- Host and device should use matching `max_outstanding` values for best performance
- Responses are **guaranteed** to return in the exact order requests were accepted (OBI requirement)
- Backpressure is automatic: when the pipeline is full, new requests wait until space is available

### Optional `ObiInterface` (cocotbext-interface)

[`cocotbext-interface`](https://github.com/RasmusGOlsen/cocotbext-interface) is **not** required to use this package. `pip install cocotbext-obi` still only needs `cocotb`. Hosts, devices, monitors, and `ObiBus` work as they always have.

If you want a SystemVerilog-style `Interface` connection instead of `ObiBus`, install the extra (needs **cocotb 2.x**):

    $ pip install cocotbext-obi[interface]

`ObiInterface` is a drop-in for `ObiBus`: same signal names, `from_prefix` / `from_entity`, and the same `ObiHost` / `ObiMonitor` / `ObiDevice` classes.

    from cocotbext.obi import ObiInterface, ObiHost, HAVE_COCOTBEXT_INTERFACE

    bus = ObiInterface.from_prefix(dut, "s_obi")
    obi_driver = ObiHost(bus, dut.clk)

`HAVE_COCOTBEXT_INTERFACE` is `True` only when both cocotb 2.x handle types and `cocotbext-interface` imported successfully. Otherwise `import cocotbext.obi` still succeeds, but constructing `ObiInterface` raises `ImportError` with the install command. Tests that need the extra skip when the flag is false (`tests/test_interface`, `tests/test_interface_noid`).

## Testing

### Package Tests

The `cocotbext-obi` package includes its own test suite:

```bash
cd tests/test_slverr

# Generate RTL
make etana

# Run with Verilator
make sim SIM=verilator

# Run with Icarus
make sim SIM=icarus
```

**Test Results:** ✅ 3/3 PASS (Verilator and Icarus)

### Integration Tests

See the PeakRDL-etana `tests/` directory for comprehensive testbenches using cocotbext-obi across 30+ test scenarios.

## License

MIT License. See LICENSE file for details.

## References

- [OpenHW Group OBI Specification](https://github.com/openhwgroup/obi)
- [Cocotb Documentation](https://docs.cocotb.org/)
- [PeakRDL-etana](https://github.com/daxzio/PeakRDL-etana) - Uses this package for OBI testing

