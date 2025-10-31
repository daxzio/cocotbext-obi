from __future__ import annotations

from typing import Any

from cocotb import start_soon
from cocotb.triggers import RisingEdge

from .obi_base import ObiBase
from .obi_bus import ObiBus


class ObiSlave(ObiBase):
    def __init__(self, bus: ObiBus, clock: Any, target=None, **kwargs) -> None:
        super().__init__(bus, clock, name="slave", **kwargs)
        self.target = target

        # Initialize outputs
        self.bus.gnt.value = 0
        self.bus.rvalid.value = 0
        self.bus.rdata.value = 0
        self.bus.err.value = 0
        self.bus.rid.value = 0

        self._active: bool = False
        self._run_coroutine_obj: Any = None
        self._restart()

    def _restart(self) -> None:
        if self._run_coroutine_obj is not None:
            self._run_coroutine_obj.kill()
        self._run_coroutine_obj = start_soon(self._run())

    async def _write(self, address, data, strb=None):
        if self.target:
            if strb is None:
                await self.target.write(address, data)
            else:
                for i in range(self.byte_lanes):
                    if 1 == ((int(strb) >> i) & 0x1):
                        await self.target.write_byte(
                            address + i, data[i].to_bytes(1, "little")
                        )
        else:
            # Fallback to internal mem if no target
            if not hasattr(self, 'mem'):
                self.mem = bytearray(2**self.address_width)
            if strb is None:
                for i, byte_val in enumerate(data):
                    if address + i < len(self.mem):
                        self.mem[address + i] = byte_val
            else:
                for i in range(self.byte_lanes):
                    if 1 == ((int(strb) >> i) & 0x1):
                        if address + i < len(self.mem):
                            self.mem[address + i] = data[i]

    async def _read(self, address, length):
        if self.target:
            return await self.target.read(address, length)
        else:
            # Fallback to internal mem if no target
            if not hasattr(self, 'mem'):
                self.mem = bytearray(2**self.address_width)
            return bytes(self.mem[address:address + length])

    async def _run(self):
        await RisingEdge(self.clock)
        while True:
            await RisingEdge(self.clock)

            self.bus.gnt.value = 0

            # Accept request when idle
            if (int(self.bus.req.value) == 1) and not self._active:
                self._active = True
                self.bus.gnt.value = 1
                addr = int(self.bus.addr.value)
                we = int(self.bus.we.value) == 1
                be = int(self.bus.be.value)
                wdata = int(self.bus.wdata.value)
                aid = int(self.bus.aid.value)

                self.bus.rid.value = aid

                if addr < 0 or addr >= 2**self.address_width:
                    raise ValueError("Address out of range")

                # Apply delay for backpressure
                for i in range(self.delay):
                    await RisingEdge(self.clock)

                try:
                    if we:
                        await self._write(
                            addr,
                            wdata.to_bytes(self.byte_lanes, "little"),
                            be,
                        )
                        self.log.debug(f"Write 0x{addr:08x} 0x{wdata:08x}")
                        self.bus.rvalid.value = 1
                        self.bus.err.value = 0
                        self.bus.rdata.value = 0
                    else:
                        x = await self._read(addr, self.byte_lanes)
                        rdata = int.from_bytes(x, byteorder="little")
                        self.bus.rvalid.value = 1
                        self.bus.err.value = 0
                        self.bus.rdata.value = rdata
                        self.log.debug(f"Read  0x{addr:08x} 0x{rdata:08x}")
                except Exception as e:
                    self.log.warning(f"Access 0x{addr:08x} Invalid: {e}")
                    self.bus.rvalid.value = 1
                    self.bus.err.value = 1
                    self.bus.rdata.value = 0

            # Complete response when manager accepts
            if int(self.bus.rvalid.value) == 1 and int(self.bus.rready.value) == 1:
                self.bus.rvalid.value = 0
                self.bus.err.value = 0
                self._active = False
