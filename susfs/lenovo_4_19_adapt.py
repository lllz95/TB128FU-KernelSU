#!/usr/bin/env python3
"""Lenovo 4.19 adaptation for SuSFS v2.3.0.

Two files need manual handling because they differ from the tree the upstream
patch was written against:

  fs/notify/fdinfo.c  - our tree keeps `u32 mask = mark->mask & IN_ALL_EVENTS;`
                        and prints ignored_mask, so hunk #4 does not apply.
                        The build script restores the original file and this
                        script rebuilds the SUS_KSTAT / SUS_MOUNT support.

  fs/namespace.c      - 4.19 has no fs_context / vfs_create_mount(); the
                        equivalent allocation lives in vfs_kern_mount().
                        Also restores the rejected include/CL_COPY_MNT_NS block.
"""
import os
import sys

FDINFO = "fs/notify/fdinfo.c"
NS = "fs/namespace.c"

# susfs.h is needed by both SUS_KSTAT and SUS_MOUNT code paths.
SUSFS_HDR = """#ifdef CONFIG_KSU_SUSFS
#include <linux/susfs.h>
#include <linux/susfs_def.h>
#endif
"""

FDINFO_BLOCK = """#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
		if (susfs_is_current_app_uid()) {
			bool is_fuse = false;
			if (susfs_is_inode_sus_kstat(inode, &is_fuse)) {
				unsigned long ino = inode->i_ino;
				dev_t dev = inode->i_sb->s_dev;
				susfs_sus_kstat_spoof_inotify_fdinfo(&ino, &dev);
				seq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 ",
						inode_mark->wd, ino, dev,
						inotify_mark_user_mask(mark));
				show_mark_fhandle(m, inode);
				seq_putc(m, '\\n');
				iput(inode);
				return;
			}
		}
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
		if (likely(susfs_is_current_proc_umounted())) {
			struct mount *mnt = real_mount(file->f_path.mnt);
			if (mnt->mnt_id >= DEFAULT_KSU_MNT_ID) {
				struct path path;
				char *pathname = kmalloc(PAGE_SIZE, GFP_KERNEL);
				char *dpath;
				if (!pathname) {
					goto orig_flow;
				}
				dpath = d_path(&file->f_path, pathname, PAGE_SIZE);
				if (!dpath) {
					goto out_kfree;
				}
				if (kern_path(dpath, 0, &path)) {
					goto out_kfree;
				}
				if (!d_backing_inode(path.dentry)) {
					goto out_path_put;
				}
				seq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 ",
						inode_mark->wd, d_backing_inode(path.dentry)->i_ino, d_backing_inode(path.dentry)->i_sb->s_dev,
						inotify_mark_user_mask(mark));
				show_mark_fhandle(m, d_backing_inode(path.dentry));
				seq_putc(m, '\\n');
				path_put(&path);
				kfree(pathname);
				iput(inode);
				return;
out_path_put:
				path_put(&path);
out_kfree:
				kfree(pathname);
			}
		}
orig_flow:
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
"""


def patch_fdinfo():
    src = open(FDINFO, "r", encoding="utf-8").read()
    if "SUS_KSTAT" in src:
        print("fdinfo.c already adapted")
        return

    # 1. includes
    anchor = "#include <linux/exportfs.h>\n"
    if anchor not in src:
        sys.exit("fdinfo.c: exportfs include not found")
    src = src.replace(anchor, anchor + SUSFS_HDR, 1)

    # 1b. the upstream patch declares these two helpers locally in fdinfo.c
    guard = "#if defined(CONFIG_INOTIFY_USER) || defined(CONFIG_FANOTIFY)\n\n"
    if guard not in src:
        sys.exit("fdinfo.c: inotify/fanotify guard not found")
    decls = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
        "extern bool susfs_is_inode_sus_kstat(struct inode *inode, bool *out_is_fuse);\n"
        "extern void susfs_sus_kstat_spoof_inotify_fdinfo(unsigned long *out_target_ino, dev_t *out_target_dev);\n"
        "#endif // #ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n\n"
    )
    src = src.replace(guard, guard + decls, 1)

    # 2. show_fdinfo prototype + call
    old_proto = (
        "static void show_fdinfo(struct seq_file *m, struct file *f,\n"
        "\t\t\tvoid (*show)(struct seq_file *m,\n"
        "\t\t\t\t     struct fsnotify_mark *mark))\n"
    )
    new_proto = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
        "static void show_fdinfo(struct seq_file *m, struct file *f,\n"
        "\t\t\tvoid (*show)(struct seq_file *m,\n"
        "\t\t\t\t     struct fsnotify_mark *mark,\n"
        "\t\t\t\t     struct file *file))\n"
        "#else\n"
        + old_proto +
        "#endif\n"
    )
    if old_proto not in src:
        sys.exit("fdinfo.c: show_fdinfo prototype not found")
    src = src.replace(old_proto, new_proto, 1)

    old_call = "\t\tshow(m, mark);\n"
    new_call = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
        "\t\tshow(m, mark, f);\n"
        "#else\n"
        "\t\tshow(m, mark);\n"
        "#endif\n"
    )
    if old_call not in src:
        sys.exit("fdinfo.c: show() call not found")
    src = src.replace(old_call, new_call, 1)

    # 3. inotify_fdinfo signature
    old_sig = "static void inotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark)\n"
    new_sig = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
        "static void inotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark, struct file *file)\n"
        "#else\n"
        + old_sig +
        "#endif\n"
    )
    if old_sig not in src:
        sys.exit("fdinfo.c: inotify_fdinfo signature not found")
    src = src.replace(old_sig, new_sig, 1)

    # 4a. hoist `u32 mask` to the top of inotify_fdinfo (gnu89: no declaration
    #     after a label; orig_flow: is followed by the original declaration).
    top_anchor = (
        "\tstruct inode *inode;\n"
        "\n"
        "\tif (mark->connector->type != FSNOTIFY_OBJ_TYPE_INODE)\n"
    )
    top_new = (
        "\tstruct inode *inode;\n"
        "\tu32 mask;\n"
        "\n"
        "\tif (mark->connector->type != FSNOTIFY_OBJ_TYPE_INODE)\n"
    )
    if top_anchor not in src:
        sys.exit("fdinfo.c: inotify_fdinfo top anchor not found")
    src = src.replace(top_anchor, top_new, 1)

    if "\t\tu32 mask = mark->mask & IN_ALL_EVENTS;\n" not in src:
        sys.exit("fdinfo.c: mask declaration not found")
    src = src.replace("\t\tu32 mask = mark->mask & IN_ALL_EVENTS;\n",
                      "\t\tmask = mark->mask & IN_ALL_EVENTS;\n", 1)

    # 4b. insert hiding block right after "if (inode) {"
    anchor2 = (
        "\tinode_mark = container_of(mark, struct inotify_inode_mark, fsn_mark);\n"
        "\tinode = igrab(fsnotify_conn_inode(mark->connector));\n"
        "\tif (inode) {\n"
    )
    if anchor2 not in src:
        sys.exit("fdinfo.c: inode anchor not found")
    src = src.replace(anchor2, anchor2 + FDINFO_BLOCK, 1)

    # 5. fanotify_fdinfo signature
    old_fan = "static void fanotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark)\n"
    new_fan = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
        "static void fanotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark, struct file *file)\n"
        "#else\n"
        + old_fan +
        "#endif\n"
    )
    if old_fan not in src:
        sys.exit("fdinfo.c: fanotify_fdinfo signature not found")
    src = src.replace(old_fan, new_fan, 1)

    open(FDINFO, "w", encoding="utf-8").write(src)
    print("fdinfo.c adapted (SUS_KSTAT + SUS_MOUNT)")


NS_HDR = """
#ifdef CONFIG_KSU_SUSFS
#include <linux/susfs_def.h>
#endif

#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
extern bool susfs_is_current_ksu_domain(void);
extern struct static_key_true susfs_is_sdcard_android_data_not_decrypted;

#ifndef CL_COPY_MNT_NS
#define CL_COPY_MNT_NS BIT(25) /* used by copy_mnt_ns() */
#endif
#endif
"""

NS_ALLOC = """#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
	if (static_branch_unlikely(&susfs_is_sdcard_android_data_not_decrypted) &&
	    susfs_is_current_ksu_domain())
		mnt = susfs_alloc_non_unshare_ksu_vfsmnt(name);
	else
#endif
		mnt = alloc_vfsmnt(name);
"""


def patch_ns():
    src = open(NS, "r", encoding="utf-8").read()
    if "CL_COPY_MNT_NS BIT" in src and "susfs_alloc_non_unshare_ksu_vfsmnt(name)" in src:
        print("namespace.c already adapted")
        return

    if "#include <linux/susfs_def.h>" not in src:
        anchor = '#include "internal.h"\n'
        if anchor not in src:
            sys.exit("namespace.c: internal.h include not found")
        src = src.replace(anchor, anchor + NS_HDR, 1)

    if "susfs_alloc_non_unshare_ksu_vfsmnt(name)" not in src:
        old_alloc = "\tmnt = alloc_vfsmnt(name);\n"
        if old_alloc not in src:
            sys.exit("namespace.c: alloc_vfsmnt(name) not found")
        src = src.replace(old_alloc, NS_ALLOC, 1)

    open(NS, "w", encoding="utf-8").write(src)
    print("namespace.c adapted (fs_context-free vfs_kern_mount path)")


patch_fdinfo()
patch_ns()
