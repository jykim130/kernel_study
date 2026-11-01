# Local preparation and lab delivery. Boot/image/debug recipes remain upstream.
.NOTPARALLEL:

# Ubuntu 22.04 x86-64 baseline; other guest architectures are opt-in later.
HOST_DEPS := build-essential gcc-11 bc bison flex libncurses-dev libssl-dev \
 libelf-dev pkg-config git curl ca-certificates gnupg xz-utils cpio kmod \
 e2fsprogs util-linux mmdebstrap libarchive-tools uidmap debian-archive-keyring \
 qemu-system-x86 qemu-utils gdb-multiarch python3

.PHONY: source kernel-config kernel keys check-linux check-kernel lab stage test

check-linux:
	bash scripts/check-linux.sh

deps: check-linux

source: check-linux
	bash scripts/prepare-kernel.sh

kernel-config: source
	bash scripts/configure-kernel.sh

kernel: kernel-config
	$(MAKE) -C "$(KERNELSRC)" ARCH=x86 CC="$(KERNEL_CC)" HOSTCC="$(KERNEL_CC)" -j$$(nproc)

keys: check-linux
	@if test "$(SUITE)" = bookworm && ! test -s .cache/debian-bookworm.gpg; then bash scripts/prepare-debian-keyring.sh; fi

check-kernel: check-linux
	bash scripts/check-kernel.sh

check-image: check-kernel check-output-path keys
check-boot: check-kernel
check-gdb: check-linux
copy-modules: check-kernel check-output-path
boot-log: check-linux check-output-path

# Repackage after settings or staged lab files change. Removed files update the
# parent directory mtime. Package additions can also be forced with make rebuild.
OVERLAY_INPUTS := $(shell find "$(ROOTFS_OVERLAY)" -type f -o -type d 2>/dev/null)
KERNEL_MODULE_INPUTS := $(wildcard $(addprefix $(KERNELSRC)/,$(shell cat "$(MODULES_ORDER)" 2>/dev/null)))
$(INITRAMFS): Makefile study.mk $(wildcard local.mk) $(OVERLAY_INPUTS) $(KERNEL_MODULE_INPUTS)

lab: check-kernel
	bash scripts/stage-lab.sh --build

stage: check-linux
	bash scripts/stage-lab.sh

test:
	python3 -B tests/test_workflow.py -v

clean distclean: check-linux check-output-path
.PHONY: check-output-path
check-output-path:
	bash scripts/check-output-path.sh

# Reuse the upstream INIT hook, adding loopback and best-effort guest DHCP.
# This is the guest's /init, not a service installed on the Ubuntu host.
define INIT
#!/bin/sh
set -eu
mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs dev /dev
mount -t debugfs none /sys/kernel/debug
hostname kernel-study
export TERM=xterm-256color
ip link set lo up
for iface in /sys/class/net/*; do
    name=$${iface##*/}
    [ "$$name" = lo ] && continue
    ip link set "$$name" up
    udhcpc -n -q -i "$$name" || echo "DHCP unavailable; configure the network manually."
    break
done
exec agetty --autologin root --noclear $(CONSOLE) linux
endef

help: study-help
.PHONY: study-help
study-help:
	@echo "kernel-study: Ubuntu 22.04 x86-64 / Linux $(KERNEL_VERSION) / Debian $(SUITE)"
	@echo "  make source          Download and verify the kernel source"
	@echo "  make kernel-config   Prepare an in-tree configuration (preserves source edits)"
	@echo "  make kernel          Configure and build; manual make in the kernel tree also works"
	@echo "  make lab LAB=name    Build external modules from labs/name and stage their files"
	@echo "  make stage LAB=name  Stage already-built lab files without compiling"
	@echo "  make test            Run isolated, unprivileged workflow tests"
	@echo "  make boot DISK=/absolute/path/to/disk.img   Attach an existing raw disk"
	@echo "  make rebuild EXTRA_PACKAGES=package1,package2   Add guest tools"
	@echo "  Copy local.mk.example to local.mk for persistent local settings."
