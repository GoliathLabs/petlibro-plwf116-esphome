"""Flash a LibreTiny image into OTA1 of an AmebaD device, in one ltchiptool session.

Needs ltchiptool with AmebaD support (libretiny-eu/ltchiptool#98). Run it from a
LibreTiny checkout, because ltchiptool reads platform.json/families.json there:

  python path/to/ambd_session.py check IMAGE PORT       # read only
  python path/to/ambd_session.py write IMAGE PORT       # write IMAGE to OTA1, then verify
  python path/to/ambd_session.py invalidate-ota2 PORT   # zero the OTA2 slot signature

IMAGE is image_ota.0x006000.bin from the ESPHome/LibreTiny build. PORT is e.g.
/dev/ttyUSB0 or COM3. Put the chip into UART download mode first.

check:           link, show the OTA1 sector map against IMAGE and the OTA2 signature state.
write:           check, write IMAGE to 0x6000, read OTA1 back and compare.
invalidate-ota2: zero the first 8 bytes of OTA2 (0x186000) so that the bootloader
                 starts OTA1. The rest of the slot (the vendor firmware) is kept.
Every mode stops at the first error and does not retry.
"""

import struct
import sys
import time
from io import BytesIO

from ltchiptool import Family
from ltchiptool.commands.flash._utils import flash_link_interactive
from ltchiptool.soc import SocInterface
from ltchiptool.soc.ambd.util import ambdtool as _ambd
from ltchiptool.util.flash import FlashConnection
from ltchiptool.util.intbin import align_down, inttole16, inttole24

OTA1 = 0x6000
OTA2 = 0x186000
SEC = 0x1000
SIGN = b"81958711"
T0 = time.monotonic()


def log(msg):
    print(f"[{time.monotonic() - T0:7.2f}s] {msg}", flush=True)


# Workaround until libretiny-eu/ltchiptool#98 skips stray NAKs: the flash loader
# sends 0x15 bytes between commands, and the erase then misses its ACK.
def _flash_erase(self, offset, length):
    count = (length + _ambd.AMBD_BLOCK_SIZE - 1) // _ambd.AMBD_BLOCK_SIZE
    offset = align_down(offset, _ambd.AMBD_BLOCK_SIZE)
    timeout = 1.0 * count
    self.s.read_all()
    pkt = struct.pack("<B3s2s", _ambd.CMD_EFS, inttole24(offset), inttole16(count))
    self.s.timeout = 0.5
    t = time.monotonic()
    self.s.write(pkt)
    while time.monotonic() - t < timeout:
        b = self.s.read(1)
        if b and b[0] == _ambd.ACK[0]:
            log(f"erase of {count} sectors ACKed after {time.monotonic() - t:.2f} s")
            return
    raise RuntimeError(f"No ACK for sector erase at 0x{offset:X} within {timeout:.0f} s")


_orig_memory_write = _ambd.AmbDTool.memory_write


def _memory_write(self, *args, **kwargs):
    time.sleep(0.2)
    self.s.read_all()
    return _orig_memory_write(self, *args, **kwargs)


_ambd.AmbDTool.flash_erase = _flash_erase
_ambd.AmbDTool.memory_write = _memory_write


def read(soc, offset, length):
    return b"".join(soc.flash_read_raw(offset=offset, length=length, verify=True))


def sector_map(data, ref):
    """N = same as IMAGE, . = blank, ? = other."""
    out = ""
    for i in range(0, len(data), SEC):
        c = data[i : i + SEC]
        r = ref[i : i + SEC].ljust(len(c), b"\xff")
        out += "N" if c == r else "." if c == b"\xff" * len(c) else "?"
    return out


def connect(port):
    soc = SocInterface.get(Family.get("ambd"))
    # links at the ROM's 115200, transfers at the default 460800
    soc.flash_set_connection(FlashConnection(port))
    # The first baud switch after a fresh loader upload often gets no ACK;
    # the next link attempt finds the loader at 460800.
    for attempt in range(1, 4):
        try:
            flash_link_interactive(soc, 20.0)
            break
        except RuntimeError as e:
            log(f"link attempt {attempt} failed: {e}")
            soc.flash_disconnect()
            soc.flash_build_protocol(force=True)
    else:
        sys.exit("no stable link")
    log(f"port baud rate: {soc.amb.s.baudrate}, chip: {soc.flash_get_chip_info_string()}")
    return soc


def ota2_state(soc):
    head = read(soc, OTA2, SEC)
    state = "valid" if head[:8] == SIGN else "invalid"
    log(f"OTA2 signature: {state} ({head[:8].hex(' ')})")
    return head


def main():
    mode = sys.argv[1]
    if mode == "invalidate-ota2":
        soc = connect(sys.argv[2])
        head = ota2_state(soc)
        if head[:8] != SIGN:
            log("nothing to do")
            return
        new = b"\x00" * 8 + head[8:]
        soc.flash_write_raw(offset=OTA2, length=SEC, data=BytesIO(new), verify=True)
        ok = read(soc, OTA2, SEC) == new
        log(f"OTA2 sector written and read back: {'ok' if ok else 'MISMATCH'}")
        sys.exit(0 if ok else 2)

    assert mode in ("check", "write"), __doc__
    image = open(sys.argv[2], "rb").read()
    assert image[:8] == SIGN and len(image) <= 0xFA000, "not an OTA1 image"
    length = (len(image) + SEC - 1) // SEC * SEC
    soc = connect(sys.argv[3])
    log("OTA1 before: " + sector_map(read(soc, OTA1, length), image))
    ota2_state(soc)
    if mode == "check":
        return

    log(f"writing {len(image)} bytes to 0x{OTA1:X} ...")
    soc.flash_write_raw(offset=OTA1, length=len(image), data=BytesIO(image), verify=True)
    after = read(soc, OTA1, length)
    ok = after[: len(image)] == image and set(after[len(image) :]) <= {0xFF}
    log(f"OTA1 read back: {'identical' if ok else 'MISMATCH'}")
    ota2_state(soc)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
