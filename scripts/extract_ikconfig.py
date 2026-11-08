#!/usr/bin/env python3
"""Extract the embedded kernel .config from a boot image / kernel binary.

Kernels built with CONFIG_IKCONFIG embed their config as a zlib blob wrapped in
IKCFG_ST ... IKCFG_ED magic. That blob is copied into the kernel image (and thus
the boot image), so the config can be recovered without a running device.

Works for:
  - Android boot.img (v0-v4): scans the whole file for gzip members
  - raw Image / Image.gz

Usage: extract_ikconfig.py <boot.img|Image[.gz]>  > output.config
"""
import re
import sys
import zlib


def gunzip_members(buf):
    """Decompress every gzip member found in buf, keep concatenated output."""
    out = bytearray()
    pos = 0
    while True:
        start = buf.find(b"\x1f\x8b", pos)
        if start < 0:
            break
        try:
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            out += d.decompress(buf[start:])
        except zlib.error:
            pass
        pos = start + 2
    return bytes(out)


def find_config(blob):
    m = re.search(rb"IKCFG_ST(.+?)IKCFG_ED", blob, re.S)
    if not m:
        return None
    try:
        return zlib.decompress(m.group(1))
    except zlib.error:
        return None


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: extract_ikconfig.py <boot.img|Image[.gz]>")
    data = open(sys.argv[1], "rb").read()

    # 1. try the file as-is (raw Image / uncompressed)
    cfg = find_config(data)
    # 2. try decompressing gzip members (Image.gz or boot.img containing one)
    if cfg is None:
        cfg = find_config(gunzip_members(data))
    if cfg is None:
        sys.exit(
            "IKCFG magic not found: this image was built without CONFIG_IKCONFIG, "
            "or the kernel is compressed with a format other than gzip"
        )
    sys.stdout.buffer.write(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
