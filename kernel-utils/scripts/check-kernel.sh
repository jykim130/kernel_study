#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
[[ ${TARGET_ARCH:-amd64} == amd64 ]] || die 'This study workflow currently supports TARGET_ARCH=amd64 only.'
for path in .config Makefile arch/x86/boot/bzImage include/config/kernel.release modules.order; do
    [[ -f $KERNELSRC/$path ]] || die "Missing kernel artifact: $path. Run make kernel-config, then build the kernel and modules."
done
for option in MODULES BINFMT_ELF BLOCK PCI VIRTIO VIRTIO_PCI VIRTIO_BLK EXT4_FS \
    DEVTMPFS DEVTMPFS_MOUNT PROC_FS SYSFS TMPFS SERIAL_8250_CONSOLE \
    CGROUPS INOTIFY_USER SIGNALFD TIMERFD EPOLL UNIX DEBUG_FS ACPI; do
    grep -qx "CONFIG_${option}=y" "$KERNELSRC/.config" || die "CONFIG_${option}=y is required. Run make kernel-config and rebuild."
done
