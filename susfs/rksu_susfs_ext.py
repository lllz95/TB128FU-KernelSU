import os
import sys

ROOT = os.getcwd()

def patch(path, old, new, count=1):
    p = os.path.join(ROOT, path)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if old not in text:
        sys.exit(f"marker not found in {path}")
    text = text.replace(old, new, count)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

# 1. header: add all-procs API + try_umount API
patch(
    "include/linux/susfs.h",
    """#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
struct st_susfs_hide_sus_mnts_for_non_su_procs {
\tbool                                    enabled;
\tint                                     err;
};
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
""",
    """#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
struct st_susfs_hide_sus_mnts_for_non_su_procs {
\tbool                                    enabled;
\tint                                     err;
};
struct st_susfs_hide_sus_mnts_for_all_procs {
\tbool                                    enabled;
\tint                                     err;
};
void susfs_set_hide_sus_mnts_for_all_procs(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT

/* try_umount */
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
struct st_susfs_try_umount {
\tchar                                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
\tint                                     mnt_mode;
\tint                                     err;
};
struct st_susfs_try_umount_list {
\tstruct list_head                        list;
\tstruct st_susfs_try_umount              info;
};
void susfs_add_try_umount(void __user **user_info);
void susfs_try_umount(uid_t uid);
#endif // #ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
""",
)

# 2. def header: command id for all-procs
patch(
    "include/linux/susfs_def.h",
    "#define CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS 0x55561",
    "#define CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS 0x55561\n"
    "#define CMD_SUSFS_HIDE_SUS_MNTS_FOR_ALL_PROCS 0x55561",
)

# 3. susfs.c: all-procs implementation
patch(
    "fs/susfs.c",
    '#include "mount.h"',
    '#include "mount.h"\n#include <linux/mount.h>',
)

patch(
    "fs/susfs.c",
    "DEFINE_STATIC_KEY_FALSE(susfs_is_hide_sus_mnts_for_non_su_procs_enabled);",
    """DEFINE_STATIC_KEY_FALSE(susfs_is_hide_sus_mnts_for_non_su_procs_enabled);
DEFINE_STATIC_KEY_FALSE(susfs_is_hide_sus_mnts_for_all_procs_enabled);

void susfs_set_hide_sus_mnts_for_all_procs(void __user **user_info) {
\tstruct st_susfs_hide_sus_mnts_for_all_procs info = {0};

\tif (copy_from_user(&info, (struct st_susfs_hide_sus_mnts_for_all_procs __user*)*user_info, sizeof(info))) {
\t\tinfo.err = -EFAULT;
\t\tgoto out_copy_to_user;
\t}

\tif (info.enabled) {
\t\tstatic_branch_enable(&susfs_is_hide_sus_mnts_for_all_procs_enabled);
\t} else {
\t\tstatic_branch_disable(&susfs_is_hide_sus_mnts_for_all_procs_enabled);
\t}

\tSUSFS_LOGI("susfs_is_hide_sus_mnts_for_all_procs_enabled: %d\\n", static_key_enabled(&susfs_is_hide_sus_mnts_for_all_procs_enabled));
\tinfo.err = 0;
out_copy_to_user:
\tif (copy_to_user(&((struct st_susfs_hide_sus_mnts_for_all_procs __user*)*user_info)->err, &info.err, sizeof(info.err))) {
\t\tinfo.err = -EFAULT;
\t}
\tSUSFS_LOGI("CMD_SUSFS_HIDE_SUS_MNTS_FOR_ALL_PROCS -> ret: %d\\n", info.err);
}
""",
)

# 4. susfs.c: try_umount implementation
patch(
    "fs/susfs.c",
    "/* spoof_uname */",
    """/* try_umount */
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
extern void try_umount(const char *mnt, int flags);
static DEFINE_MUTEX(susfs_mutex_lock_try_umount);
static LIST_HEAD(LH_TRY_UMOUNT_PATH);

void susfs_add_try_umount(void __user **user_info) {
\tstruct st_susfs_try_umount info = {0};
\tstruct st_susfs_try_umount_list *new_list = NULL;

\tif (copy_from_user(&info, (struct st_susfs_try_umount __user*)*user_info, sizeof(info))) {
\t\tinfo.err = -EFAULT;
\t\tgoto out_copy_to_user;
\t}

\tif (info.mnt_mode == TRY_UMOUNT_DEFAULT) {
\t\tinfo.mnt_mode = 0;
\t} else if (info.mnt_mode == TRY_UMOUNT_DETACH) {
\t\tinfo.mnt_mode = MNT_DETACH;
\t} else {
\t\tSUSFS_LOGE("Unsupported mnt_mode: %d\\n", info.mnt_mode);
\t\tinfo.err = -EINVAL;
\t\tgoto out_copy_to_user;
\t}

\tnew_list = kzalloc(sizeof(struct st_susfs_try_umount_list), GFP_KERNEL);
\tif (!new_list) {
\t\tinfo.err = -ENOMEM;
\t\tgoto out_copy_to_user;
\t}

\tmemcpy(&new_list->info, &info, sizeof(info));
\tINIT_LIST_HEAD(&new_list->list);
\tmutex_lock(&susfs_mutex_lock_try_umount);
\tlist_add_tail(&new_list->list, &LH_TRY_UMOUNT_PATH);
\tmutex_unlock(&susfs_mutex_lock_try_umount);
\tinfo.err = 0;
out_copy_to_user:
\tif (copy_to_user(&((struct st_susfs_try_umount __user*)*user_info)->err, &info.err, sizeof(info.err))) {
\t\tinfo.err = -EFAULT;
\t}
\tSUSFS_LOGI("CMD_SUSFS_ADD_TRY_UMOUNT -> ret: %d\\n", info.err);
}

void susfs_try_umount(uid_t uid) {
\tstruct st_susfs_try_umount_list *cursor = NULL;

\tlist_for_each_entry_reverse(cursor, &LH_TRY_UMOUNT_PATH, list) {
\t\tSUSFS_LOGI("umounting '%s' for uid: %u\\n", cursor->info.target_pathname, uid);
\t\ttry_umount(cursor->info.target_pathname, cursor->info.mnt_mode);
\t}
}
#endif // #ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT

/* spoof_uname */""",
)

# 5. KSU selinux: treat all procs as non-ksu when all-procs hiding is on
patch(
    "drivers/kernelsu/selinux/selinux.c",
    """bool susfs_is_current_ksu_domain(void)
{
\treturn unlikely(current_sid() == susfs_ksu_sid);
}""",
    """#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
#include <linux/jump_label.h>
extern struct static_key_false susfs_is_hide_sus_mnts_for_all_procs_enabled;
#endif

bool susfs_is_current_ksu_domain(void)
{
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
\tif (static_branch_likely(&susfs_is_hide_sus_mnts_for_all_procs_enabled))
\t\treturn false;
#endif
\treturn unlikely(current_sid() == susfs_ksu_sid);
}""",
)

# 6. fs/susfs.c: newer APIs used by RKSU setuid hook
patch(
    "fs/susfs.c",
    '#include "mount.h"\n#include <linux/mount.h>',
    '#include "mount.h"\n#include <linux/mount.h>\n#include <linux/nsproxy.h>',
)

# existing 2.3.0 helper becomes the uid-aware variant RKSU calls
patch(
    "fs/susfs.c",
    "static void susfs_run_sus_path_loop(void) {",
    "void susfs_run_sus_path_loop(uid_t uid) {",
)
patch(
    "fs/susfs.c",
    "susfs_run_sus_path_loop();",
    "susfs_run_sus_path_loop(current_uid().val);",
)

patch(
    "fs/susfs.c",
    "/* susfs_init */",
    """#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
void susfs_reorder_mnt_id(void) {
\tstruct mnt_namespace *mnt_ns = current->nsproxy->mnt_ns;
\tstruct mount *mnt;
\tint first_mnt_id = 0;

\tif (!mnt_ns || list_empty(&mnt_ns->list))
\t\treturn;

\tfirst_mnt_id = list_first_entry(&mnt_ns->list, struct mount, mnt_list)->mnt_id;
\tlist_for_each_entry(mnt, &mnt_ns->list, mnt_list) {
\t\tif (mnt->mnt_id == DEFAULT_KSU_MNT_ID)
\t\t\tcontinue;
\t\tWRITE_ONCE(mnt->mnt_id, first_mnt_id++);
\t}
}
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT

/* susfs_init */""",
)

print("rksu susfs ext: ok")