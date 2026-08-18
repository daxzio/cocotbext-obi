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

from __future__ import annotations

from collections import deque
from typing import Any, Optional

from cocotb import start_soon
from cocotb.triggers import RisingEdge

from .address_space import SparseMemoryRegion
from .obi_base import ObiBase
from .obi_bus import ObiBus


class ObiDevice(ObiBase):
    """OBI (Open Bus Interface) device/subordinate responder.

    Backs the OBI response channel with a memory *target* (any object
    exposing async ``read``/``write`` such as a
    :class:`~cocotbext.obi.address_space.MemoryRegion`). Override
    :meth:`_read`/:meth:`_write` for custom behaviour (see :class:`ObiRam`).

    Parameters
    ----------
    bus, clock:
        OBI bus and clock.
    target:
        Backing memory object. If omitted, a :class:`SparseMemoryRegion`
        sized to *size_bytes* (or the full address space) is created.
    size_bytes:
        Size of the auto-created backing memory when *target* is not given.
    max_outstanding:
        Maximum number of accepted-but-unanswered requests. Default ``2``.
        Responses are returned in strict order.
    """

    def __init__(
        self,
        bus: ObiBus,
        clock: Any,
        target=None,
        size_bytes: Optional[int] = None,
        max_outstanding: int = 2,
        autostart: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(bus, clock, name="device", **kwargs)

        if target is not None:
            self.target = target
        else:
            size = size_bytes if size_bytes is not None else 2**self.address_width
            self.target = SparseMemoryRegion(size)

        self.max_outstanding = max(1, int(max_outstanding))

        self.bus.gnt.value = 0
        self.bus.rvalid.value = 0
        self.bus.rdata.value = 0
        self.bus.err.value = 0
        self.write_rid(0)

        self._run_coroutine_obj: Any = None
        if autostart:
            self._restart()

    def _restart(self) -> None:
        if self._run_coroutine_obj is not None:
            self._run_coroutine_obj.kill()
        self._run_coroutine_obj = start_soon(self._run())

    def start(self) -> None:
        """(Re)start the responder coroutine."""
        self._restart()

    async def _write(self, address, data, strb=None):
        if strb is None:
            await self.target.write(address, data)
        else:
            for i in range(self.byte_lanes):
                if 1 == ((int(strb) >> i) & 0x1):
                    await self.target.write(address + i, data[i : i + 1])

    async def _read(self, address, length):
        return await self.target.read(address, length)

    async def _process(self, addr, we, be, wdata, aid) -> tuple[int, int, int]:
        """Apply a request and return the response tuple ``(rid, rdata, err)``."""
        try:
            if we:
                await self._write(addr, wdata.to_bytes(self.byte_lanes, "little"), be)
                self.log.debug(f"Write 0x{addr:08x} 0x{wdata:08x}")
                return (aid, 0, 0)
            else:
                x = await self._read(addr, self.byte_lanes)
                rdata = int.from_bytes(x, byteorder="little")
                self.log.debug(f"Read  0x{addr:08x} 0x{rdata:08x}")
                return (aid, rdata, 0)
        except Exception as e:  # noqa: BLE001 - any target fault becomes err=1
            self.log.warning(f"Access 0x{addr:08x} Invalid: {e}")
            return (aid, 0, 1)

    async def _run(self):
        """Decoupled grant and response with back-to-back acceptance."""
        self.bus.gnt.value = 0
        self.bus.rvalid.value = 0
        self.bus.rdata.value = 0
        self.bus.err.value = 0
        self.write_rid(0)

        pending: deque[tuple[int, int, int]] = deque()
        gnt_stall = 0
        await RisingEdge(self.clock)

        while True:
            req = self.sig_int(self.bus.req) == 1
            can_accept = len(pending) < self.max_outstanding
            grant = False

            if gnt_stall > 0:
                gnt_stall -= 1
            elif req and can_accept:
                stall = self.gnt_delay
                if stall:
                    gnt_stall = stall - 1
                else:
                    grant = True

            self.bus.gnt.value = 1 if grant else 0

            present = bool(pending)
            if present:
                rid, rdata, err = pending[0]
                self.bus.rvalid.value = 1
                self.write_rid(rid)
                self.bus.rdata.value = rdata
                self.bus.err.value = err
            else:
                self.bus.rvalid.value = 0
                self.bus.err.value = 0

            if grant:
                addr = self.sig_int(self.bus.addr)
                we = self.sig_int(self.bus.we) == 1
                be = self.sig_int(self.bus.be)
                wdata = self.sig_int(self.bus.wdata)
                aid = self.read_aid()

            rready = self.sig_int(self.bus.rready) == 1
            pop = present and rready

            await RisingEdge(self.clock)

            if pop:
                pending.popleft()
            if grant:
                pending.append(await self._process(addr, we, be, wdata, aid))
