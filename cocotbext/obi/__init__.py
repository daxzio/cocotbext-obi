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

from .address_map import AddressMap
from .address_space import (
    AddressSpace,
    MemoryInterface,
    MemoryRegion,
    PeripheralRegion,
    Pool,
    Region,
    SparseMemoryRegion,
    Window,
    WindowPool,
)
from .buddy_allocator import BuddyAllocator
from .constants import InvalidAccess, OBIError, ObiResp
from .memory import Memory
from .obi_base import ObiBase
from .obi_bus import OBIBus, ObiBus
from .obi_device import ObiDevice
from .obi_host import ObiHost
from .obi_interface import HAVE_COCOTBEXT_INTERFACE, ObiInterface
from .obi_master import OBIMaster, ObiMaster
from .obi_monitor import ObiMonitor, ObiTransaction
from .obi_ram import ObiRam
from .obi_slave import ObiSlave
from .sparse_memory import SparseMemory
from .version import __version__

__all__ = [
    "HAVE_COCOTBEXT_INTERFACE",
    "AddressMap",
    "AddressSpace",
    "BuddyAllocator",
    "InvalidAccess",
    "Memory",
    "MemoryInterface",
    "MemoryRegion",
    "OBIBus",
    "OBIError",
    "OBIMaster",
    "ObiBase",
    "ObiBus",
    "ObiDevice",
    "ObiHost",
    "ObiInterface",
    "ObiMaster",
    "ObiMonitor",
    "ObiRam",
    "ObiResp",
    "ObiSlave",
    "ObiTransaction",
    "PeripheralRegion",
    "Pool",
    "Region",
    "SparseMemory",
    "SparseMemoryRegion",
    "Window",
    "WindowPool",
    "__version__",
]
