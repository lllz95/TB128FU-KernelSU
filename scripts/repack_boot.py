#!/usr/bin/env python3
"""Replace the kernel inside an Android boot image, keeping every other section.

Supports boot header v0, v1, v2, v3 and v4.

Usage:
    repack_boot.py <boot.img> <Image.gz> <output.img>

Layout (v0-v2):   header | kernel | ramdisk | second | recovery_dtbo | dtb
Layout (v3/v4):   header | kernel | ramdisk | bootconfig
"""
import struct
import sys

MAGIC = b"ANDROID!"
PAGE_ALIGN = 4096


def align(x, a):
    return (x + a - 1) // a * a


def parse_v0_v2(data):
    version = struct.unpack_from("<I", data, 40)[0]
    page_size = struct.unpack_from("<I", data, 36)[0]
    kernel_size = struct.unpack_from("<I", data, 8)[0]
    ramdisk_size = struct.unpack_from("<I", data, 16)[0]
    header_size = struct.unpack_from("<I", data, 20)[0]

    fields = {
        "version": version,
        "page_size": page_size,
        "kernel_size": kernel_size,
        "ramdisk_size": ramdisk_size,
        "header_size": header_size,
        "second_size": struct.unpack_from("<I", data, 24)[0],
        "recovery_dtbo_size": 0,
        "dtb_size": 0,
    }
    if version >= 1:
        fields["recovery_dtbo_size"] = struct.unpack_from("<I", data, 1632)[0]
    if version >= 2:
        fields["dtb_size"] = struct.unpack_from("<I", data, 1648)[0]

    ps = page_size
    off = ps
    sec = {}
    sec["kernel"] = data[off:off + kernel_size]
    off = align(off + kernel_size, ps)
    sec["ramdisk"] = data[off:off + ramdisk_size]
    off = align(off + ramdisk_size, ps)
    sec["second"] = data[off:off + fields["second_size"]]
    off = align(off + fields["second_size"], ps)
    if version >= 1:
        sec["recovery_dtbo"] = data[off:off + fields["recovery_dtbo_size"]]
        off = align(off + fields["recovery_dtbo_size"], ps)
    if version >= 2:
        sec["dtb"] = data[off:off + fields["dtb_size"]]
    return fields, sec


def parse_v3_v4(data):
    version = struct.unpack_from("<I", data, 40)[0]
    header_size = struct.unpack_from("<I", data, 20)[0]
    kernel_size = struct.unpack_from("<I", data, 8)[0]
    ramdisk_size = struct.unpack_from("<I", data, 16)[0]
    fields = {
        "version": version,
        "page_size": PAGE_ALIGN,
        "kernel_size": kernel_size,
        "ramdisk_size": ramdisk_size,
        "header_size": header_size,
        "second_size": 0,
        "recovery_dtbo_size": 0,
        "dtb_size": 0,
    }
    off = header_size
    sec = {}
    sec["kernel"] = data[off:off + kernel_size]
    off = align(off + kernel_size, PAGE_ALIGN)
    sec["ramdisk"] = data[off:off + ramdisk_size]
    off = align(off + ramdisk_size, PAGE_ALIGN)
    sec["bootconfig"] = data[off:]
    return fields, sec


def build_v0_v2(header, sec, new_kernel):
    ps = header["page_size"]
    out = bytearray(header["raw_header"])
    # update kernel size + section sizes in header copy
    struct.pack_into("<I", out, 8, len(new_kernel))
    struct.pack_into("<I", out, 16, len(sec["ramdisk"]))
    struct.pack_into("<I", out, 24, len(sec["second"]))
    if header["version"] >= 1:
        struct.pack_into("<I", out, 1632, len(sec.get("recovery_dtbo", b"")))
    if header["version"] >= 2:
        struct.pack_into("<I", out, 1648, len(sec.get("dtb", b"")))

    # pad header to page size
    if len(out) < ps:
        out += b"\x00" * (ps - len(out))
    out += new_kernel
    out += b"\x00" * (align(len(out), ps) - len(out))
    out += sec["ramdisk"]
    out += b"\x00" * (align(len(out), ps) - len(out))
    out += sec["second"]
    out += b"\x00" * (align(len(out), ps) - len(out))
    if header["version"] >= 1:
        out += sec.get("recovery_dtbo", b"")
        out += b"\x00" * (align(len(out), ps) - len(out))
    if header["version"] >= 2:
        out += sec.get("dtb", b"")
    return bytes(out)


def build_v3_v4(header, sec, new_kernel):
    hdr_size = header["header_size"]
    out = bytearray(header["raw_header"])
    struct.pack_into("<I", out, 8, len(new_kernel))
    struct.pack_into("<I", out, 16, len(sec["ramdisk"]))
    out = out[:hdr_size]
    out += new_kernel
    out += b"\x00" * (align(len(out), PAGE_ALIGN) - len(out))
    out += sec["ramdisk"]
    out += b"\x00" * (align(len(out), PAGE_ALIGN) - len(out))
    out += sec.get("bootconfig", b"")
    return bytes(out)


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: repack_boot.py <boot.img> <Image.gz> <output.img>")
    boot_path, kernel_path, out_path = sys.argv[1:4]
    data = open(boot_path, "rb").read()
    if data[:8] != MAGIC:
        sys.exit("not an Android boot image (magic mismatch)")
    version = struct.unpack_from("<I", data, 40)[0]
    if version not in (0, 1, 2, 3, 4):
        sys.exit("unsupported boot header version %d" % version)
    raw_header = data[: struct.unpack_from("<I", data, 20)[0]]
    if version <= 2:
        header, sec = parse_v0_v2(data)
    else:
        header, sec = parse_v3_v4(data)
    header["raw_header"] = raw_header
    new_kernel = open(kernel_path, "rb").read()
    if version <= 2:
        out = build_v0_v2(header, sec, new_kernel)
    else:
        out = build_v3_v4(header, sec, new_kernel)
    with open(out_path, "wb") as f:
        f.write(out)
    print(
        "repacked v%d: kernel %d -> %d bytes, ramdisk %d bytes, output %d bytes"
        % (version, header["kernel_size"], len(new_kernel), len(sec["ramdisk"]), len(out))
    )


if __name__ == "__main__":
    main()
