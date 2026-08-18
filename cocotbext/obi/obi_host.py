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
from dataclasses import dataclass
from typing import Any, Optional, Union

from cocotb import start_soon
from cocotb.triggers import Event, First, RisingEdge

from .address_map import AddressMap
from .constants import OBIError
from .obi_base import ObiBase
from .utils import resolve_x_int


@dataclass
class _ObiTxOp:
    write: bool
    addr: int
    data: bytes
    strb: int
    error_expected: bool
    tx_id: int
    event: Event


class ObiHost(ObiBase):
    """OBI (Open Bus Interface) host/manager driver.

    Implements the manager side of the OBI protocol from OpenHW Group.
    Supports automatic splitting of wide data into multiple bus-width
    transactions, register-name addressing via an :class:`AddressMap`, and
    pipelined address/data phases via decoupled A-channel and R-channel
    coroutines.

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
        transactions. Default ``2``. Values ``>1`` allow the address phase of
        transaction N+1 to overlap the data phase of N when the subordinate
        supports it.
    """

    def __init__(
        self,
        bus,
        clock,
        name: str = "host",
        timeout_cycles: int = 1000,
        max_outstanding: int = 2,
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

        self.queue_tx: deque[_ObiTxOp] = deque()
        self.queue_rx: deque[tuple[bytes, int]] = deque()
        self.outstanding: deque[_ObiTxOp] = deque()
        self.tx_id = 0

        self.sync = Event()

        self._idle = Event()
        self._idle.set()
        self._rx_event = Event()
        self._a_wake = Event()

        self._presented: Optional[_ObiTxOp] = None
        self._req_pause = 0
        self._gnt_timeout = 0
        self._resp_timeout = 0

        # Initialize request channel signals
        self.bus.req.value = 0
        self.bus.addr.value = 0
        self.bus.we.value = 0
        self.bus.be.value = 0
        self.bus.wdata.value = 0
        if self.has_aid:
            self.bus.aid.value = 0

        self.bus.rready.value = 1

        self._a_coroutine_obj: Any = None
        self._r_coroutine_obj: Any = None
        self._rready_coroutine_obj: Any = None
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
        """Number of bus-width transactions needed to transfer *data*."""
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
        events = self._enqueue_write(
            addr, data, strb, error_expected, length, device, index
        )
        for event in events:
            await event.wait()
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
        self._enqueue_write(
            addr, data, strb, error_expected, length, device, index
        )

    def _enqueue_write(
        self,
        addr: int,
        data: Union[int, bytes],
        strb: int = -1,
        error_expected: bool = False,
        length: int = -1,
        device: int = 0,
        index: int = -1,
    ) -> list[Event]:
        resolved = self.calc_address(addr, device, index)
        num_transactions = self.calc_length(length, data, self.wbytes)
        events: list[Event] = []

        for i in range(num_transactions):
            addrb = resolved + i * self.wbytes
            if isinstance(data, int):
                subdata = (data >> self.wwidth * i) & self.wdata_mask
                datab = subdata.to_bytes(self.wbytes, "little")
            else:
                datab = data[i * self.wbytes : (i + 1) * self.wbytes]
            self.tx_id += 1
            event = Event()
            events.append(event)
            self.queue_tx.append(
                _ObiTxOp(True, addrb, datab, strb, error_expected, self.tx_id, event)
            )

        self.sync.set()
        self._idle.clear()
        return events

    def _leading_write(self) -> Optional[_ObiTxOp]:
        if self._presented is not None and self._presented.write:
            return self._presented
        if self.outstanding and self.outstanding[0].write:
            return self.outstanding[0]
        if self.queue_tx and self.queue_tx[0].write:
            return self.queue_tx[0]
        return None

    async def _await_prior_writes(self) -> None:
        """Wait for earlier writes to complete before a blocking ``read()``.

        ``read_nowait()`` does not do this, so queued reads can still overlap
        in-flight writes on the bus.
        """
        while True:
            op = self._leading_write()
            if op is None:
                return
            await op.event.wait()
            if op is self._leading_write():
                await RisingEdge(self.clock)

    async def read(
        self,
        addr: int,
        data: Union[int, bytes] = b"",
        error_expected: bool = False,
        length: int = -1,
        device: int = 0,
        index: int = -1,
    ) -> Union[bytes, int]:
        """Read data from an OBI device.

        Waits for any earlier writes to finish first so the returned value is
        coherent with those writes. Use :meth:`read_nowait` to issue a read
        without that wait.
        """
        await self._await_prior_writes()
        rx_id = self.read_nowait(addr, data, error_expected, length, device, index)
        found = False
        ret: bytes = b""
        while not found:
            while self.queue_rx:
                ret_bytes, tx_id = self.queue_rx.popleft()
                if rx_id == tx_id:
                    found = True
                    ret = ret_bytes
                    break
            if not found:
                self._rx_event.clear()
                await self._rx_event.wait()
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
        """Queue a read without waiting for completion. Returns the last tx id."""
        resolved = self.calc_address(addr, device, index)
        num_transactions = self.calc_length(length, data, self.rbytes)
        last_tx_id = self.tx_id

        for i in range(num_transactions):
            addrb = resolved + i * self.rbytes
            if isinstance(data, int):
                subdata = (data >> self.rwidth * i) & self.rdata_mask
                datab = subdata.to_bytes(self.rbytes, "little")
            else:
                datab = data
            self.tx_id += 1
            last_tx_id = self.tx_id
            event = Event()
            self.queue_tx.append(
                _ObiTxOp(
                    False, addrb, datab, -1, error_expected, self.tx_id, event
                )
            )

        self.sync.set()
        self._idle.clear()
        return last_tx_id

    async def poll(
        self,
        addr: int,
        data: Union[int, bytes] = b"",
        device: int = 0,
        index: int = -1,
    ) -> None:
        """Repeatedly read *addr* until the returned data equals *data*."""
        resolved = self.calc_address(addr, device)
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
        if self._a_coroutine_obj is not None:
            self._a_coroutine_obj.kill()
        if self._r_coroutine_obj is not None:
            self._r_coroutine_obj.kill()
        if self._rready_coroutine_obj is not None:
            self._rready_coroutine_obj.kill()
        self._presented = None
        self._req_pause = 0
        self._gnt_timeout = 0
        self._resp_timeout = 0
        self._a_wake.clear()
        self._a_coroutine_obj = start_soon(self._run_a_channel())
        self._r_coroutine_obj = start_soon(self._run_r_channel())
        self._rready_coroutine_obj = start_soon(self._run_rready())

    async def _run_rready(self) -> None:
        """Drive the R-channel ready signal."""
        self.bus.rready.value = 1
        while True:
            await RisingEdge(self.clock)
            if not self.backpressure_rready:
                self.bus.rready.value = 1
                continue
            stall = self.rready_delay
            if stall:
                self.bus.rready.value = 0
                for _ in range(stall):
                    await RisingEdge(self.clock)
                self.bus.rready.value = 1

    @property
    def rready_delay(self) -> int:
        """Number of cycles to hold rready low, or 0 to stay ready."""
        return self._stall_cycles(self.backpressure_rready)

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
        return (
            self.empty_tx
            and not self.outstanding
            and self._presented is None
        )

    def clear(self) -> None:
        """Clears the RX and TX queues"""
        self.queue_tx.clear()
        self.queue_rx.clear()

    async def wait(self) -> None:
        """Wait for idle"""
        await self._idle.wait()

    def _update_idle(self) -> None:
        if self.idle:
            self._idle.set()

    def _deassert_req(self) -> None:
        self.bus.req.value = 0
        self.bus.we.value = 0
        self.bus.addr.value = 0
        self.bus.wdata.value = 0
        self.bus.be.value = 0
        if self.has_aid:
            self.bus.aid.value = 0

    def _drive_req(self, op: _ObiTxOp) -> None:
        if op.addr < 0 or op.addr >= 2**self.address_width:
            raise ValueError("Address out of range")

        self.bus.req.value = 1
        self.bus.we.value = op.write
        self.bus.addr.value = op.addr
        if self.has_aid:
            self.bus.aid.value = op.tx_id & self.aid_mask

        label = self.format_addr(op.addr)
        if op.write:
            data_int = int.from_bytes(op.data, byteorder="little")
            self.log.info(f"Write {self._format_addr_col(label)}: 0x{data_int:08x}")
            self.bus.wdata.value = data_int & self.wdata_mask
            if -1 == op.strb:
                self.bus.be.value = self.be_mask
            else:
                self.bus.be.value = op.strb & self.be_mask
        else:
            self.log.info(f"Read  {self._format_addr_col(label)}")
            self.bus.wdata.value = 0
            self.bus.be.value = self.be_mask

    def _can_present(self) -> bool:
        total = len(self.outstanding) + (1 if self._presented is not None else 0)
        return bool(self.queue_tx) and total < self.max_outstanding

    def _present_next(self) -> None:
        if self._req_pause > 0:
            self._req_pause -= 1
            self._deassert_req()
            return
        if not self._can_present():
            self._deassert_req()
            self._update_idle()
            return
        if self.backpressure_req:
            stall = self.req_delay
            if stall:
                self._req_pause = stall
                self._deassert_req()
                return
        op = self.queue_tx.popleft()
        self._drive_req(op)
        self._presented = op
        self._gnt_timeout = 0

    # --- Decoupled A/R channel drivers ---------------------------------------

    async def _run_a_channel(self) -> None:
        """Drive the OBI request (A) channel with zero-bubble back-to-back beats."""
        await RisingEdge(self.clock)
        while True:
            while not self.queue_tx and self._presented is None:
                self._deassert_req()
                self._update_idle()
                self.sync.clear()
                await self.sync.wait()

            await First(RisingEdge(self.clock), self._a_wake.wait())
            if self._a_wake.is_set():
                self._a_wake.clear()
                if self._presented is None:
                    self._present_next()
                    continue

            req_sample = bool(int(self.bus.req.value))
            gnt_sample = bool(int(self.bus.gnt.value))

            # Advance when the beat was accepted (req && gnt) or when idle.
            if (req_sample and gnt_sample) or (not req_sample):
                if req_sample and gnt_sample and self._presented is not None:
                    self.outstanding.append(self._presented)
                    self._presented = None
                    self._gnt_timeout = 0

                if self._presented is None:
                    self._present_next()
            elif self._presented is not None:
                self._gnt_timeout += 1
                if (
                    self.timeout_cycles >= 0
                    and self._gnt_timeout >= self.timeout_cycles
                ):
                    addr = self._presented.addr
                    msg = (
                        f"Request timeout: No gnt after {self._gnt_timeout} cycles "
                        f"(addr=0x{addr:08x})"
                    )
                    self.log.critical(msg)
                    raise TimeoutError(msg)

    async def _run_r_channel(self) -> None:
        """Collect OBI responses (R channel) in strict order."""
        await RisingEdge(self.clock)
        while True:
            await RisingEdge(self.clock)

            if self.outstanding:
                self._resp_timeout += 1
                if (
                    self.timeout_cycles >= 0
                    and self._resp_timeout >= self.timeout_cycles
                ):
                    addr = self.outstanding[0].addr
                    msg = (
                        f"Response timeout: No rvalid after {self._resp_timeout} "
                        f"cycles (addr=0x{addr:08x})"
                    )
                    self.log.critical(msg)
                    raise TimeoutError(msg)
            else:
                self._resp_timeout = 0

            if not (self.bus.rvalid.value and self.bus.rready.value):
                continue

            if not self.outstanding:
                continue

            op = self.outstanding.popleft()
            self._resp_timeout = 0

            self._check_error(op.error_expected, op.addr)

            if not op.write:
                ret = resolve_x_int(self.bus.rdata) & self.rdata_mask
                self.log.info(f"Value read: 0x{ret:08x}")
                if op.data != b"":
                    data_int = int.from_bytes(op.data, byteorder="little")
                    if data_int != ret:
                        raise ValueError(
                            f"Expected 0x{data_int:08x} doesn't match "
                            f"returned 0x{ret:08x}"
                        )
                ret_bytes = ret.to_bytes(self.rbytes, "little")
                self.queue_rx.append((ret_bytes, op.tx_id))
                self._rx_event.set()

            op.event.set()
            self._update_idle()
            if self._presented is None and self._can_present():
                self._a_wake.set()

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
