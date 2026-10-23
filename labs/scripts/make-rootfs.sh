#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
update_modules=n
case ${1:-} in
    --help) echo 'Usage: bash labs/scripts/make-rootfs.sh [--update-modules]'; exit 0 ;;
    --update-modules) update_modules=y; shift ;;
esac
(( $# == 0 )) || die 'Unexpected argument. Use --help.'
require_linux
lock_lab
mkdir -p "$IMAGE_DIR"
if [[ -e $ROOTFS_IMAGE && $update_modules == n ]]; then
    log "Image already exists; leaving it unchanged: $ROOTFS_IMAGE"
    log 'To install rebuilt modules, use --update-modules.'
    exit 0
fi
if [[ $update_modules == y && ! -f $ROOTFS_IMAGE ]]; then
    die 'No rootfs image exists. Run this script without --update-modules first.'
fi
require_build
need sudo make "$KERNEL_CC" mount umount mountpoint mktemp
sudo -v
mount_dir=$(mktemp -d "$CACHE_DIR/rootfs-mount.XXXXXX")
work_image=''

cleanup() {
    local result=$?
    trap - EXIT
    # Never remove a directory while it or a descendant is still mounted.
    if mountpoint -q "$mount_dir"; then
        if ! sudo umount -R "$mount_dir"; then
            printf 'Cleanup failed. Mount left at: %s\nImage: %s\n' "$mount_dir" "${work_image:-$ROOTFS_IMAGE}" >&2
            exit 1
        fi
    fi
    rmdir -- "$mount_dir" || result=1
    if [[ -n $work_image && -f $work_image ]]; then
        printf 'Incomplete image retained at: %s\n' "$work_image" >&2
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ $update_modules == y ]]; then
    sudo mount -o loop "$ROOTFS_IMAGE" "$mount_dir"
else
    need debootstrap mkfs.ext4 truncate
    [[ $GUEST_ROOT_PASSWORD != *$'\n'* && $GUEST_ROOT_PASSWORD != *$'\r'* ]] || die 'Password must be one line.'
    # Ubuntu 22.04 may ship a Debian keyring older than the Bookworm keys.
    # Prepare pinned official keys before allocating or mounting the new image.
    bash "$PROJECT_ROOT/scripts/prepare-debian-keyring.sh"
    work_image=$(mktemp "$IMAGE_DIR/.rootfs.XXXXXX.img")
    truncate -s "$ROOTFS_SIZE" "$work_image"
    # Explicit features avoid newer ext4 defaults unsupported by Linux 5.15.
    mkfs.ext4 -q -F -O none,has_journal,ext_attr,dir_index,filetype,extent,sparse_super,large_file,uninit_bg,extra_isize "$work_image"
    sudo mount -o loop "$work_image" "$mount_dir"
    log "Installing Debian $ROOTFS_SUITE amd64"
    sudo debootstrap --arch=amd64 --variant=minbase --include=ca-certificates \
        --keyring="$DEBIAN_KEYRING" \
        "$ROOTFS_SUITE" "$mount_dir" "$ROOTFS_MIRROR"
    sudo mount -t proc proc "$mount_dir/proc"
    sudo mount -t sysfs sysfs "$mount_dir/sys"
    sudo mount --bind /dev "$mount_dir/dev"
    sudo mount --make-private "$mount_dir/dev"
    printf '#!/bin/sh\nexit 101\n' | sudo tee "$mount_dir/usr/sbin/policy-rc.d" >/dev/null
    sudo chmod 755 "$mount_dir/usr/sbin/policy-rc.d"
    sudo cp -L /etc/resolv.conf "$mount_dir/etc/resolv.conf"
    sudo chroot "$mount_dir" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
    sudo chroot "$mount_dir" /usr/bin/env DEBIAN_FRONTEND=noninteractive \
        apt-get install -y --no-install-recommends \
        systemd-sysv udev kmod iproute2 iputils-ping procps vim-tiny ca-certificates
    printf '%s\n' "$GUEST_HOSTNAME" | sudo tee "$mount_dir/etc/hostname" >/dev/null
    printf '127.0.0.1 localhost\n127.0.1.1 %s\n' "$GUEST_HOSTNAME" | sudo tee "$mount_dir/etc/hosts" >/dev/null
    printf '/dev/vda / ext4 defaults 0 1\n' | sudo tee "$mount_dir/etc/fstab" >/dev/null
    printf 'nameserver 10.0.2.3\n' | sudo tee "$mount_dir/etc/resolv.conf" >/dev/null
    sudo mkdir -p "$mount_dir/etc/systemd/network"
    printf '[Match]\nName=en* eth*\n\n[Network]\nDHCP=yes\n' | \
        sudo tee "$mount_dir/etc/systemd/network/20-wired.network" >/dev/null
    sudo systemctl --root="$mount_dir" enable serial-getty@ttyS0.service systemd-networkd.service
    printf 'root:%s\n' "$GUEST_ROOT_PASSWORD" | sudo chroot "$mount_dir" chpasswd
    sudo chroot "$mount_dir" apt-get clean
    sudo rm -f -- "$mount_dir/usr/sbin/policy-rc.d"
fi

log 'Installing kernel modules into the guest image'
sudo make --no-print-directory -C "$KERNEL_SRC" O="$KERNEL_BUILD" \
    ARCH=x86 CC="$KERNEL_CC" HOSTCC="$KERNEL_CC" \
    INSTALL_MOD_PATH="$mount_dir" INSTALL_MOD_STRIP=1 modules_install
release=$(cat "$KERNEL_BUILD/include/config/kernel.release")
printf '%s\n' "$release" | sudo tee "$mount_dir/etc/kernel-study-release" >/dev/null
sync
sudo umount -R "$mount_dir"
if [[ $update_modules == n ]]; then
    mv -- "$work_image" "$ROOTFS_IMAGE"
    work_image=''
fi
printf '%s\n' "$release" > "$ROOTFS_IMAGE.kernel-release"
log "Guest image ready for $release: $ROOTFS_IMAGE"
log 'Next: bash labs/scripts/run-qemu.sh'
