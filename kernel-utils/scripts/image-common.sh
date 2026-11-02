#!/usr/bin/env bash
# Sourced by the disk manager and QEMU launcher.
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
bash "$STUDY_ROOT/scripts/check-output-path.sh"
ROOTFS_IMAGE=${ROOTFS_IMAGE:-$STUDY_ROOT/disks/rootfs.img}
image_base=$(realpath -m -- "$STUDY_ROOT/disks")
image_path=$(realpath -m -- "$ROOTFS_IMAGE")
[[ ! -L $STUDY_ROOT/disks && ! -L $ROOTFS_IMAGE && $image_path == "$image_base"/* ]] ||
    die 'ROOTFS_IMAGE must be a regular image inside kernel-utils/disks, without symlinks.'
[[ $image_path != *[[:space:],\'\"]* ]] || die 'ROOTFS_IMAGE cannot contain whitespace, commas or quotes.'
[[ ! -e $ROOTFS_IMAGE || -f $ROOTFS_IMAGE ]] || die 'ROOTFS_IMAGE is not a regular file.'
[[ ! -L $ROOTFS_IMAGE.lock && ! -L $ROOTFS_IMAGE.kernel-release ]] || die 'Refusing symlinked image metadata.'
need flock
mkdir -p -- "$(dirname -- "$ROOTFS_IMAGE")"
exec 9>"$ROOTFS_IMAGE.lock"
flock -n 9 || die 'The root disk is in use. Shut down QEMU or wait for the image operation to finish.'
