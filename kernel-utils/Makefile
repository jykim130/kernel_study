# Project defaults around aweeraman/kernel-utils; see UPSTREAM.md.
.DEFAULT_GOAL := help
-include local.mk

KERNEL_VERSION := 5.15.2
KERNEL_SHA256 := 5634033a4981be42d3259f50d5371a2cdc9ace5d9860da67a2879630533ab175
KERNELSRC ?= $(CURDIR)/linux-$(KERNEL_VERSION)
KERNEL_CC ?= gcc-11
SUITE ?= bookworm
GUEST_SHELL ?= /bin/bash
EXTRA_PACKAGES ?=
comma := ,
INCLUDEPKGS ?= bash,strace,kmod,util-linux,e2fsprogs,iproute2,iputils-ping,procps,vim-tiny,ca-certificates,udhcpc$(if $(strip $(EXTRA_PACKAGES)),$(comma)$(EXTRA_PACKAGES))
INSTALL_MOD_STRIP ?= 1
export INSTALL_MOD_STRIP
ROOTFS_OVERLAY ?= $(CURDIR)/overlay
OUTPUT_ROOT ?= $(CURDIR)/out
QEMU_MEMORY ?= 2G
QEMU_CPUS ?= 2
ACCEL ?= tcg
DISK ?=
EXTRA_QEMU_ARGS ?=
NETWORK_ARGS ?= -netdev user,id=net0 -device virtio-net-pci,netdev=net0
DISK_ARGS = -drive file=$(DISK)$(comma)format=raw$(comma)if=virtio
QEMU_EXTRA_ARGS ?= -accel $(ACCEL) $(NETWORK_ARGS) $(if $(strip $(DISK)),$(DISK_ARGS)) $(EXTRA_QEMU_ARGS)
KERNEL_EXTRA_ARGS ?= nokaslr
MMDEBSTRAP_FLAGS ?= $(if $(filter bookworm,$(SUITE)),--keyring='$(CURDIR)/.cache/debian-bookworm.gpg')

export KERNEL_VERSION KERNEL_SHA256 KERNELSRC KERNEL_CC SUITE OUTPUT_ROOT LAB
export CC = $(KERNEL_CC)
export HOSTCC = $(KERNEL_CC)
unexport KBUILD_OUTPUT

include upstream.mk
include study.mk

export TARGET_ARCH ROOTFS_OVERLAY OUTPUT_DIR MODULES_DIR ROOTFS INITRAMFS SERIAL_LOG
