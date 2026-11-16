import subprocess
import sys

try:
    ORIG = open("/tmp/fdinfo.orig", "r", encoding="utf-8").read()
except FileNotFoundError:
    ORIG = subprocess.check_output(["git", "show", "HEAD:fs/notify/fdinfo.c"], text=True)
text = ORIG

# 1. include
anchor = "#include <linux/exportfs.h>\n"
sus_hdr = (
    "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
    "#include <linux/susfs_def.h>\n"
    "#endif\n"
)
if anchor not in text:
    sys.exit("fdinfo: exportfs include not found")
text = text.replace(anchor, anchor + sus_hdr, 1)

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
if old_proto not in text:
    sys.exit("fdinfo: show_fdinfo prototype not found")
text = text.replace(old_proto, new_proto, 1)

old_call = "\t\tshow(m, mark);\n"
new_call = (
    "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
    "\t\tshow(m, mark, f);\n"
    "#else\n"
    "\t\tshow(m, mark);\n"
    "#endif\n"
)
if old_call not in text:
    sys.exit("fdinfo: show() call not found")
text = text.replace(old_call, new_call, 1)

# 3. inotify_fdinfo
start = text.find("static void inotify_fdinfo(")
end = text.find("void inotify_show_fdinfo(", start)
if start < 0 or end < 0:
    sys.exit("fdinfo: inotify_fdinfo region not found")
original_func = text[start:end].rstrip() + "\n"

sus_func = r'''#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
static void inotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark, struct file *file)
{
	struct inotify_inode_mark *inode_mark;
	struct inode *inode;
	u32 mask;

	if (mark->connector->type != FSNOTIFY_OBJ_TYPE_INODE)
		return;

	inode_mark = container_of(mark, struct inotify_inode_mark, fsn_mark);
	inode = igrab(fsnotify_conn_inode(mark->connector));
	if (inode) {
		mask = mark->mask & IN_ALL_EVENTS;
		if (likely(susfs_is_current_proc_umounted()) &&
		    real_mount(file->f_path.mnt)->mnt_id >= DEFAULT_KSU_MNT_ID) {
			struct path path;
			char *pathname = kmalloc(PAGE_SIZE, GFP_KERNEL);
			char *dpath;

			if (pathname) {
				dpath = d_path(&file->f_path, pathname, PAGE_SIZE);
				if (dpath && !kern_path(dpath, 0, &path) &&
				    path.dentry->d_inode) {
					seq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 ",
						   inode_mark->wd,
						   path.dentry->d_inode->i_ino,
						   path.dentry->d_inode->i_sb->s_dev,
						   inotify_mark_user_mask(mark));
					show_mark_fhandle(m, path.dentry->d_inode);
					seq_putc(m, '\n');
					iput(inode);
					path_put(&path);
					kfree(pathname);
					return;
				}
				if (dpath && !kern_path(dpath, 0, &path))
					path_put(&path);
				kfree(pathname);
			}
		}
		seq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:%x ",
			   inode_mark->wd, inode->i_ino, inode->i_sb->s_dev,
			   mask, mark->ignored_mask);
		show_mark_fhandle(m, inode);
		seq_putc(m, '\n');
		iput(inode);
	}
}
#else
'''
text = text[:start] + sus_func + original_func + "#endif\n\n" + text[end:]

# 4. fanotify_fdinfo signature
old_fan = "static void fanotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark)\n"
new_fan = (
    "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
    "static void fanotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark, struct file *file)\n"
    "#else\n"
    + old_fan +
    "#endif\n"
)
if old_fan not in text:
    sys.exit("fdinfo: fanotify_fdinfo not found")
text = text.replace(old_fan, new_fan, 1)

with open("fs/notify/fdinfo.c", "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print("fdinfo adapted for SuSFS v2.0.0")
