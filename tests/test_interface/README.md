# test_interface — OBI with cocotbext-interface style

This directory runs the same test flow as `test_basic` but connects to the DUT
using the **cocotbext-interface** style (`ObiInterface.from_prefix`) instead of
`ObiBus.from_prefix`.

## Prerequisites

Needs the optional `cocotbext-interface` dependency:

```bash
pip install -e .[interface]
```

`cocotbext-interface` is never required by `cocotbext-obi` itself. Without it,
`import cocotbext.obi` still works and these tests **skip** rather than fail
(they gate on the exported `HAVE_COCOTBEXT_INTERFACE` flag).

This suite is included in the root `make test` list.

## Run

```bash
make SIM=icarus
```

## What this demonstrates

- **ObiInterface** (`cocotbext.obi.obi_interface`) uses the cocotbext-interface
  `Interface` base and `from_prefix(entity, prefix)` for connection
  (e.g. `s_obi_req`, `s_obi_addr`, …).
- The same **ObiHost** and **ObiMonitor** are used unchanged; they see a
  bus-compatible object (`_signals`, `_optional_signals`, `hasattr`-based
  optional signal detection) so no VIP changes were required.
