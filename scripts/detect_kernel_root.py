#!/usr/bin/env python3
"""Locate the kernel root inside a downloaded/unpacked source tree.

A "kernel root" is a directory that contains a Makefile with VERSION and
PATCHLEVEL, plus arch/arm64/ and include/linux/kconfig.h. Useful when the
supplied source is a vendor package that nests the kernel in a subdirectory.

Usage: detect_kernel_root.py <base-dir> [subdir]
Prints the detected path on stdout; exits non-zero when not found.
"""
import os
import re
import sys


def is_kernel(d):
    mk = os.path.join(d, "Makefile")
    if not os.path.isfile(mk):
        return False
    try:
        with open(mk, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except OSError:
        return False
    if not re.search(r"^VERSION\s*=\s*\d+", txt, re.M):
        return False
    if not re.search(r"^PATCHLEVEL\s*=\s*\d+", txt, re.M):
        return False
    return os.path.isdir(os.path.join(d, "arch", "arm64")) and os.path.isfile(
        os.path.join(d, "include", "linux", "kconfig.h")
    )


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: detect_kernel_root.py <base-dir> [subdir]")
    base = os.path.abspath(sys.argv[1])
    sub = sys.argv[2].strip() if len(sys.argv) > 2 else ""

    if sub:
        cand = os.path.join(base, sub)
        if is_kernel(cand):
            print(cand)
            return 0
        sys.exit("kernel not found at %s" % cand)

    candidates = []
    for root, dirs, _files in os.walk(base):
        rel = os.path.relpath(root, base)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 3:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in (".git", "out", "modout")]
        if is_kernel(root):
            candidates.append((depth, root))
    if not candidates:
        sys.exit("kernel root not found under %s (depth <= 3)" % base)
    candidates.sort()
    print(candidates[0][1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
