"""

Copyright (c) 2024-2025 Daxzio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

import math
import logging
from collections import deque
from typing import Deque, Tuple, Any, Union

from cocotb import start_soon
from cocotb.triggers import RisingEdge, Event


class ObiMaster:
    """OBI (Open Bus Interface) Manager/Master driver
    
    Implements the manager side of the OBI protocol from OpenHW Group.
    Supports automatic splitting of wide data into multiple bus-width transactions.
    """
    
    def __init__(
        self, bus, clock, name="master", timeout_cycles=1000, **kwargs
    ) -> None:
        self.name = name
        self.bus = bus
        self.clock = clock
        self.timeout_cycles = timeout_cycles  # -1 disables timeout
        self.exception_enabled = True
        self.exception_occurred = False
        
        if bus._name:
            self.log = logging.getLogger(f"cocotb.obi_{name}.{bus._name}")
        else:
            self.log = logging.getLogger(f"cocotb.obi_{name}")
        self.log.setLevel(logging.INFO)
        self.log.info(f"OBI {self.name}")
        
        self.address_width = len(self.bus.addr)
        self.wwidth = len(self.bus.wdata)
        self.rwidth = len(self.bus.rdata)
        self.rbytes = int(self.rwidth / 8)
        self.wbytes = int(self.wwidth / 8)
        self.rdata_mask = 2**self.rwidth - 1
        self.wdata_mask = 2**self.wwidth - 1
        self.be_width = len(self.bus.be)

        self.log.info(f"OBI {self.name} configuration:")
        self.log.info(f"  Address width: {self.address_width} bits")
        self.log.info(f"  Data width: {self.wwidth} bits ({self.wbytes} bytes)")
        self.log.info(f"  BE width: {self.be_width} bits")
        if self.timeout_cycles >= 0:
            self.log.info(f"  Timeout: {self.timeout_cycles} clock cycles")
        else:
            self.log.info("  Timeout: disabled")

        self.log.info("OBI signals:")
        for sig in sorted(
            list(set().union(self.bus._signals, self.bus._optional_signals))
        ):
            if hasattr(self.bus, sig):
                self.log.info(f"  {sig} width: {len(getattr(self.bus, sig))} bits")
            else:
                self.log.info(f"  {sig}: not present")

        self.queue_tx: Deque[Tuple[bool, int, bytes, int, bool, int]] = deque()
        self.queue_rx: Deque[Tuple[bytes, int]] = deque()
        self.tx_id = 0

        self.sync = Event()

        self._idle = Event()
        self._idle.set()

        # Initialize request channel signals
        self.bus.req.value = 0
        self.bus.addr.value = 0
        self.bus.we.value = 0
        self.bus.be.value = 0
        self.bus.wdata.value = 0
        self.bus.aid.value = 0
        
        # Initialize response channel signals (manager side)
        self.bus.rready.value = 1  # Always ready to accept responses

        self._run_coroutine_obj: Any = None
        self._restart()

    async def write(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
        length: int = -1,
    ) -> None:
        """Write data to OBI subordinate
        
        Automatically splits wide data into multiple bus-width transactions.
        
        Args:
            addr: Byte address
            data: Data to write (int or bytes)
            strb: Byte enable mask (default: all bytes enabled)
            error_expected: Whether an error response is expected
        """
        self.write_nowait(addr, data, strb, error_expected, length=length)
        await self._idle.wait()

    def write_nowait(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
        length: int = -1,
    ) -> None:
        """Queue write without waiting for completion"""
        # Calculate how many bus-width transactions needed
        if isinstance(data, int):
            if length and length > 0:
                num_transactions = math.ceil((length * 8) / self.wwidth)
            else:
                num_transactions = (
                    math.ceil(data.bit_length() / self.wwidth)
                    if data.bit_length() > 0
                    else 1
                )
        else:
            if length and length > 0:
                num_transactions = math.ceil(length / self.wbytes)
            else:
                num_transactions = math.ceil(len(data) / self.wbytes)
        
        # Split into multiple bus-width transactions if needed
        for i in range(num_transactions):
            addrb = addr + i * self.wbytes
            if isinstance(data, int):
                subdata = (data >> self.wwidth * i) & self.wdata_mask
                datab = subdata.to_bytes(self.wbytes, "little")
            else:
                datab = data[i * self.wbytes : (i + 1) * self.wbytes]
            self.tx_id += 1
            self.queue_tx.append((True, addrb, datab, strb, error_expected, self.tx_id))
        
        self.sync.set()
        self._idle.clear()

    async def read(
        self,
        addr: int,
        data: Union[int, bytes] = bytes(),
        error_expected: bool = False,
        length: int = -1,
    ) -> bytes:
        """Read data from OBI subordinate
        
        Automatically splits wide data into multiple bus-width transactions.
        
        Args:
            addr: Byte address
            data: Expected data for verification (optional)
            error_expected: Whether an error response is expected
            
        Returns:
            Read data as bytes
        """
        rx_id = self.read_nowait(addr, data, error_expected, length=length)
        found = False
        while not found:
            while self.queue_rx:
                ret, tx_id = self.queue_rx.popleft()
                if rx_id == tx_id:
                    found = True
                    break
            await RisingEdge(self.clock)
        await self._idle.wait()
        return ret

    def read_nowait(
        self,
        addr: int,
        data: Union[int, bytes] = bytes(),
        error_expected: bool = False,
        length: int = -1,
    ) -> int:
        """Queue read without waiting for completion"""
        # Calculate how many bus-width transactions needed
        if isinstance(data, int):
            if length and length > 0:
                num_transactions = math.ceil((length * 8) / self.rwidth)
            else:
                num_transactions = (
                    math.ceil(data.bit_length() / self.rwidth)
                    if data.bit_length() > 0
                    else 1
                )
        else:
            if length and length > 0:
                num_transactions = math.ceil(length / self.rbytes)
            else:
                num_transactions = 1
        
        # Split into multiple bus-width transactions if needed
        for i in range(num_transactions):
            addrb = addr + i * self.rbytes
            if isinstance(data, int):
                subdata = (data >> self.rwidth * i) & self.rdata_mask
                datab = subdata.to_bytes(self.rbytes, "little")
            else:
                datab = data
            self.tx_id += 1
            self.queue_tx.append((False, addrb, datab, -1, error_expected, self.tx_id))
        
        self.sync.set()
        self._idle.clear()
        return self.tx_id

    def _restart(self) -> None:
        if self._run_coroutine_obj is not None:
            self._run_coroutine_obj.kill()
        self._run_coroutine_obj = start_soon(self._run())

    @property
    def count_tx(self) -> int:
        return len(self.queue_tx)

    @property
    def empty_tx(self) -> bool:
        return not self.queue_tx

    @property
    def count_rx(self) -> int:
        return len(self.queue_rx)

    @property
    def empty_rx(self) -> bool:
        return not self.queue_rx

    @property
    def idle(self) -> bool:
        return self.empty_tx and self.empty_rx

    def clear(self) -> None:
        """Clears the RX and TX queues"""
        self.queue_tx.clear()
        self.queue_rx.clear()

    async def wait(self) -> None:
        """Wait for idle"""
        await self._idle.wait()

    async def _run(self):
        await RisingEdge(self.clock)
        while True:
            while not self.queue_tx:
                self._idle.set()
                self.sync.clear()
                await self.sync.wait()

            (
                write,
                addr,
                data,
                strb,
                error_expected,
                tx_id,
            ) = self.queue_tx.popleft()

            if addr < 0 or addr >= 2**self.address_width:
                raise ValueError("Address out of range")

            # --- OBI Request Phase (A-channel) ---
            # Set request signals
            self.bus.req.value = 1
            self.bus.we.value = write
            self.bus.addr.value = addr
            self.bus.aid.value = tx_id & ((1 << len(self.bus.aid)) - 1)  # Truncate to ID width

            if write:
                data_int = int.from_bytes(data, byteorder="little")
                self.log.info(f"Write addr: 0x{addr:08x} data: 0x{data_int:08x}")
                self.bus.wdata.value = data_int & self.wdata_mask
                if -1 == strb:
                    self.bus.be.value = (1 << self.be_width) - 1  # All bytes enabled
                else:
                    self.bus.be.value = strb & ((1 << self.be_width) - 1)
            else:
                self.log.info(f"Read addr: 0x{addr:08x}")
                self.bus.wdata.value = 0
                self.bus.be.value = (1 << self.be_width) - 1

            # Wait for grant (with timeout)
            cycle_count = 0
            await RisingEdge(self.clock)
            while not self.bus.gnt.value:
                await RisingEdge(self.clock)
                cycle_count += 1
                if self.timeout_cycles >= 0 and cycle_count >= self.timeout_cycles:
                    msg = f"Request timeout: No gnt after {cycle_count} cycles (addr=0x{addr:08x})"
                    self.log.critical(msg)
                    raise Exception(msg)

            # Request accepted, deassert req
            self.bus.req.value = 0
            self.bus.we.value = 0
            self.bus.addr.value = 0
            self.bus.wdata.value = 0
            self.bus.be.value = 0
            self.bus.aid.value = 0

            # --- OBI Response Phase (R-channel) ---
            # Keep rready asserted (already set in init)
            # Wait for rvalid with timeout
            cycle_count = 0
            while not self.bus.rvalid.value:
                await RisingEdge(self.clock)
                cycle_count += 1
                if self.timeout_cycles >= 0 and cycle_count >= self.timeout_cycles:
                    msg = f"Response timeout: No rvalid after {cycle_count} cycles (addr=0x{addr:08x})"
                    self.log.critical(msg)
                    raise Exception(msg)

            # Response received - check error signal
            if not self.bus.err.value == error_expected:
                msg = f"ERR: incorrect error received {self.bus.err.value} (expected {error_expected})"
                self.exception_occurred = True
                if self.exception_enabled:
                    self.log.critical(msg)
                    raise Exception(msg)
                else:
                    self.log.warning(msg)

            if not write:
                # Read operation - capture data
                ret = int(self.bus.rdata.value)
                self.log.info(f"Value read: 0x{ret:08x}")
                if not data == bytes():
                    data_int = int.from_bytes(data, byteorder="little")
                    if not data_int == ret:
                        raise Exception(
                            f"Expected 0x{data_int:08x} doesn't match returned 0x{ret:08x}"
                        )
                self.queue_rx.append((ret.to_bytes(self.rbytes, "little"), tx_id))

            # Wait for response handshake to complete (rvalid && rready)
            await RisingEdge(self.clock)

            self.sync.set()


# Alias for convenience
OBIMaster = ObiMaster

