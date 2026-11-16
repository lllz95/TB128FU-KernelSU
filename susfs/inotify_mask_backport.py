#!/usr/bin/env python3
"""Backport inotify_mark_user_mask() into 4.19's fs/notify/inotify/inotify.h.

SuSFS' fdinfo.c hunk (SUS_MOUNT display hiding) calls this helper, which only
exists in 5.x kernels. The implementation is trivial and all IN_* flags it
uses exist on 4.19, so we add it instead of dropping the fdinfo change.
"""
import os
import sys

path = "fs/notify/inotify/inotify.h"
if not os.path.exists(path):
    sys.exit("inotify.h not found")

src = open(path, "r", encoding="utf-8").read()
if "inotify_mark_user_mask" in src:
    print("inotify_mark_user_mask already present")
    sys.exit(0)

block = (
    "\n#ifndef INOTIFY_USER_MASK\n"
    "#define INOTIFY_USER_MASK (IN_ALL_EVENTS | IN_ONESHOT | IN_EXCL_UNLINK)\n"
    "#endif\n"
    "\n"
    "static inline __u32 inotify_mark_user_mask(struct fsnotify_mark *fsn_mark)\n"
    "{\n"
    "\treturn fsn_mark->mask & INOTIFY_USER_MASK;\n"
    "}\n"
)

idx = src.rfind("\n#endif")
if idx == -1:
    sys.exit("no trailing #endif in inotify.h")
src = src[:idx] + "\n" + block + src[idx:]
with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("inotify_mark_user_mask() backported")
