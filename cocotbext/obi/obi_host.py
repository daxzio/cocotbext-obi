"""

Copyright (c) 2024-2026 Daxzio

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

import logging
import math
from collections import deque
from typing import Any, Deque, Tuple, Union

from cocotb import start_soon
from cocotb.triggers import Event, RisingEdge

from .address_map import AddressMap
from .constants import OBIError
from .obi_base import ObiBase
from .utils import resolve_x_int


class ObiHost(ObiBase):
    """OBI (Open Bus Interface) host/manager driver.

    Implements the manager side of the OBI protocol from OpenHW Group.
    Supports automatic splitting of wide data into multiple bus-width
    transactions, register-name addressing via an :class:`AddressMap`, and
    optional pipelining of multiple outstanding transactions.

    Parameters
    ----------
    bus:
        :class:`ObiBus` object containing the OBI interface signals.
    clock:
        Clock signal.
    timeout_cycles:
        Maximum clock cycles to wait for ``gnt``/``rvalid`` before raising a
        timeout. Set to ``-1`` to disable. Default ``1000``.
    max_outstanding:
        Maximum number of outstanding (accepted but not yet responded)
        transactions. ``1`` (default) uses a strictly sequential, backward
        compatible request/response loop. Values ``>1`` enable pipelining
        with strict in-order completion.
    """

    def __init__(
        self,
        bus,
        clock,
        name: str = "host",
        timeout_cycles: int = 1000,
        max_outstanding: int = 1,
        **kwargs,
    ) -> None:
        super().__init__(bus, clock, name=name, **kwargs)

        self.timeout_cycles = timeout_cycles  # -1 disables timeout
        self.max_outstanding = max(1, int(max_outstanding))
        self.exception_enabled = True
        self.exception_occurred = False
        self.return_int = False
        self.ret: Union[bytes, None] = None
        self.intra_delay: int = 0

        self.be_width = len(self.bus.be)
        self.be_mask = (1 << self.be_width) - 1

        self.addrmap = AddressMap(word_bytes=self.wbytes, multi_device=False)

        self.log.info(f"OBI {self.name} configuration:")
        self.log.info(f"  Address width: {self.address_width} bits")
        self.log.info(f"  Data width: {self.wwidth} bits ({self.wbytes} bytes)")
        self.log.info(f"  BE width: {self.be_width} bits")
        self.log.info(f"  Max outstanding: {self.max_outstanding}")
        if self.timeout_cycles >= 0:
            self.log.info(f"  Timeout: {self.timeout_cycles} clock cycles")
        else:
            self.log.info("  Timeout: disabled")

        # (write, addr, data, strb, error_expected, tx_id)
        self.queue_tx: Deque[Tuple[bool, int, bytes, int, bool, int]] = deque()
        self.queue_rx: Deque[Tuple[bytes, int]] = deque()
        # outstanding: (write, addr, expected_data, error_expected, tx_id)
        self.outstanding: Deque[Tuple[bool, int, bytes, bool, int]] = deque()
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
        if self.has_aid:
            self.bus.aid.value = 0

        # Response channel (manager side) - always ready to accept responses
        self.bus.rready.value = 1

        self._run_coroutine_obj: Any = None
        self._resp_coroutine_obj: Any = None
        self._restart()

    # --- Address map helpers -------------------------------------------------

    def addaddrmap(self, addrmap, device: int = 0) -> None:
        self.addrmap.add(addrmap, device)

    def calc_address(self, addr, device: int = 0, index: int = -1) -> int:
        self.addr = self.addrmap.resolve(addr, device, index)
        return self.addr

    def format_addr(self, addr: int, device: int = 0) -> str:
        """Resolve a byte address to a register name when addrmap is configured."""
        return self.addrmap.format(addr, device)

    def _update_addr_label_width(self) -> None:
        self.addrmap._update_label_width()

    def _format_addr_col(self, label: str, prefix: str = "") -> str:
        return self.addrmap.format_col(label, prefix)

    def calc_length(self, length: int, data: Union[int, bytes], width: int) -> int:
        """Number of bus-width transactions needed to transfer *data*.

        ``width`` is the transfer width in bytes (wbytes for writes, rbytes
        for reads).
        """
        if isinstance(data, int):
            if length and length > 0:
                num = math.ceil((length * 8) / (width * 8))
            else:
                num = (
                    math.ceil(data.bit_length() / (width * 8))
                    if data.bit_length() > 0
                    else 1
                )
        else:
            if length and length > 0:
                num = math.ceil(length / width)
            else:
                num = math.ceil(len(data) / width) if len(data) > 0 else 1
        return max(1, num)

    # --- Public transaction API ---------------------------------------------

    async def write(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
        length: int = -1,
        device: int = 0,
        index: int = -1,
    ) -> None:
        """Write *data* to an OBI device and wait for completion."""
        self.write_nowait(addr, data, strb, error_expected, length, device, index)
        await self._idle.wait()
        for _ in range(self.intra_delay):
            await RisingEdge(self.clock)

    def write_nowait(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
        length: int = -1,
        device: int = 0,
        index: int = -1,
    ) -> None:
        """Queue a write without waiting for completion."""
        resolved = self.calc_address(addr, device, index)
        num_transactions = self.calc_length(length, data, self.wbytes)

        for i in range(num_transactions):
            addrb = resolved + i * self.wbytes
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
        data: Union[int, bytes] = b"",
        error_expected: bool = False,
        length: int = -1,
        device: int = 0,
        index: int = -1,
    ) -> Union[bytes, int]:
        """Read data from an OBI device."""
        rx_id = self.read_nowait(addr, data, error_expected, length, device, index)
        found = False
        ret: bytes = b""
        while not found:
            while self.queue_rx:
                ret, tx_id = self.queue_rx.popleft()
                if rx_id == tx_id:
                    found = True
                    break
            if not found:
                await RisingEdge(self.clock)
        await self._idle.wait()
        for _ in range(self.intra_delay):
            await RisingEdge(self.clock)
        self.ret = ret
        if self.return_int:
            return int.from_bytes(ret, byteorder="little")
        return ret

    def read_nowait(
        self,
        addr: int,
        data: Union[int, bytes] = b"",
        error_expected: bool = False,
        length: int = -1,
        device: int = 0,
        index: int = -1,
    ) -> int:
        """Queue a read without waiting for completion. Returns the tx id."""
        resolved = self.calc_address(addr, device, index)
        num_transactions = self.calc_length(length, data, self.rbytes)

        for i in range(num_transactions):
            addrb = resolved + i * self.rbytes
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

    async def poll(
        self,
        addr: int,
        data: Union[int, bytes] = b"",
        device: int = 0,
        index: int = -1,
    ) -> None:
        """Repeatedly read *addr* until the returned data equals *data*."""
        resolved = self.calc_address(addr, device, index)
        label = self.format_addr(resolved, device)
        self.log.info(f"Poll  {self._format_addr_col(label)}")
        level_num = self.log.getEffectiveLevel()
        self.log.setLevel(logging.WARNING)
        if isinstance(data, int):
            datab = data.to_bytes(self.rbytes, "little")
        else:
            datab = data
        self.ret = None
        while self.ret != datab:
            await self.read(addr, device=device, index=index)
        self.log.setLevel(level_num)

    # --- Lifecycle / status --------------------------------------------------

    def _restart(self) -> None:
        if self._run_coroutine_obj is not None:
            self._run_coroutine_obj.kill()
        if self._resp_coroutine_obj is not None:
            self._resp_coroutine_obj.kill()
            self._resp_coroutine_obj = None
        if self.max_outstanding <= 1:
            self._run_coroutine_obj = start_soon(self._run_sequential())
        else:
            self._run_coroutine_obj = start_soon(self._run_request())
            self._resp_coroutine_obj = start_soon(self._run_response())

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
        return self.empty_tx and not self.outstanding

    def clear(self) -> None:
        """Clears the RX and TX queues"""
        self.queue_tx.clear()
        self.queue_rx.clear()

    async def wait(self) -> None:
        """Wait for idle"""
        await self._idle.wait()

    def _update_idle(self) -> None:
        if not self.queue_tx and not self.outstanding:
            self._idle.set()

    # --- Sequential (max_outstanding == 1) implementation --------------------

    async def _run_sequential(self):
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
            self.bus.req.value = 1
            self.bus.we.value = write
            self.bus.addr.value = addr
            if self.has_aid:
                self.bus.aid.value = tx_id & self.aid_mask

            label = self.format_addr(addr)
            if write:
                data_int = int.from_bytes(data, byteorder="little")
                self.log.info(f"Write {self._format_addr_col(label)}: 0x{data_int:08x}")
                self.bus.wdata.value = data_int & self.wdata_mask
                if -1 == strb:
                    self.bus.be.value = self.be_mask
                else:
                    self.bus.be.value = strb & self.be_mask
            else:
                self.log.info(f"Read  {self._format_addr_col(label)}")
                self.bus.wdata.value = 0
                self.bus.be.value = self.be_mask

            # Wait for grant (with timeout)
            cycle_count = 0
            await RisingEdge(self.clock)
            while not self.bus.gnt.value:
                await RisingEdge(self.clock)
                cycle_count += 1
                if self.timeout_cycles >= 0 and cycle_count >= self.timeout_cycles:
                    msg = (
                        f"Request timeout: No gnt after {cycle_count} cycles "
                        f"(addr=0x{addr:08x})"
                    )
                    self.log.critical(msg)
                    raise TimeoutError(msg)

            # Request accepted, deassert req
            self.bus.req.value = 0
            self.bus.we.value = 0
            self.bus.addr.value = 0
            self.bus.wdata.value = 0
            self.bus.be.value = 0
            if self.has_aid:
                self.bus.aid.value = 0

            # --- OBI Response Phase (R-channel) ---
            cycle_count = 0
            while not self.bus.rvalid.value:
                await RisingEdge(self.clock)
                cycle_count += 1
                if self.timeout_cycles >= 0 and cycle_count >= self.timeout_cycles:
                    msg = (
                        f"Response timeout: No rvalid after {cycle_count} cycles "
                        f"(addr=0x{addr:08x})"
                    )
                    self.log.critical(msg)
                    raise TimeoutError(msg)

            self._check_error(error_expected, addr)

            if not write:
                ret = resolve_x_int(self.bus.rdata) & self.rdata_mask
                self.log.info(f"Value read: 0x{ret:08x}")
                if data != b"":
                    data_int = int.from_bytes(data, byteorder="little")
                    if data_int != ret:
                        raise ValueError(
                            f"Expected 0x{data_int:08x} doesn't match "
                            f"returned 0x{ret:08x}"
                        )
                self.queue_rx.append((ret.to_bytes(self.rbytes, "little"), tx_id))

            if not self.queue_tx:
                self._idle.set()

            # Wait for response handshake to complete (rvalid && rready)
            await RisingEdge(self.clock)

            self.sync.set()

    # --- Pipelined (max_outstanding > 1) implementation ----------------------

    async def _run_request(self):
        await RisingEdge(self.clock)
        while True:
            while (not self.queue_tx) or (
                len(self.outstanding) >= self.max_outstanding
            ):
                self.bus.req.value = 0
                self.bus.we.value = 0
                self.bus.addr.value = 0
                self.bus.wdata.value = 0
                self.bus.be.value = 0
                if self.has_aid:
                    self.bus.aid.value = 0
                self._update_idle()
                await RisingEdge(self.clock)

            (
                write,
                addr,
                data,
                strb,
                error_expected,
                tx_id,
            ) = self.queue_tx[0]

            if addr < 0 or addr >= 2**self.address_width:
                raise ValueError("Address out of range")

            self.bus.req.value = 1
            self.bus.we.value = write
            self.bus.addr.value = addr
            if self.has_aid:
                self.bus.aid.value = tx_id & self.aid_mask

            label = self.format_addr(addr)
            if write:
                data_int = int.from_bytes(data, byteorder="little")
                self.log.info(f"Write {self._format_addr_col(label)}: 0x{data_int:08x}")
                self.bus.wdata.value = data_int & self.wdata_mask
                if -1 == strb:
                    self.bus.be.value = self.be_mask
                else:
                    self.bus.be.value = strb & self.be_mask
            else:
                self.log.info(f"Read  {self._format_addr_col(label)}")
                self.bus.wdata.value = 0
                self.bus.be.value = self.be_mask

            cycle_count = 0
            await RisingEdge(self.clock)
            while not self.bus.gnt.value:
                await RisingEdge(self.clock)
                cycle_count += 1
                if self.timeout_cycles >= 0 and cycle_count >= self.timeout_cycles:
                    msg = (
                        f"Request timeout: No gnt after {cycle_count} cycles "
                        f"(addr=0x{addr:08x})"
                    )
                    self.log.critical(msg)
                    raise TimeoutError(msg)

            # Request accepted
            self.queue_tx.popleft()
            self.outstanding.append((write, addr, data, error_expected, tx_id))

            # Deassert req for one cycle so the device sees a clean req
            # edge (avoids a delta-cycle race where a lingering req is granted
            # twice). The device enforces a matching one-cycle grant gap.
            self.bus.req.value = 0
            self.bus.we.value = 0
            self.bus.addr.value = 0
            self.bus.wdata.value = 0
            self.bus.be.value = 0
            if self.has_aid:
                self.bus.aid.value = 0
            await RisingEdge(self.clock)

    async def _run_response(self):
        self.bus.rready.value = 1
        await RisingEdge(self.clock)
        while True:
            while not self.bus.rvalid.value:
                await RisingEdge(self.clock)

            if not self.outstanding:
                # Response with nothing outstanding - ignore this cycle
                await RisingEdge(self.clock)
                continue

            write, addr, expected, error_expected, tx_id = self.outstanding.popleft()

            self._check_error(error_expected, addr)

            if not write:
                ret = resolve_x_int(self.bus.rdata) & self.rdata_mask
                self.log.info(f"Value read: 0x{ret:08x}")
                if expected != b"":
                    data_int = int.from_bytes(expected, byteorder="little")
                    if data_int != ret:
                        raise ValueError(
                            f"Expected 0x{data_int:08x} doesn't match "
                            f"returned 0x{ret:08x}"
                        )
                self.queue_rx.append((ret.to_bytes(self.rbytes, "little"), tx_id))

            self._update_idle()

            # Advance past the accepted response (rvalid && rready)
            await RisingEdge(self.clock)

    def _check_error(self, error_expected: bool, addr: int) -> None:
        err = bool(int(self.bus.err.value))
        if err != error_expected:
            msg = (
                f"ERR: incorrect error received {err} "
                f"(expected {error_expected}) (addr=0x{addr:08x})"
            )
            self.exception_occurred = True
            if self.exception_enabled:
                self.log.critical(msg)
                raise OBIError(msg)
            else:
                self.log.warning(msg)
