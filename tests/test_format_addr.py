"""Unit tests for ObiHost.format_addr reverse lookup."""

from cocotbext.obi.obi_host import ObiHost
from cocotbext.obi.address_map import AddressMap


def _host_with_map(addrmap):
    h = ObiHost.__new__(ObiHost)
    am = AddressMap(word_bytes=4, multi_device=False)
    am.update({0: addrmap})
    h.addrmap = am
    return h


def test_legacy_aliases():
    from cocotbext.obi import ObiDevice, ObiHost, ObiMaster, ObiSlave

    assert issubclass(ObiMaster, ObiHost)
    assert issubclass(ObiSlave, ObiDevice)
    assert ObiMaster.__mro__[1] is ObiHost
    assert ObiSlave.__mro__[1] is ObiDevice


def test_format_addr_exact():
    m = _host_with_map({"STATUS": 0x84, "CTRL": 0x74})
    assert m.format_addr(0x84) == "STATUS"
    assert m.format_addr(0x74) == "CTRL"


def test_format_addr_indexed():
    m = _host_with_map({"AES_KEY_SHARE0": 0x04, "AES_KEY_SHARE1": 0x24})
    assert m.format_addr(0x04) == "AES_KEY_SHARE0"
    assert m.format_addr(0x08) == "AES_KEY_SHARE0[1]"
    assert m.format_addr(0x24) == "AES_KEY_SHARE1"
    assert m.format_addr(0x40) == "AES_KEY_SHARE1[7]"


def test_format_addr_unknown():
    m = _host_with_map({"STATUS": 0x84})
    assert m.format_addr(0x00) == "0x00000000"


def test_format_addr_col_alignment():
    m = _host_with_map(
        {
            "AES_STATUS": 0x84,
            "AES_CTRL_AUX_SHADOWED": 0x78,
            "AES_KEY_SHARE0": 0x04,
        }
    )
    m._update_addr_label_width()
    short = m._format_addr_col("AES_STATUS")
    long = m._format_addr_col("AES_CTRL_AUX_SHADOWED")
    assert len(short) == len(long)
    assert m._format_addr_col("AES_KEY_SHARE0[7]").endswith(" ")
