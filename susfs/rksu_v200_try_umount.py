import sys

HDR = "include/linux/susfs.h"
SRC = "fs/susfs.c"

HDR_BLOCK = '''#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
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

/* susfs_init */'''

SRC_BLOCK = '''#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
#include <linux/mount.h>

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

/* susfs_init */'''

for path, block in ((HDR, HDR_BLOCK), (SRC, SRC_BLOCK)):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "struct st_susfs_try_umount" in text:
        print(path, "already patched")
        continue
    marker = "/* susfs_init */"
    if marker not in text:
        sys.exit(f"{path}: susfs_init marker not found")
    text = text.replace(marker, block, 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(path, "try_umount added")
