#!/usr/bin/env python3
"""Patch the kernel inside an Android boot image in place.

The output is a byte-for-byte copy of the input image (same file size) with
only the kernel section replaced and the header size fields updated. Existing
ramdisk / second / recovery_dtbo / dtb sections and any trailing partition
padding stay untouched.

Supports:
  * legacy boot header (v0/v1/v2 with addr fields, e.g. Lenovo TB128FU)
  * AOSP boot header v1/v2 (size fields)
  * AOSP boot header v3/v4

Usage:
    repack_boot.py <boot.img> <Image.gz> <output.img>
"""
import struct
import sys

MAGIC = b"ANDROID!"
PAGE_ALIGN = 4096


def align(x, a):
    return (x + a - 1) // a * a


def u32(d, off):
    return struct.unpack_from("<I", d, off)[0]


def u64(d, off):
    return struct.unpack_from("<Q", d, off)[0]


def detect(d):
    version = u32(d, 40)
    page_size = u32(d, 36)
    size_at_20 = u32(d, 20)
    legacy = page_size in (2048, 4096) and size_at_20 > 0x10000
    return version, page_size if legacy else 0, legacy


def header_size(d, version, legacy):
    if version >= 1 and legacy:
        return u32(d, 1644)
    return u32(d, 20)


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: repack_boot.py <boot.img> <Image.gz> <output.img>")
    boot_path, kernel_path, out_path = sys.argv[1:4]
    data = bytearray(open(boot_path, "rb").read())
    if data[:8] != MAGIC:
        sys.exit("not an Android boot image (magic mismatch)")

    version, page_size, legacy = detect(data)
    if version > 4:
        sys.exit("unsupported boot header version %d" % version)
    new_kernel = open(kernel_path, "rb").read()

    if version <= 2:
        ps = page_size or 4096
        hdr_size = header_size(data, version, legacy) or (1632 + 12 * version)
        # section sizes
        if legacy:
            kernel_size = u32(data, 8)
            ramdisk_size = u32(data, 16)
            second_size = u32(data, 24)
        else:
            kernel_size = u32(data, 8)
            ramdisk_size = u32(data, 12)
            second_size = u32(data, 24)
        recovery_size = u32(data, 1632) if version >= 1 else 0
        dtb_size = u32(data, 1648) if version >= 2 else 0

        # read original sections
        off = ps
        ramdisk = bytes(data[off + align(kernel_size, ps):off + align(kernel_size, ps) + ramdisk_size])
        off2 = off + align(kernel_size, ps) + align(ramdisk_size, ps)
        second = bytes(data[off2:off2 + second_size])
        off3 = off2 + align(second_size, ps)
        recovery = bytes(data[off3:off3 + recovery_size]) if recovery_size else b""
        off4 = off3 + align(recovery_size, ps)
        dtb = bytes(data[off4:off4 + dtb_size]) if dtb_size else b""

        # recompute offsets
        k_off = ps
        r_off = k_off + align(len(new_kernel), ps)
        s_off = r_off + align(ramdisk_size, ps)
        rec_off = s_off + align(second_size, ps)
        d_off = rec_off + align(recovery_size, ps)

        # update header fields in place
        struct.pack_into("<I", data, 8, len(new_kernel))
        if legacy:
            struct.pack_into("<I", data, 16, ramdisk_size)
        else:
            struct.pack_into("<I", data, 12, ramdisk_size)
        struct.pack_into("<I", data, 24, second_size)
        if version >= 1:
            struct.pack_into("<I", data, 1632, recovery_size)
            struct.pack_into("<Q", data, 1636, rec_off)
        if version >= 2:
            struct.pack_into("<I", data, 1648, dtb_size)

        # write sections into the original buffer (keeps file size and padding)
        data[k_off:k_off + len(new_kernel)] = new_kernel
        data[r_off:r_off + len(ramdisk)] = ramdisk
        if second:
            data[s_off:s_off + len(second)] = second
        if recovery:
            data[rec_off:rec_off + len(recovery)] = recovery
        if dtb:
            data[d_off:d_off + len(dtb)] = dtb
        print(
            "patched legacy/v%d image: kernel %d -> %d bytes at %d, ramdisk at %d, dtb at %d, size %d"
            % (version, kernel_size, len(new_kernel), k_off, r_off, d_off, len(data))
        )
    else:
        hdr_size = u32(data, 20)
        old_kernel = u32(data, 8)
        ramdisk_size = u32(data, 16)
        ramdisk_off = align(hdr_size + old_kernel, PAGE_ALIGN)
        ramdisk = bytes(data[ramdisk_off:ramdisk_off + ramdisk_size])
        bootconfig = bytes(data[align(ramdisk_off + ramdisk_size, PAGE_ALIGN):])

        k_off = hdr_size
        r_off = align(k_off + len(new_kernel), PAGE_ALIGN)
        struct.pack_into("<I", data, 8, len(new_kernel))
        struct.pack_into("<I", data, 16, ramdisk_size)
        data[k_off:k_off + len(new_kernel)] = new_kernel
        if ramdisk:
            data[r_off:r_off + len(ramdisk)] = ramdisk
        bc_off = align(r_off + len(ramdisk), PAGE_ALIGN)
        if bootconfig:
            data[bc_off:bc_off + len(bootconfig)] = bootconfig
        print(
            "patched v%d image: kernel %d -> %d bytes, size %d"
            % (version, old_kernel, len(new_kernel), len(data))
        )

    with open(out_path, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
