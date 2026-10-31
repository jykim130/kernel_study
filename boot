#!/usr/bin/env bash
# Lab-style entry point; run-qemu.sh owns the QEMU configuration and checks.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source "$repo_dir/labs/scripts/common.sh"

usage() {
    printf 'Usage: ./boot linux-%s [--debug] [--snapshot] [--accel tcg|kvm] [--gdb-port PORT] [--dry-run]\n' "$KERNEL_VERSION"
}

if [[ ${1:-} == --help ]]; then
    usage
    exit 0
fi
if (( $# == 0 )); then
    usage >&2
    exit 1
fi
[[ $1 == "linux-$KERNEL_VERSION" ]] ||
    die "Kernel must match labs/config/lab.conf.sh: linux-$KERNEL_VERSION"
shift

exec bash "$repo_dir/labs/scripts/run-qemu.sh" "$@"
