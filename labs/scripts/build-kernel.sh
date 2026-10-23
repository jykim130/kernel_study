#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
reset_config=n
case ${1:-} in
    --help) echo 'Usage: bash labs/scripts/build-kernel.sh [--reset-config]'; exit 0 ;;
    --reset-config) reset_config=y; shift ;;
esac
(( $# == 0 )) || die 'Unexpected argument. Use --help.'
require_linux
need curl tar sha256sum make "$KERNEL_CC" bison flex bc
positive_integer BUILD_JOBS "$BUILD_JOBS"
lock_lab
mkdir -p "$CACHE_DIR" "$PROJECT_ROOT/src" "$KERNEL_BUILD" "$LOG_DIR"
exec > >(tee "$LOG_DIR/build-$(date +%Y%m%d-%H%M%S).log") 2>&1

if [[ ! -d $KERNEL_SRC ]]; then
    archive="$CACHE_DIR/linux-$KERNEL_VERSION.tar.xz"
    if [[ ! -f $archive ]]; then
        log "Downloading Linux $KERNEL_VERSION"
        curl --fail --location --retry 3 "$KERNEL_URL" --output "$archive.part"
        mv -- "$archive.part" "$archive"
    fi
    printf '%s  %s\n' "$KERNEL_SHA256" "$archive" | sha256sum --check -
    staging=$(mktemp -d "$CACHE_DIR/source.XXXXXX")
    tar -xJf "$archive" -C "$staging"
    mv -- "$staging/linux-$KERNEL_VERSION" "$KERNEL_SRC"
    rmdir -- "$staging"
fi
[[ -f "$KERNEL_SRC/Makefile" ]] || die 'Incomplete kernel source tree.'

if [[ ! -f "$KERNEL_BUILD/.config" || $reset_config == y ]]; then
    if [[ -f "$KERNEL_BUILD/.config" ]]; then
        cp -- "$KERNEL_BUILD/.config" "$KERNEL_BUILD/.config.backup-$(date +%Y%m%d-%H%M%S)"
    fi
    kernel_make x86_64_defconfig
    cfg=(bash "$KERNEL_SRC/scripts/config" --file "$KERNEL_BUILD/.config")
    for option in MODULES PCI VIRTIO_PCI VIRTIO_BLK VIRTIO_NET EXT4_FS \
        DEVTMPFS DEVTMPFS_MOUNT SERIAL_8250 SERIAL_8250_CONSOLE \
        PROC_FS SYSFS TMPFS DEBUG_INFO DEBUG_INFO_DWARF4 GDB_SCRIPTS; do
        "${cfg[@]}" --enable "$option"
    done
    "${cfg[@]}" --disable DEBUG_INFO_BTF --disable DEBUG_INFO_DWARF5 \
        --disable LOCALVERSION_AUTO --set-str LOCALVERSION "$KERNEL_LOCALVERSION" \
        --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''
fi

kernel_make olddefconfig
# These must be built in: no initramfs is supplied by run-qemu.sh.
for option in VIRTIO_PCI VIRTIO_BLK EXT4_FS DEVTMPFS DEVTMPFS_MOUNT SERIAL_8250_CONSOLE; do
    grep -qx "CONFIG_${option}=y" "$KERNEL_BUILD/.config" ||
        die "CONFIG_${option}=y is required for direct rootfs boot. See README."
done
log "Building Linux $KERNEL_VERSION with $BUILD_JOBS jobs"
kernel_make -j"$BUILD_JOBS" bzImage modules
require_build
log "Build complete: $(cat "$KERNEL_BUILD/include/config/kernel.release")"
printf 'bzImage: %s\nvmlinux: %s\n' "$KERNEL_BUILD/arch/x86/boot/bzImage" "$KERNEL_BUILD/vmlinux"
log 'Next: bash labs/scripts/make-rootfs.sh (or --update-modules for an existing image)'
