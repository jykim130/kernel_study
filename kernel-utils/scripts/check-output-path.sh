#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
# Upstream clean/distclean use rm -rf. Only the project's out tree is disposable.
candidate=$(realpath -m -- "${OUTPUT_ROOT:-$STUDY_ROOT/out}")
allowed=$(realpath -m -- "$STUDY_ROOT/out")
[[ $candidate == "$allowed" || $candidate == "$allowed"/* ]] || die 'Cleanup is limited to kernel-utils/out. Refusing this OUTPUT_ROOT.'
[[ ! -L $STUDY_ROOT/out ]] || die 'Refusing cleanup through a symlinked out directory.'
for value in "${OUTPUT_DIR:-$candidate/${TARGET_ARCH:-amd64}}" "${MODULES_DIR:-$candidate/${TARGET_ARCH:-amd64}/modules}" \
    "${ROOTFS:-$candidate/${TARGET_ARCH:-amd64}/rootfs.tar}" "${INITRAMFS:-$candidate/${TARGET_ARCH:-amd64}/initramfs.cpio}" \
    "${SERIAL_LOG:-$candidate/${TARGET_ARCH:-amd64}/console.log}"; do
    resolved=$(realpath -m -- "$value")
    [[ $resolved == "$allowed"/* ]] || die 'Generated paths must stay inside kernel-utils/out.'
done
case ${TARGET_ARCH:-amd64} in amd64|arm64|riscv64) ;; *) die 'Unsupported target architecture.' ;; esac
