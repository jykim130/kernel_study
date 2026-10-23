#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ ${1:-} == --help ]]; then
    echo 'Usage: bash labs/scripts/install-deps.sh (Ubuntu 22.04 amd64)'
    exit 0
fi
(( $# == 0 )) || die 'Unexpected argument. Use --help.'
require_linux
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 22.04 ]] ||
    die 'The documented dependency baseline is Ubuntu 22.04 LTS amd64.'
need sudo
sudo apt-get update
sudo apt-get install -y \
    build-essential gcc-11 bc bison flex libncurses-dev libssl-dev libelf-dev \
    dwarves pkg-config git curl ca-certificates gnupg xz-utils cpio kmod \
    e2fsprogs util-linux debootstrap debian-archive-keyring \
    qemu-system-x86 qemu-utils gdb python3
log 'Dependencies installed. Next: bash labs/scripts/build-kernel.sh'
