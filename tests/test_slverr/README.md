# OBI Error Response Test (test_slverr)

## Overview

This test verifies that the OBI interface correctly generates error responses when accessing registers incorrectly (read-only/write-only violations).

Based on the equivalent test in cocotbext-apb.

---

## Test Description

### Registers Defined (regblock.rdl)

```rdl
reg r_rw {
    field { sw=rw; hw=na; } f[31:0] = 40;  // Read-write register
}

reg r_r {
    field { sw=r; hw=na; } f[31:0] = 80;   // Read-only register
}

reg r_w {
    field { sw=w; hw=r; } f[31:0] = 100;   // Write-only register
}
```

### Test Cases

**1. test_dut_proper_err** - Normal error handling with `error_expected=True`
- ✅ Read/write to r_rw (should work)
- ✅ Read r_r (should work)
- ✅ Write to r_r with `error_expected=True` (should error correctly)
- ✅ Read from r_w with `error_expected=True` (should error correctly)

**2. test_dut_incorrect_write_err** - Detect unexpected write errors
- Disable exceptions: `exception_enabled = False`
- Write to read-only register with `error_expected=False`
- Verify `exception_occurred = True` (error was detected)

**3. test_dut_incorrect_read_err** - Detect unexpected read errors
- Disable exceptions: `exception_enabled = False`
- Read from write-only register with `error_expected=False`
- Verify `exception_occurred = True` (error was detected)

---

## How to Run

### Generate RTL
```bash
make etana  # Generates with OBI interface and error responses
```

### Run Tests
```bash
# With Verilator
make clean sim SIM=verilator

# With Icarus
make clean sim SIM=icarus
```

### Expected Results
```
TESTS=3 PASS=3 FAIL=0 SKIP=0
```

---

## Key Features Demonstrated

### Error Response Generation
The RTL is generated with:
```bash
peakrdl etana regblock.rdl --cpuif obi-flat --err-if-bad-rw --rename regblock
```

`--err-if-bad-rw` enables error responses for:
- Writing to read-only registers → `s_obi_err = 1`
- Reading from write-only registers → `s_obi_err = 1`

### OBI Error Signaling
```systemverilog
// OBI Response Channel
output logic s_obi_rvalid   // Response valid
output logic s_obi_err      // Error flag (1 = error)
output logic [31:0] s_obi_rdata
```

### Exception Control in Driver
```python
# Enable exceptions (default)
obi_host.exception_enabled = True
await obi_host.write(bad_addr, data, error_expected=False)
# Raises exception if error occurs

# Disable exceptions
obi_host.exception_enabled = False
await obi_host.write(bad_addr, data, error_expected=False)
# Sets exception_occurred flag, logs warning, no exception raised
```

---

## Files

```
test_slverr/
├── regblock.rdl           - Register definitions
├── regblock.sv            - Generated RTL (from 'make etana')
├── test_dut.py            - Three test cases
├── Makefile               - Build and sim control
├── interfaces/
│   └── clkrst.py          - Clock/reset utilities
└── README.md              - This file
```

---

## Test Results

**Verilator:**
```
test_dut.test_dut_proper_err:           PASS
test_dut.test_dut_incorrect_write_err:  PASS
test_dut.test_dut_incorrect_read_err:   PASS

TESTS=3 PASS=3 FAIL=0 SKIP=0
```

**Icarus:**
```
test_dut.test_dut_proper_err:           PASS
test_dut.test_dut_incorrect_write_err:  PASS
test_dut.test_dut_incorrect_read_err:   PASS

TESTS=3 PASS=3 FAIL=0 SKIP=0
```

---

## Comparison with APB Test

| Aspect | APB (cocotbext-apb) | OBI (cocotbext-obi) |
|--------|---------------------|---------------------|
| **RDL File** | Same | Same |
| **Test Logic** | Same | Same |
| **Error Flag** | `pslverr` | `err` |
| **Exception Control** | ✅ | ✅ |
| **Results** | 3/3 PASS | 3/3 PASS |

Both implementations are identical in behavior!

---

## Usage Example

```python
from cocotbext.obi import ObiHost, ObiBus

# Create driver
bus = ObiBus.from_prefix(dut, "s_obi")
obi = ObiHost(bus, dut.clk)

# Normal operation - exceptions enabled (default)
await obi.write(0x4, 81, error_expected=True)  # OK - error expected and occurred

# Disable exceptions for testing
obi.exception_enabled = False
await obi.write(0x4, 81, error_expected=False)  # Sets exception_occurred flag
assert obi.exception_occurred == True  # Verify error was detected
```

---

## Verification

This test verifies that:
1. ✅ OBI error signaling works correctly
2. ✅ Error responses are generated for access violations
3. ✅ Driver detects and reports errors properly
4. ✅ Exception control mechanism works
5. ✅ Compatible with both Verilator and Icarus

**Status:** ✅ All tests pass






