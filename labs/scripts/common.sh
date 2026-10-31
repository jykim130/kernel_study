#!/usr/bin/env bash
# PROJECT_ROOT is the labs workspace; caller commands in README use the repo root.
# Paths are independent of the caller's working directory.
set -euo pipefail
PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
source "$PROJECT_ROOT/config/lab.conf.sh"
# An old shell setting must not redirect an in-tree build elsewhere.
unset KBUILD_OUTPUT

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '\n[kernel-study] %s\n' "$*"; }
need() {
    local cmd
    for cmd in "$@"; do
        command -v "$cmd" >/dev/null 2>&1 || die "Missing tool: $cmd. Run bash labs/scripts/install-deps.sh first."
    done
}
require_linux() {
    [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] ||
        die 'Run this command inside the VMware Ubuntu Linux x86_64 guest.'
    (( EUID != 0 )) || die 'Run as a normal user; the script requests sudo when needed.'
}
positive_integer() {
    [[ $2 =~ ^[1-9][0-9]*$ ]] || die "$1 must be a positive integer."
}
lock_lab() {
    need flock
    mkdir -p "$CACHE_DIR"
    exec 9>"$CACHE_DIR/lab.lock"
    flock -n 9 || die 'Another build, image operation or QEMU is using this project.'
}
kernel_make() {
    make --no-print-directory -C "$KERNEL_SRC" \
        ARCH=x86 CC="$KERNEL_CC" HOSTCC="$KERNEL_CC" "$@"
}
require_build() {
    [[ -s "$KERNEL_BUILD/arch/x86/boot/bzImage" &&
       -s "$KERNEL_BUILD/include/config/kernel.release" &&
       -f "$KERNEL_BUILD/modules.order" ]] ||
        die 'Build the kernel and modules first: bash labs/scripts/build-kernel.sh'
}
