import os
import sys

def pick(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    sys.exit("file not found: %s" % (paths,))

PATH = pick("drivers/kernelsu/ksud.c", "drivers/kernelsu/runtime/ksud.c")
text = open(PATH, "r", encoding="utf-8", errors="replace").read()

if "#include <linux/proc_fs.h>" not in text:
    anchor = '#include "selinux/selinux.h"'
    if anchor in text:
        text = text.replace(anchor, anchor + "\n#include <linux/proc_fs.h>\n#include <linux/seq_file.h>", 1)
    else:
        idx = text.find("#include")
        if idx < 0:
            sys.exit("ksud.c: no include anchor")
        end = text.find("\n", idx)
        text = text[:end + 1] + "#include <linux/proc_fs.h>\n#include <linux/seq_file.h>\n" + text[end + 1:]

if "ksu_dbg_enter" not in text:
    anchor = "u32 ksu_file_sid;"
    decls = "\nu32 ksu_dbg_enter;\nu32 ksu_dbg_inject;\nu32 ksu_dbg_apply;\nchar ksu_dbg_path[160];"
    if anchor in text:
        text = text.replace(anchor, anchor + decls, 1)
    else:
        idx = text.find("#include")
        end = text.find("\n", idx)
        text = text[:end + 1] + decls + "\n" + text[end + 1:]

old = '\tpr_info("ksu: enter comm=%s\\n", current->comm);'
if old in text:
    text = text.replace(old, '\tksu_dbg_enter++;\n' + old, 1)

old = '\tpr_info("ksu: dpath=%s\\n", dpath);'
if old in text:
    text = text.replace(old, old + '\n\tstrscpy(ksu_dbg_path, dpath, sizeof(ksu_dbg_path));', 1)

old = '\tpr_info("ksu: injected\\n");'
if old in text:
    text = text.replace(old, '\tksu_dbg_inject++;\n' + old, 1)

show = '''static int ksu_dbg_show(struct seq_file *m, void *v)
{
\tseq_printf(m, "enter=%u inject=%u apply=%u sid=%u path=%s\\n",
\t\t   ksu_dbg_enter, ksu_dbg_inject, ksu_dbg_apply,
\t\t   ksu_file_sid, ksu_dbg_path);
\treturn 0;
}

void ksu_ksud_init(void)
{
\tproc_create_single("ksu_dbg", 0, NULL, ksu_dbg_show);
}
'''
old_init = "void ksu_ksud_init(void)\n{\n}\n"
if old_init in text:
    text = text.replace(old_init, show, 1)
elif "ksu_ksud_init(void)" not in text:
    text += "\n" + show

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

RULES = pick("drivers/kernelsu/selinux/rules.c")
rt = open(RULES, "r", encoding="utf-8", errors="replace").read()
if "ksu_dbg_apply" not in rt:
    start = rt.find("void apply_kernelsu_rules(void)")
    if start < 0:
        sys.exit("rules.c: apply_kernelsu_rules not found")
    brace = rt.find("{", start)
    end = rt.find("\n}\n", brace)
    if brace < 0 or end < 0:
        sys.exit("rules.c: apply_kernelsu_rules body end not found")
    rt = rt[:start] + "extern u32 ksu_dbg_apply;\n\n" + rt[start:brace + 1] + "\n\tksu_dbg_apply = 1;\n" + rt[brace + 1:end] + "\n\tksu_dbg_apply = 2;\n" + rt[end:]
    with open(RULES, "w", encoding="utf-8", newline="\n") as f:
        f.write(rt)

print("ksud.c debug proc added")
