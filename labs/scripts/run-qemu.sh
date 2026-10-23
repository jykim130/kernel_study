#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
accel=tcg
debug=n
snapshot=n
dry_run=n
gdb_port=1234
while (( $# )); do
    case $1 in
        --debug) debug=y; shift ;;
        --snapshot) snapshot=y; shift ;;
        --dry-run) dry_run=y; shift ;;
        --accel|--gdb-port)
            (( $# >= 2 )) || die "Missing value for $1."
            if [[ $1 == --accel ]]; then accel=$2; else gdb_port=$2; fi
            shift 2 ;;
        --help)
            echo 'Usage: bash labs/scripts/run-qemu.sh [--debug] [--snapshot] [--accel tcg|kvm] [--gdb-port PORT] [--dry-run]'
            exit 0 ;;
        *) die "Unknown option: $1. Use --help." ;;
    esac
done
[[ $accel == tcg || $accel == kvm ]] || die 'Acceleration must be tcg or kvm.'
positive_integer QEMU_MEMORY "$QEMU_MEMORY"
positive_integer QEMU_CPUS "$QEMU_CPUS"
positive_integer GDB_PORT "$gdb_port"
(( ${#gdb_port} <= 5 && gdb_port <= 65535 )) || die 'GDB port must be between 1 and 65535.'

# QEMU escapes a literal comma inside an option value as two commas.
drive_path=${ROOTFS_IMAGE//,/,,}
command=(qemu-system-x86_64 -machine pc -accel "$accel"
    -m "$QEMU_MEMORY" -smp "$QEMU_CPUS"
    -kernel "$KERNEL_BUILD/arch/x86/boot/bzImage"
    -drive "file=$drive_path,format=raw,if=virtio"
    -append 'root=/dev/vda rootfstype=ext4 rw rootwait console=ttyS0,115200 nokaslr'
    -netdev user,id=net0 -device virtio-net-pci,netdev=net0
    -nographic -no-reboot)
[[ $debug == n ]] || command+=(-gdb "tcp:127.0.0.1:$gdb_port" -S)
[[ $snapshot == n ]] || command+=(-snapshot)
if [[ $dry_run == y ]]; then
    printf '%q ' "${command[@]}"
    printf '\n'
    exit 0
fi

require_linux
need qemu-system-x86_64 tee
lock_lab
require_build
[[ -s $ROOTFS_IMAGE && -s $ROOTFS_IMAGE.kernel-release ]] ||
    die 'Create the guest image first: bash labs/scripts/make-rootfs.sh'
[[ $(cat "$KERNEL_BUILD/include/config/kernel.release") == "$(cat "$ROOTFS_IMAGE.kernel-release")" ]] ||
    die 'Kernel release mismatch. Run bash labs/scripts/make-rootfs.sh --update-modules.'
if [[ $accel == kvm ]]; then
    [[ -r /dev/kvm && -w /dev/kvm ]] || die '/dev/kvm is unavailable. Use default TCG or configure nested virtualization.'
fi
mkdir -p "$LOG_DIR"
log 'Starting QEMU. Guest login: root. Use poweroff in the guest to exit.'
if [[ $debug == y ]]; then
    log "CPU stopped; connect GDB to 127.0.0.1:$gdb_port and continue."
fi
"${command[@]}" 2>&1 | tee "$LOG_DIR/qemu-$(date +%Y%m%d-%H%M%S).log"
