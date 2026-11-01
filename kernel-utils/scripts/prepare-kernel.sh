#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
[[ ! -d $KERNELSRC ]] || { [[ -f $KERNELSRC/Makefile ]] || die "Incomplete source directory: $KERNELSRC"; log "Keeping existing source: $KERNELSRC"; exit 0; }
need curl sha256sum tar mktemp
mkdir -p "$CACHE_DIR" "$(dirname -- "$KERNELSRC")"
archive="$CACHE_DIR/linux-$KERNEL_VERSION.tar.xz"
if [[ ! -f $archive ]]; then
    curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' \
        "https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-$KERNEL_VERSION.tar.xz" --output "$archive.part"
    mv -- "$archive.part" "$archive"
fi
printf '%s  %s\n' "$KERNEL_SHA256" "$archive" | sha256sum --check -
staging=$(mktemp -d "$CACHE_DIR/kernel-extract.XXXXXX")
cleanup() { [[ $staging == "$CACHE_DIR"/kernel-extract.* && -d $staging ]] && rm -rf -- "$staging"; }
trap cleanup EXIT
tar -xJf "$archive" -C "$staging"
[[ -f $staging/linux-$KERNEL_VERSION/Makefile ]] || die 'Archive has no kernel Makefile.'
mv -- "$staging/linux-$KERNEL_VERSION" "$KERNELSRC"
log "Source ready: $KERNELSRC"
