# Linux 5.15.2 tar.xz checksum from kernel.org/pub/linux/kernel/v5.x/sha256sums.asc.
KERNEL_VERSION=5.15.2
KERNEL_SHA256=5634033a4981be42d3259f50d5371a2cdc9ace5d9860da67a2879630533ab175
KERNEL_URL="https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-${KERNEL_VERSION}.tar.xz"
KERNEL_LOCALVERSION=-kernel-study
KERNEL_CC=gcc-11

ROOTFS_SUITE=bookworm
ROOTFS_MIRROR=https://deb.debian.org/debian
ROOTFS_SIZE=4G
GUEST_HOSTNAME=kernel-study
GUEST_ROOT_PASSWORD=${GUEST_ROOT_PASSWORD:-kernel}

# At most four jobs by default to limit memory use in the Ubuntu VM.
if [[ -z ${BUILD_JOBS:-} ]]; then
    BUILD_JOBS=$(nproc)
    (( BUILD_JOBS <= 4 )) || BUILD_JOBS=4
fi
QEMU_MEMORY=${QEMU_MEMORY:-1024}
QEMU_CPUS=${QEMU_CPUS:-2}

CACHE_DIR="$PROJECT_ROOT/.cache"
DEBIAN_KEYRING="$CACHE_DIR/debian-bookworm.gpg"
KERNEL_SRC="$PROJECT_ROOT/src/linux-$KERNEL_VERSION"
KERNEL_BUILD="$PROJECT_ROOT/build/linux-$KERNEL_VERSION"
IMAGE_DIR="$PROJECT_ROOT/images"
ROOTFS_IMAGE="$IMAGE_DIR/rootfs.img"
LOG_DIR="$PROJECT_ROOT/logs"
