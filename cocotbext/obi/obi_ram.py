from .obi_slave import ObiSlave

# Import Memory from cocotbext.apb since we're reusing that infrastructure
from cocotbext.apb.memory import Memory


class ObiRam(ObiSlave, Memory):
    def __init__(
        self,
        bus,
        clock,
        size=2**32,
        mem=None,
        **kwargs
    ):
        Memory.__init__(self, size, mem, **kwargs)
        ObiSlave.__init__(self, bus, clock, **kwargs)

    async def _write(self, address, data, strb=None):
        if strb is None:
            self.write((address % self.size), data)
        else:
            for i in range(self.byte_lanes):
                if 1 == ((int(strb) >> i) & 0x1):
                    self.write_byte((address % self.size) + i, data[i])

    async def _read(self, address, length):
        return self.read(address % self.size, length)

