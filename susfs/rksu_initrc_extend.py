import sys

PATH = "drivers/kernelsu/ksud.c"

OLD_SHORT = '''\tconst char *short_name = file->f_path.dentry->d_name.name;
\tif (strcmp(short_name, "atrace.rc")) {
\t\t// we are only interest `atrace.rc` file name file
\t\treturn 0;
\t}
'''

NEW_SHORT = '''\tconst char *short_name = file->f_path.dentry->d_name.name;
\tif (strcmp(short_name, "atrace.rc") && strcmp(short_name, "init.rc")) {
\t\t// only interested in init rc files
\t\treturn 0;
\t}
'''

OLD_PATH = '''\tif (strcmp(dpath, "/system/etc/init/atrace.rc")) {
\t\treturn 0;
\t}
'''

NEW_PATH = '''\tif (strcmp(dpath, "/system/etc/init/atrace.rc") &&
\t    strcmp(dpath, "/system/etc/init/hw/init.rc") &&
\t    strcmp(dpath, "/init.rc")) {
\t\treturn 0;
\t}
\tpr_info("ksu: init rc read: %s\\n", dpath);
'''

text = open(PATH, "r", encoding="utf-8", errors="replace").read()
if OLD_SHORT not in text:
    sys.exit("ksud.c: atrace.rc short_name condition not found")
if OLD_PATH not in text:
    sys.exit("ksud.c: atrace.rc path condition not found")
text = text.replace(OLD_SHORT, NEW_SHORT, 1)
text = text.replace(OLD_PATH, NEW_PATH, 1)
open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("ksud.c init rc trigger extended")
