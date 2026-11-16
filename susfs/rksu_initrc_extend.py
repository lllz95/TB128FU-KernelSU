import os
import sys

def pick(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    sys.exit("file not found: %s" % (paths,))

PATH = pick("drivers/kernelsu/ksud.c", "drivers/kernelsu/runtime/ksud.c")

RC_OLD = '''\t"on post-fs-data\\n"
\t"    start logd\\n"
\t// We should wait for the post-fs-data finish
\t"    exec u:r:" KERNEL_SU_DOMAIN ":s0 root -- " KSUD_PATH
\t" post-fs-data\\n"
\t"\\n"
'''

RC_NEW = '''\t"on post-fs-data\\n"
\t"    start logd\\n"
\t// We should wait for the post-fs-data finish
\t"    exec u:r:" KERNEL_SU_DOMAIN ":s0 root -- " KSUD_PATH
\t" post-fs-data\\n"
\t"\\n"
\t"on boot\\n"
\t"    exec u:r:" KERNEL_SU_DOMAIN ":s0 root -- " KSUD_PATH
\t" post-fs-data\\n"
\t"\\n"
'''

FUNC_PREFIX = '''int ksu_handle_vfs_read(struct file **file_ptr, char __user **buf_ptr,
			size_t *count_ptr, loff_t **pos)
{
	pr_info("ksu: enter comm=%s\\n", current->comm);

	if (!ksu_vfs_read_hook) {
		pr_info("ksu: flag off\\n");
		return 0;
	}

	struct file *file;
	char __user *buf;
	size_t count;

	if (strcmp(current->comm, "init")) {
		pr_info("ksu: not init\\n");
		return 0;
	}

	file = *file_ptr;
	if (IS_ERR(file)) {
		pr_info("ksu: bad file\\n");
		return 0;
	}

	if (!d_is_reg(file->f_path.dentry)) {
		pr_info("ksu: not regular\\n");
		return 0;
	}

	const char *short_name = file->f_path.dentry->d_name.name;
	pr_info("ksu: short_name=%s\\n", short_name);
	if (strcmp(short_name, "init.rc") && strcmp(short_name, "atrace.rc")) {
		return 0;
	}
	char path[256];
	char *dpath = d_path(&file->f_path, path, sizeof(path));

	if (IS_ERR(dpath)) {
		pr_info("ksu: dpath err\\n");
		return 0;
	}

	pr_info("ksu: dpath=%s\\n", dpath);
	if (strcmp(dpath, "/system/etc/init/hw/init.rc") &&
	    strcmp(dpath, "/init.rc") &&
	    strcmp(dpath, "/system/etc/init/atrace.rc")) {
		return 0;
	}

'''

OLD_INJECT = "\t// we've succeed to insert ksud.rc, now we need to proxy the read and modify the result!"
NEW_INJECT = '\tpr_info("ksu: injected\\n");\n' + OLD_INJECT

text = open(PATH, "r", encoding="utf-8", errors="replace").read()

if RC_OLD not in text:
    sys.exit("ksud.c: KERNEL_SU_RC post-fs-data block not found")
text = text.replace(RC_OLD, RC_NEW, 1)

start = text.find("int ksu_handle_vfs_read(")
if start < 0:
    sys.exit("ksud.c: ksu_handle_vfs_read not found")
end = text.find("// we only process the first read", start)
if end < 0:
    sys.exit("ksud.c: first-read marker not found")
text = text[:start] + FUNC_PREFIX + text[end:]

OLD_COUNT = "\tif (count < rc_count) {"
NEW_COUNT = '\tpr_info("ksu: count=%zu rc_count=%zu\\n", count, rc_count);\n\tif (count < rc_count) {'
if OLD_COUNT not in text:
    sys.exit("ksud.c: count check not found")
text = text.replace(OLD_COUNT, NEW_COUNT, 1)

if OLD_INJECT not in text:
    sys.exit("ksud.c: injected marker not found")
text = text.replace(OLD_INJECT, NEW_INJECT, 1)

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print("ksud.c instrumented")
