#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
build=n
if [[ ${1:-} == --build ]]; then build=y; shift; fi
(( $# == 0 )) || die 'Usage: make lab LAB=name, or make stage LAB=name'
[[ ${LAB:-} =~ ^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$ ]] || die 'Set LAB to a relative directory inside labs/.'
src=$(realpath -e -- "$STUDY_ROOT/labs/$LAB")
lab_base=$(realpath -e -- "$STUDY_ROOT/labs")
[[ -d $src && $src == "$lab_base"/* ]] || die 'LAB must stay inside labs/.'
if [[ $build == y ]]; then
    [[ -f $src/Makefile || -f $src/Kbuild ]] || die 'The lab needs an external module Makefile or Kbuild.'
    kernel_make M="$src" modules
fi
overlay=${ROOTFS_OVERLAY:-$STUDY_ROOT/overlay}
dest=$(realpath -m -- "$overlay/root/labs/$LAB")
base=$(realpath -m -- "$STUDY_ROOT/overlay/root/labs")
[[ $dest == "$base"/* ]] || die 'Staging is limited to the project overlay/root/labs tree.'
[[ ! -L $overlay && ! -L $overlay/root && ! -L $overlay/root/labs ]] || die 'Refusing staging through a symlink.'
need tar
mkdir -p "$CACHE_DIR"
tmp=$(mktemp -d "$CACHE_DIR/stage-lab.XXXXXX")
cleanup() { [[ $tmp == "$CACHE_DIR"/stage-lab.* && -d $tmp ]] && rm -rf -- "$tmp"; }
trap cleanup EXIT
tar -C "$src" --exclude=.git --exclude='*.o' --exclude='*.cmd' --exclude='*.mod.c' -cf - . | tar -C "$tmp" -xf -
mkdir -p "$(dirname -- "$dest")"
# dest is resolved and checked above; this tree is generated, never the lab source.
[[ ! -e $dest ]] || rm -rf -- "$dest"
mv -- "$tmp" "$dest"
trap - EXIT
log "Staged $LAB at /root/labs/$LAB. Next: make boot"
