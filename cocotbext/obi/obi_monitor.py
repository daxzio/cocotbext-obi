from __future__ import annotations

from typing import Any, AsyncIterator, Optional

import cocotb
from cocotb.triggers import RisingEdge

from .obi_bus import ObiBus


class ObiTransaction:
    def __init__(self, *, addr: int, we: bool, be: int, wdata: int, aid: int,
                 rvalid: bool = False, rdata: int = 0, err: bool = False, rid: int = 0) -> None:
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


class ObiMonitor:
    def __init__(self, bus: ObiBus, clock: Any) -> None:
        self.bus = bus
        self.clock = clock
        self._queue: list[ObiTransaction] = []
        self._active: bool = False
        self._aid_latched: int = 0
        self._req_sample: Optional[ObiTransaction] = None

    async def _run(self) -> None:
        while True:
            await RisingEdge(self.clock)

            # Capture A-channel request when req asserted and we're idle
            if (int(self.bus.req.value) == 1) and not self._active:  # type: ignore[attr-defined]
                self._active = True
                self._aid_latched = int(self.bus.aid.value)  # type: ignore[attr-defined]
                self._req_sample = ObiTransaction(
                    addr=int(self.bus.addr.value),  # type: ignore[attr-defined]
                    we=bool(int(self.bus.we.value)),  # type: ignore[attr-defined]
                    be=int(self.bus.be.value),  # type: ignore[attr-defined]
                    wdata=int(self.bus.wdata.value),  # type: ignore[attr-defined]
                    aid=self._aid_latched,
                )

            # When response is valid, emit a completed transaction
            if self._active and int(self.bus.rvalid.value) == 1:  # type: ignore[attr-defined]
                r = ObiTransaction(
                    addr=self._req_sample.addr if self._req_sample else 0,
                    we=self._req_sample.we if self._req_sample else False,
                    be=self._req_sample.be if self._req_sample else 0,
                    wdata=self._req_sample.wdata if self._req_sample else 0,
                    aid=self._aid_latched,
                    rvalid=True,
                    rdata=int(self.bus.rdata.value),  # type: ignore[attr-defined]
                    err=bool(int(self.bus.err.value)),  # type: ignore[attr-defined]
                    rid=int(self.bus.rid.value),  # type: ignore[attr-defined]
                )
                self._queue.append(r)
                # Complete when consumer accepts; if rready low, still record once
                if int(self.bus.rready.value) == 1:  # type: ignore[attr-defined]
                    self._active = False
                    self._req_sample = None

    def start(self) -> None:
        cocotb.start_soon(self._run())

    async def recv(self) -> ObiTransaction:
        while not self._queue:
            await RisingEdge(self.clock)
        return self._queue.pop(0)

    async def __aiter__(self) -> AsyncIterator[ObiTransaction]:
        while True:
            yield await self.recv()


