#!/usr/bin/env bash
# Backport path_umount() into fs/namespace.c for kernels older than 5.9.
# KernelSU needs it to unmount its own mounts before detection; without it the
# "umount modules" step silently fails on 4.19.
set -euo pipefail

cd "${1:-kernel}"

NS=fs/namespace.c
[ -f "$NS" ] || { echo "ERROR: $NS not found" >&2; exit 1; }

KVER=$(awk '/^VERSION =/{v=$3} /^PATCHLEVEL =/{p=$3} /^SUBLEVEL =/{s=$3} END{print v"."p"."s}' Makefile)
echo "kernel version: $KVER"
MAJOR=${KVER%%.*}
MINOR=$(echo "$KVER" | cut -d. -f2)
if [ "$MAJOR" -gt 5 ] || { [ "$MAJOR" -eq 5 ] && [ "$MINOR" -ge 9 ]; }; then
    echo "kernel >= 5.9 already has path_umount(); skipping"
    exit 0
fi

if grep -qE '^(static )?int path_umount' "$NS"; then
    echo "path_umount() already present; skipping"
    exit 0
fi

ANCHOR='Now umount can handle mount points as well as block devices'
grep -q "$ANCHOR" "$NS" || { echo "ERROR: anchor not found in $NS" >&2; exit 1; }

SNIPPET=$(mktemp)
if ! grep -q 'static int can_umount' "$NS"; then
cat >"$SNIPPET" <<'EOF'
static int can_umount(const struct path *path, int flags)
{
	struct mount *mnt = real_mount(path->mnt);

	if (flags & ~(MNT_FORCE | MNT_DETACH | MNT_EXPIRE | UMOUNT_NOFOLLOW))
		return -EINVAL;
	if (!may_mount())
		return -EPERM;
	if (path->dentry != path->mnt->mnt_root)
		return -EINVAL;
	if (!check_mnt(mnt))
		return -EINVAL;
	if (mnt->mnt.mnt_flags & MNT_LOCKED)
		return -EINVAL;
	if (flags & MNT_FORCE && !capable(CAP_SYS_ADMIN))
		return -EPERM;
	return 0;
}

EOF
fi
cat >>"$SNIPPET" <<'EOF'
int path_umount(struct path *path, int flags)
{
	struct mount *mnt = real_mount(path->mnt);
	int ret;

	ret = can_umount(path, flags);
	if (!ret)
		ret = do_umount(mnt, flags);

	/* we mustn't call path_put() as that would clear mnt_expiry_mark */
	dput(path->dentry);
	mntput_no_expire(mnt);
	return ret;
}

EOF

ANCHOR_LINE=$(grep -n "$ANCHOR" "$NS" | head -n1 | cut -d: -f1)
START=$ANCHOR_LINE
while [ "$START" -gt 1 ] && ! sed -n "${START}p" "$NS" | grep -q '/\*'; do
    START=$((START - 1))
done

TMP=$(mktemp)
head -n "$((START - 1))" "$NS" >"$TMP"
cat "$SNIPPET" >>"$TMP"
tail -n "+${START}" "$NS" >>"$TMP"
mv "$TMP" "$NS"
rm -f "$SNIPPET"

grep -q '^int path_umount' "$NS" || { echo "ERROR: insertion failed" >&2; exit 1; }
echo "path_umount() backported into $NS"
