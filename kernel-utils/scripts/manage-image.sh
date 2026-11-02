#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/image-common.sh"
mode=${1:-}
case $mode in create|update|rebuild) ;; *) die 'Usage: manage-image.sh create|update|rebuild' ;; esac
if [[ $mode == create && -s $ROOTFS_IMAGE ]]; then
    log "Reusing root disk: $ROOTFS_IMAGE"
    exit 0
fi
if [[ $mode == update ]]; then
    [[ -s $ROOTFS_IMAGE ]] || die 'No root disk exists. Run make image first.'
fi
need sudo mount umount mountpoint mktemp tar truncate mkfs.ext4 make
sudo -v
ROOTFS=${ROOTFS:-$STUDY_ROOT/out/${TARGET_ARCH:-amd64}/rootfs.tar}
MODULES_DIR=${MODULES_DIR:-$STUDY_ROOT/out/${TARGET_ARCH:-amd64}/modules}
ROOTFS_OVERLAY=${ROOTFS_OVERLAY-$STUDY_ROOT/overlay}
if [[ $mode == update ]]; then
    make --no-print-directory -C "$STUDY_ROOT" copy-modules
else
    make --no-print-directory -C "$STUDY_ROOT" rootfs
fi
mount_dir=$(mktemp -d /tmp/kernel-study-rootfs.XXXXXX)
work_image=''
cleanup() {
    local result=$?
    trap - EXIT
    if mountpoint -q "$mount_dir"; then
        if ! sudo umount "$mount_dir"; then
            printf 'Unmount failed. Mount retained: %s\nImage: %s\n' "$mount_dir" "${work_image:-$ROOTFS_IMAGE}" >&2
            exit 1
        fi
    fi
    rmdir -- "$mount_dir" || result=1
    if [[ -n $work_image && -f $work_image ]]; then
        printf 'Incomplete image retained: %s\n' "$work_image" >&2
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ $mode == update ]]; then
    sudo mount -o loop "$ROOTFS_IMAGE" "$mount_dir"
    # Updates are limited to the module tree and the explicitly staged overlay.
    # Do not reapply account, network, systemd or filesystem configuration.
    tar --owner=0 --group=0 -C "$MODULES_DIR" -cpf - lib/modules |
        sudo tar --numeric-owner -xpf - -C "$mount_dir"
    if [[ -n $ROOTFS_OVERLAY && -d $ROOTFS_OVERLAY ]]; then
        tar --owner=0 --group=0 -C "$ROOTFS_OVERLAY" -cpf - . |
            sudo tar --numeric-owner -xpf - -C "$mount_dir"
    fi
else
    work_image=$(mktemp "$(dirname -- "$ROOTFS_IMAGE")/.rootfs.XXXXXX.img")
    truncate -s "${ROOTFS_SIZE:-4G}" "$work_image"
    # Pin features rather than inheriting newer host defaults (e.g. orphan_file).
    mkfs.ext4 -q -F -O none,has_journal,ext_attr,dir_index,filetype,extent,sparse_super,large_file,uninit_bg,extra_isize "$work_image"
    sudo mount -o loop "$work_image" "$mount_dir"
    sudo tar --numeric-owner -xpf "$ROOTFS" -C "$mount_dir"
fi
release=$(cat "$KERNELSRC/include/config/kernel.release")
printf '%s\n' "$release" | sudo tee "$mount_dir/etc/kernel-study-release" >/dev/null
sudo sync -f "$mount_dir"
sudo umount "$mount_dir"

if [[ $mode != update ]]; then
    if [[ -e $ROOTFS_IMAGE ]]; then
        backup="$ROOTFS_IMAGE.bak.$(date +%Y%m%d-%H%M%S).$$"
        # Keep the old inode before atomically publishing the completed new disk.
        ln -- "$ROOTFS_IMAGE" "$backup"
        if [[ -f $ROOTFS_IMAGE.kernel-release ]]; then
            cp -- "$ROOTFS_IMAGE.kernel-release" "$backup.kernel-release"
        fi
        log "Previous root disk preserved: $backup"
    fi
    mv -f -- "$work_image" "$ROOTFS_IMAGE"
    work_image=''
fi
printf '%s\n' "$release" > "$ROOTFS_IMAGE.kernel-release"
log "Root disk ready for $release: $ROOTFS_IMAGE"
log 'Next: make boot. Guest login: root (default password: kernel). Exit: poweroff.'
