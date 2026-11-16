import sys

PATH = "fs/read_write.c"

SIG = "ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)\n"
CALL = """#ifdef CONFIG_KSU
\tif (unlikely(ksu_vfs_read_hook))
\t\tksu_handle_vfs_read(&file, &buf, &count, &pos);
#endif
"""
EXTERN = """#ifdef CONFIG_KSU
extern bool ksu_vfs_read_hook __read_mostly;
extern int ksu_handle_vfs_read(struct file **file_ptr, char __user **buf_ptr,
\t\t\tsize_t *count_ptr, loff_t **pos);
#endif
"""

text = open(PATH, "r", encoding="utf-8", errors="replace").read()
pos = text.find(SIG)
if pos < 0:
    sys.exit("read_write.c: vfs_read signature not found")

# where does the function body start
brace = text.find("{", pos)
if brace < 0:
    sys.exit("read_write.c: vfs_read body not found")

# already instrumented inside vfs_read?
window = text[brace:brace + 700]
if "ksu_handle_vfs_read(&file" in window:
    print("read_write.c: vfs_read already hooked")
    sys.exit(0)

# ensure extern declarations right before vfs_read
if "extern int ksu_handle_vfs_read" not in text[max(0, pos - 600):pos]:
    text = text[:pos] + EXTERN + "\n" + text[pos:]
    pos = text.find(SIG)
    brace = text.find("{", pos)

text = text[:brace + 1] + "\n" + CALL + text[brace + 1:]
open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("read_write.c: vfs_read hook inserted")
