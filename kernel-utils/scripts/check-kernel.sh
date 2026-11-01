#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
for path in .config Makefile arch/x86/boot/bzImage include/config/kernel.release modules.order; do
    [[ -f $KERNELSRC/$path ]] || die "Missing kernel artifact: $path. Run make kernel-config, then build the kernel and modules."
done
for option in MODULES BLK_DEV_INITRD DEVTMPFS PROC_FS SYSFS DEBUG_FS SERIAL_8250_CONSOLE; do
    grep -qx "CONFIG_${option}=y" "$KERNELSRC/.config" || die "CONFIG_${option}=y is required. Run make kernel-config and rebuild."
done
