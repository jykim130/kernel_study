#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/image-common.sh"
[[ -s $ROOTFS_IMAGE && -s $ROOTFS_IMAGE.kernel-release ]] || die 'Run make image, or make update-image for an existing disk.'
[[ $(cat "$ROOTFS_IMAGE.kernel-release") == "$(cat "$KERNELSRC/include/config/kernel.release")" ]] ||
    die 'Kernel release mismatch. Run make update-image before booting.'
log 'Starting QEMU with a persistent root disk. Log in as root; run poweroff to exit.'
exec "$@"
