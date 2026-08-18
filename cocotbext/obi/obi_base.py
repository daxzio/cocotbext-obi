"""
Base class for OBI drivers
"""

import logging
from random import randint, seed

from .utils import resolve_x_int


class ObiBase:
    def __init__(self, bus, clock, name="monitor", seednum=None, **kwargs) -> None:
        self.name = name
        self.bus = bus
        self.clock = clock
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
        self.byte_size = 8
        self.byte_lanes = self.wbytes
        self.rdata_mask = 2**self.rwidth - 1
        self.wdata_mask = 2**self.wwidth - 1

        self.log.info(f"OBI {self.name} configuration:")
        self.log.info(f"  Address width: {self.address_width} bits")
        self.log.info(f"  Data width: {self.wwidth} bits ({self.byte_lanes} bytes)")

        self.has_aid = hasattr(self.bus, "aid")
        self.has_rid = hasattr(self.bus, "rid")
        if self.has_aid:
            self.aid_width = len(self.bus.aid)
            self.aid_mask = (1 << self.aid_width) - 1
        else:
            self.aid_width = 0
            self.aid_mask = 0

        self.backpressure_req = False
        self.backpressure_rready = False
        self.backpressure_gnt = False
        self.backpressure_rvalid = False
        if seednum is not None:
            self.base_seed = seednum
        else:
            self.base_seed = randint(0, 0xFFFFFF)
        seed(self.base_seed)
        self.log.debug(f"Seed is set to {self.base_seed}")

    @property
    def backpressure(self) -> bool:
        """True if any channel backpressure is enabled."""
        return (
            self.backpressure_req
            or self.backpressure_rready
            or self.backpressure_gnt
            or self.backpressure_rvalid
        )

    def _stall_cycles(self, enabled: bool) -> int:
        """Random stall length, or 0, when *enabled* is true."""
        if not enabled:
            return 0
        if 0 == randint(0, 0x3):
            return randint(1, 0x8)
        return 0

    @property
    def delay(self):
        """Cycles to postpone rvalid after a grant (device response delay)."""
        if self.backpressure_rvalid:
            if 0 == randint(0, 0x3):
                return randint(0, 0x8)
            else:
                return 0
        else:
            return 0

    @property
    def gnt_delay(self) -> int:
        """Cycles to hold gnt low after req, or 0 to grant immediately."""
        return self._stall_cycles(self.backpressure_gnt)

    @property
    def req_delay(self) -> int:
        """Cycles to wait before asserting req, or 0 to issue immediately."""
        return self._stall_cycles(self.backpressure_req)

    def enable_logging(self):
        self.log.setLevel(logging.DEBUG)

    def disable_logging(self):
        self.log.setLevel(logging.INFO)

    def enable_backpressure(
        self,
        seednum=None,
        *,
        req: bool | None = None,
        rready: bool | None = None,
        gnt: bool | None = None,
        rvalid: bool | None = None,
    ) -> None:
        """Enable random handshake stalls.

        With no channel arguments, every channel is enabled (the previous
        behaviour). Passing any of ``req``, ``rready``, ``gnt``, or ``rvalid``
        sets that channel and leaves the others unchanged, so the host can
        stall only ``req`` or only ``rready``::

            host.enable_backpressure(req=True)             # A-channel gaps
            host.enable_backpressure(rready=True)          # R-channel stalls
            host.enable_backpressure(req=True, rready=False)
        """
        if seednum is not None:
            self.base_seed = seednum
            seed(seednum)
        specified = {
            "req": req,
            "rready": rready,
            "gnt": gnt,
            "rvalid": rvalid,
        }
        if all(v is None for v in specified.values()):
            self.backpressure_req = True
            self.backpressure_rready = True
            self.backpressure_gnt = True
            self.backpressure_rvalid = True
            return
        if req is not None:
            self.backpressure_req = req
        if rready is not None:
            self.backpressure_rready = rready
        if gnt is not None:
            self.backpressure_gnt = gnt
        if rvalid is not None:
            self.backpressure_rvalid = rvalid

    def disable_backpressure(self) -> None:
        self.backpressure_req = False
        self.backpressure_rready = False
        self.backpressure_gnt = False
        self.backpressure_rvalid = False

    @staticmethod
    def sig_int(sig, default: int = 0) -> int:
        """Read a bus signal as int; return *default* when unresolved (X/Z)."""
        if not sig.value.is_resolvable:
            return default
        return resolve_x_int(sig)

    def read_aid(self, default: int = 0) -> int:
        if not self.has_aid:
            return default
        return self.sig_int(self.bus.aid, default)

    def write_rid(self, value: int) -> None:
        if self.has_rid:
            self.bus.rid.value = value
