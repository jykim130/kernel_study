#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
need make "$KERNEL_CC"
[[ -f $KERNELSRC/Makefile && -f $KERNELSRC/scripts/config ]] || die 'Run make source first.'
[[ -f $KERNELSRC/.config ]] || kernel_make x86_64_defconfig
cfg=(bash "$KERNELSRC/scripts/config" --file "$KERNELSRC/.config")
for option in MODULES BLK_DEV_INITRD RD_GZIP BINFMT_ELF PCI VIRTIO_PCI VIRTIO_BLK VIRTIO_NET \
    NET INET UNIX PACKET NETDEVICES EXT4_FS BLK_DEV_LOOP DEVTMPFS DEVTMPFS_MOUNT \
    SERIAL_8250 SERIAL_8250_CONSOLE PROC_FS SYSFS TMPFS DEBUG_FS DEBUG_KERNEL \
    DEBUG_INFO DEBUG_INFO_DWARF4 GDB_SCRIPTS; do
    "${cfg[@]}" --enable "$option"
done
"${cfg[@]}" --disable DEBUG_INFO_BTF --disable DEBUG_INFO_DWARF5 --disable LOCALVERSION_AUTO \
    --set-str LOCALVERSION '-kernel-study' --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''
kernel_make olddefconfig
log 'Configuration ready. Build in the kernel source directory with make -j$(nproc).'
