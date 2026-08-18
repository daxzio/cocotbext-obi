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

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Optional

import cocotb
from cocotb import start_soon
from cocotb.triggers import ReadOnly, RisingEdge
from cocotb.utils import get_sim_time

from .obi_base import ObiBase
from .obi_bus import ObiBus


class ObiTransaction:
    def __init__(
        self,
        *,
        addr: int,
        we: bool,
        be: int,
        wdata: int,
        aid: int,
        rvalid: bool = False,
        rdata: int = 0,
        err: bool = False,
        rid: int = 0,
    ) -> None:
        self.addr = addr
        self.we = we
        self.be = be
        self.wdata = wdata
        self.aid = aid
        self.rvalid = rvalid
        self.rdata = rdata
        self.err = err
        self.rid = rid

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"ObiTransaction(addr=0x{self.addr:08x}, we={self.we}, be=0x{self.be:x}, "
            f"wdata=0x{self.wdata:0x}, aid={self.aid}, rvalid={self.rvalid}, "
            f"rdata=0x{self.rdata:0x}, err={self.err}, rid={self.rid})"
        )


class ObiMonitor(ObiBase):
    def __init__(self, bus: ObiBus, clock: Any, **kwargs) -> None:
        super().__init__(bus, clock, name="monitor", **kwargs)
        self.disable_logging()
        self._queue: list[ObiTransaction] = []
        self._active: bool = False
        self._aid_latched: int = 0
        self._req_sample: Optional[ObiTransaction] = None
        self._run_coroutine_obj: Any = None
        self._check_sync_coroutines: list[Any] = []
        self._last_clk_time: int = 0

    def start(self) -> None:
        if self._run_coroutine_obj is not None:
            self._run_coroutine_obj.kill()
        self._run_coroutine_obj = cocotb.start_soon(self._run())

    def enable_check_sync(self) -> None:
        """Enable checking that bus signals only change on clock edges."""
        self.disable_check_sync()
        self._last_clk_time = get_sim_time()
        self._check_sync_coroutines.append(start_soon(self._check_sync_clock()))
        for name in self.bus._signals:
            if hasattr(self.bus, name):
                self._check_sync_coroutines.append(
                    start_soon(self._check_sync_signal(name, getattr(self.bus, name)))
                )

    def disable_check_sync(self) -> None:
        """Disable the synchronous signal-change check."""
        for coro in self._check_sync_coroutines:
            coro.kill()
        self._check_sync_coroutines.clear()

    async def _check_sync_clock(self) -> None:
        while True:
            await RisingEdge(self.clock)
            self._last_clk_time = get_sim_time()

    async def _check_sync_signal(self, name: str, signal: Any) -> None:
        while True:
            await signal.value_change
            if get_sim_time() != self._last_clk_time:
                await ReadOnly()
                if get_sim_time() != self._last_clk_time:
                    self.log.error(
                        f"Signal {name} changed at {get_sim_time()}, "
                        f"which is not aligned with the last clock edge at "
                        f"{self._last_clk_time}"
                    )

    @property
    def empty_txn(self) -> bool:
        return not self._queue

    async def _run(self) -> None:
        while True:
            await RisingEdge(self.clock)

            # Capture A-channel request when req asserted and we're idle
            if (self.sig_int(self.bus.req) == 1) and not self._active:
                self._active = True
                self._aid_latched = self.read_aid()
                self._req_sample = ObiTransaction(
                    addr=self.sig_int(self.bus.addr),
                    we=bool(self.sig_int(self.bus.we)),
                    be=self.sig_int(self.bus.be),
                    wdata=self.sig_int(self.bus.wdata),
                    aid=self._aid_latched,
                )

            # When response is valid, emit a completed transaction
            if self._active and self.sig_int(self.bus.rvalid) == 1:
                r = ObiTransaction(
                    addr=self._req_sample.addr if self._req_sample else 0,
                    we=self._req_sample.we if self._req_sample else False,
                    be=self._req_sample.be if self._req_sample else 0,
                    wdata=self._req_sample.wdata if self._req_sample else 0,
                    aid=self._aid_latched,
                    rvalid=True,
                    rdata=self.sig_int(self.bus.rdata),
                    err=bool(self.sig_int(self.bus.err)),
                    rid=self.sig_int(self.bus.rid) if self.has_rid else 0,
                )
                self._queue.append(r)
                if self.sig_int(self.bus.rready) == 1:
                    self._active = False
                    self._req_sample = None

    async def recv(self) -> ObiTransaction:
        while not self._queue:
            await RisingEdge(self.clock)
        return self._queue.pop(0)

    async def __aiter__(self) -> AsyncIterator[ObiTransaction]:
        while True:
            yield await self.recv()
