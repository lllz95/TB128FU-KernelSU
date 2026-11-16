import sys

PATH = "fs/read_write.c"
SIG = "ssize_t ksys_read(unsigned int fd, char __user *buf, size_t count)\n"
EXTERN = """#ifdef CONFIG_KSU
extern int ksu_handle_sys_read(unsigned int fd, char __user **buf_ptr,
\t\t\tsize_t *count_ptr);
#endif
"""
CALL = """#ifdef CONFIG_KSU
\tksu_handle_sys_read(fd, &buf, &count);
#endif
"""

text = open(PATH, "r", encoding="utf-8", errors="replace").read()
pos = text.find(SIG)
if pos < 0:
    sys.exit("read_write.c: ksys_read not found")

brace = text.find("{", pos)
if brace < 0:
    sys.exit("read_write.c: ksys_read body not found")

window = text[brace:brace + 400]
if "ksu_handle_sys_read(fd" in window:
    print("read_write.c: ksys_read already hooked")
    sys.exit(0)

if "extern int ksu_handle_sys_read" not in text[max(0, pos - 400):pos]:
    text = text[:pos] + EXTERN + "\n" + text[pos:]
    pos = text.find(SIG)
    brace = text.find("{", pos)

text = text[:brace + 1] + "\n" + CALL + text[brace + 1:]
with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print("read_write.c: ksys_read hook inserted")
