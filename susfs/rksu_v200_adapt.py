import os
import re
import sys

FDINFO = "fs/notify/fdinfo.c"

FUNC = r'''static void inotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark, struct file *file)
{
\tstruct inotify_inode_mark *inode_mark;
\tstruct inode *inode;
\tu32 mask;

\tif (mark->connector->type != FSNOTIFY_OBJ_TYPE_INODE)
\t\treturn;

\tinode_mark = container_of(mark, struct inotify_inode_mark, fsn_mark);
\tinode = igrab(fsnotify_conn_inode(mark->connector));
\tif (inode) {
\t\tmask = mark->mask & IN_ALL_EVENTS;
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
\t\t{
\t\t\tstruct mount *mnt = real_mount(file->f_path.mnt);

\t\t\tif (likely(susfs_is_current_proc_umounted()) &&
\t\t\t    mnt->mnt_id >= DEFAULT_KSU_MNT_ID) {
\t\t\t\tstruct path path;
\t\t\t\tchar *pathname = kmalloc(PAGE_SIZE, GFP_KERNEL);
\t\t\t\tchar *dpath;

\t\t\t\tif (!pathname)
\t\t\t\t\tgoto out_seq_printf;
\t\t\t\tdpath = d_path(&file->f_path, pathname, PAGE_SIZE);
\t\t\t\tif (!dpath || kern_path(dpath, 0, &path)) {
\t\t\t\t\tkfree(pathname);
\t\t\t\t\tgoto out_seq_printf;
\t\t\t\t}
\t\t\t\tif (!path.dentry->d_inode) {
\t\t\t\t\tpath_put(&path);
\t\t\t\t\tkfree(pathname);
\t\t\t\t\tgoto out_seq_printf;
\t\t\t\t}
\t\t\t\tseq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 ",
\t\t\t\t\t   inode_mark->wd, path.dentry->d_inode->i_ino,
\t\t\t\t\t   path.dentry->d_inode->i_sb->s_dev,
\t\t\t\t\t   inotify_mark_user_mask(mark));
\t\t\t\tshow_mark_fhandle(m, path.dentry->d_inode);
\t\t\t\tseq_putc(m, '\n');
\t\t\t\tiput(inode);
\t\t\t\tpath_put(&path);
\t\t\t\tkfree(pathname);
\t\t\t\treturn;
\t\t\t}
\t\t}
out_seq_printf:
#endif
\t\tseq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:%x ",
\t\t\t   inode_mark->wd, inode->i_ino, inode->i_sb->s_dev,
\t\t\t   mask, mark->ignored_mask);
\t\tshow_mark_fhandle(m, inode);
\t\tseq_putc(m, '\n');
\t\tiput(inode);
\t}
}
'''

text = open(FDINFO, "r", encoding="utf-8", errors="replace").read()
start = text.find("#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\nstatic void inotify_fdinfo(")
if start < 0:
    start = text.find("static void inotify_fdinfo(")
if start < 0:
    sys.exit("inotify_fdinfo not found")
end = text.find("void inotify_show_fdinfo(", start)
if end < 0:
    sys.exit("inotify_show_fdinfo not found")
# keep any leading comment/blank lines before the function
text = text[:start] + FUNC + "\n" + text[end:]
open(FDINFO, "w", encoding="utf-8", newline="\n").write(text)
print("rksu v2.0.0 fdinfo adapted")
