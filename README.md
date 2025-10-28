# OBI interface modules for Cocotb

GitHub repository: https://github.com/daxzio/cocotbext-obi

## Introduction

OBI (Open Bus Interface) simulation models for [cocotb](https://github.com/cocotb/cocotb).

The OBI protocol is defined by the OpenHW Group for use in RISC-V and other open-source processor designs.

## Features

- **ObiMaster**: Manager/Master driver for OBI protocol
- **ObiBus**: Bus signal container with auto-discovery
- **Wide data support**: Automatically splits data wider than bus into multiple transactions
- **Transaction IDs**: Supports pipelined transactions with ID tracking
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

### OBI Master

The `ObiMaster` class implements an OBI manager/master and is capable of generating read and write operations against OBI subordinates.

The master automatically handles data wider than the bus width by splitting transactions into multiple sequential OBI accesses at consecutive addresses. This allows seamless transfers of wide data values across narrower OBI interfaces.

To use these modules, import and connect to the DUT:

```python
from cocotbext.obi import ObiMaster, ObiBus

bus = ObiBus.from_prefix(dut, "s_obi")
obi_driver = ObiMaster(bus, dut.clk)
```

The first argument to the constructor accepts an `ObiBus` object. These objects are containers for the interface signals and include class methods to automate connections.

Once the module is instantiated, read and write operations can be initiated:

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

#### `ObiMaster` Constructor Parameters
* _bus_: `ObiBus` object containing OBI interface signals
* _clock_: Clock signal
* _timeout_cycles_: Maximum clock cycles to wait before timing out (optional, default `1000`). Set to `-1` to disable timeout.

#### Methods
* `wait()`: Blocking wait until all outstanding operations complete
* `write(addr, data, strb=-1, error_expected=False)`: Write _data_ (bytes or int) to _addr_, wait for result. If _data_ is wider than the bus width, it will automatically be split into multiple sequential OBI write accesses at consecutive addresses.
* `write_nowait(addr, data, strb=-1, error_expected=False)`: Write _data_ to _addr_, queue without waiting.
* `read(addr, data=bytes(), error_expected=False)`: Read bytes at _addr_. If _data_ supplied, verify it matches. If _data_ is wider than the bus width, it will automatically be split into multiple sequential OBI read accesses at consecutive addresses.
* `read_nowait(addr, data=bytes(), error_expected=False)`: Read bytes at _addr_, queue without waiting.

#### Error Handling

The ObiMaster includes exception control for error testing:

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

## Complete Example

```python
import cocotb
from cocotb.triggers import RisingEdge
from cocotbext.obi import ObiBus, ObiMaster

@cocotb.test()
async def test_obi(dut):
    # Create OBI master
    obi_bus = ObiBus.from_prefix(dut, "s_obi")
    obi_master = ObiMaster(obi_bus, dut.clk)
    
    # Reset
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    
    # Write some data
    await obi_master.write(0x00, 0x12345678)
    await obi_master.write(0x04, 0xABCDEF00)
    
    # Read back and verify
    await obi_master.read(0x00, 0x12345678)
    await obi_master.read(0x04, 0xABCDEF00)
    
    # Test 64-bit access on 32-bit bus (auto-splits)
    await obi_master.write(0x100, 0x123456789ABCDEF0)
    await obi_master.read(0x100, 0x123456789ABCDEF0)
```

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

