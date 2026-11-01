#!/usr/bin/env bash
set -euo pipefail
STUDY_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
KERNEL_VERSION=${KERNEL_VERSION:-5.15.2}
KERNEL_SHA256=${KERNEL_SHA256:-5634033a4981be42d3259f50d5371a2cdc9ace5d9860da67a2879630533ab175}
KERNELSRC=${KERNELSRC:-$STUDY_ROOT/linux-$KERNEL_VERSION}
KERNEL_CC=${KERNEL_CC:-gcc-11}
ROOTFS_SUITE=${SUITE:-bookworm}
CACHE_DIR="$STUDY_ROOT/.cache"
DEBIAN_KEYRING="$CACHE_DIR/debian-bookworm.gpg"
unset KBUILD_OUTPUT
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[kernel-study] %s\n' "$*"; }
need() { local cmd; for cmd in "$@"; do command -v "$cmd" >/dev/null || die "Missing tool: $cmd. Run make deps."; done; }
require_linux() {
    [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || die 'Run inside the Ubuntu 22.04 x86-64 VM.'
    (( EUID != 0 )) || die 'Run as a normal user; make deps requests sudo when needed.'
}
kernel_make() { make --no-print-directory -C "$KERNELSRC" ARCH=x86 CC="$KERNEL_CC" HOSTCC="$KERNEL_CC" "$@"; }
