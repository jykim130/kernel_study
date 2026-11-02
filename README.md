# Linux 커널 스터디 실습 환경

**Ubuntu 22.04 LTS x86-64 VM**에서 **Linux 5.15.2**를 직접 빌드하고,
[aweeraman/kernel-utils](https://github.com/aweeraman/kernel-utils) 기반 Makefile로
**Debian Bookworm + systemd + 영구 ext4 루트 디스크**를 만들어 QEMU에서 실행합니다.
이전 셸 스크립트 환경처럼 게스트의 파일·설정이 유지되고 `poweroff`로 종료합니다.

```text
실제 PC → VMware 또는 VirtualBox → Ubuntu 개발 VM
                                      └─ QEMU: Linux 5.15.2
                                                + Debian/systemd
                                                + disks/rootfs.img (ext4)
```

커널 소스 수정·빌드는 Ubuntu에서 하고 QEMU 게스트에서 모듈 적재와 테스트를 합니다.
아래 명령은 모두 **Windows가 아닌 Ubuntu VM의 터미널**에서 실행합니다.
VM 시작 사양은 CPU 4개, RAM 8GB, 디스크 60GB를 권장합니다.
QEMU 기본값은 TCG, CPU 2개, RAM 2GB입니다. 프로젝트 경로에는 공백·쉼표·따옴표를 사용하지 않습니다.

## 디렉토리 구조

커널 소스와 생성물은 Git에 포함하지 않습니다.

```text
kernel_study/
├─ README.md
└─ kernel-utils/
   ├─ Makefile              # 프로젝트 기본값
   ├─ upstream.mk           # 원본에서 수정한 이미지·부팅·디버깅 규칙
   ├─ study.mk              # 커널 준비·실습 전달·환경 확인
   ├─ COPYING, UPSTREAM.md  # 원본 라이선스와 버전·변경점
   ├─ local.mk.example      # 개인 설정 예시
   ├─ scripts/, tests/      # 준비·이미지 관리 도구와 회귀 테스트
   ├─ linux-5.15.2/         # 생성: 소스·.config·빌드 결과
   ├─ labs/                 # 호스트에서 관리할 실습 코드
   ├─ overlay/              # 이미지 생성·갱신 때 전달할 파일
   ├─ .cache/               # 생성: 다운로드·검증한 서명 키
   ├─ out/amd64/            # 생성: 임시 rootfs.tar·모듈·콘솔 로그
   └─ disks/                # 생성: rootfs.img·메타데이터·백업·추가 실습 디스크
```

중첩 Git 저장소나 서브모듈은 사용하지 않습니다.
고정한 원본 커밋과 수정점은 [UPSTREAM.md](kernel-utils/UPSTREAM.md)에 기록합니다.

## 1. 저장소와 의존성 준비

```bash
sudo apt-get update
sudo apt-get install -y git
mkdir -p ~/work
cd ~/work
git clone https://github.com/jykim130/kernel_study.git
cd kernel_study/kernel-utils

sudo apt-get update
make deps
```

GCC 11, 커널 빌드 도구, QEMU, GDB, mmdebstrap, uidmap, ext4 도구 등을 설치합니다.
이후 기본 작업 위치는 **`kernel-utils/`**입니다. 명령 전체에 `sudo`를 붙이지 않습니다.
Debian 사용자 공간 생성에는 `mmdebstrap --mode=unshare`를 사용하므로 일반 사용자의
user namespace와 `/etc/subuid`, `/etc/subgid` 범위가 필요합니다.
디스크를 마운트해 파일을 넣는 단계에서는 스크립트가 필요한 명령에만 `sudo`를 사용합니다.

## 2. 커널 소스와 설정

```bash
make source
make kernel-config
```

`make source`는 kernel.org의 tar.xz를 받아 고정된 SHA-256을 확인하고
`linux-5.15.2/`에 풉니다. 기존 소스를 덮어쓰지 않습니다.
`make kernel-config`는 `.config`가 없을 때 `x86_64_defconfig`를 생성하고,
모듈·시리얼 콘솔·virtio·ext4·systemd용 cgroup·ACPI 종료·GDB 옵션을 적용합니다.
initramfs 없이 루트 디스크를 읽으므로 **virtio 블록 드라이버와 ext4는 `=y`로 커널에 내장**합니다.
특정 Lab의 옵션은 해당 실습에서 추가합니다.

설정부터 직접 해보려면 다음 순서도 가능합니다.

```bash
cd linux-5.15.2
make defconfig
cd ..
make kernel-config
```

`make defconfig`는 설정 초기화이므로 코드 수정 후마다 반복하지 않습니다.

## 3. 커널 직접 빌드

```bash
cd linux-5.15.2
make -j$(nproc)
cd ..
```

소스와 출력은 같은 디렉토리에 있고 `O=` 옵션을 사용하지 않습니다.
주요 결과는 `linux-5.15.2/arch/x86/boot/bzImage`, `linux-5.15.2/vmlinux`이며,
기본 릴리스는 `5.15.2-kernel-study`입니다.
준비와 빌드를 한 번에 수행하는 편의 명령은 `make kernel`입니다.

## 4. 영구 루트 디스크 생성과 부팅

```bash
make print-config
make image
make boot
```

`make image`는 Debian Bookworm 사용자 공간, systemd, 커널 모듈과 `overlay/`를 담은
**`disks/rootfs.img`**를 만듭니다. 기본 크기는 4GiB이며 파일은 sparse 형식입니다.
완성 전에는 임시 이미지로 작업하고, 파일을 넣고 마운트 해제를 마친 뒤 최종 경로에 둡니다.
**이미지가 이미 있으면 그대로 재사용**하므로 게스트에서 만든 파일을 덮어쓰지 않습니다.

Ubuntu의 오래된 Debian 키링 문제를 피하도록 공식 Bookworm 키의 fingerprint를 검증합니다.
올바른 캐시는 재사용하고, 없거나 잘못된 캐시는 다시 준비합니다.
공개키를 `/tmp`에 임시 복사하므로 홈 디렉터리가 `700`·`750`이어도 사용할 수 있습니다.
저장소의 `signed-by`에도 fingerprint를 명시해 Ubuntu 22.04의 mmdebstrap이
오래된 시스템 키링을 자동 선택하는 문제를 피합니다. 게스트에는 `debian-archive-keyring`을 포함합니다.

QEMU는 `root=/dev/vda`로 디스크를 직접 마운트하고 `/sbin/init`을 실행합니다.
**PID 1은 systemd**이고, 시리얼 콘솔에서 다음 계정으로 로그인합니다.

```text
kernel-study login: root
Password: kernel
```

게스트에서 확인합니다.

```bash
uname -r
ps -p 1 -o pid,comm,args
findmnt /
systemctl is-system-running
ip -br address
```

virtio NIC와 QEMU user networking을 사용하며 systemd-networkd가 DHCP로 주소를 받습니다.
루트 디스크의 파일·설정·설치한 패키지는 다음 부팅에도 유지됩니다.

종료는 **게스트 안에서** 실행합니다.

```bash
poweroff
```

systemd가 서비스와 파일시스템을 정리하고 QEMU가 종료되면 호스트 터미널로 돌아옵니다.
`Ctrl+A`를 누른 뒤 `X`는 게스트가 응답하지 않을 때 QEMU를 강제 종료하는 용도입니다.

`make boot-log`는 콘솔을 `out/amd64/console.log`로 보냅니다.
이 모드에서는 터미널의 대화형 로그인 대신 로그 파일을 확인합니다.

## 5. 커널·실습 파일 갱신

먼저 게스트에서 `poweroff`로 QEMU를 종료합니다. 커널을 수정했다면 호스트에서:

```bash
cd linux-5.15.2
make -j$(nproc)
cd ..
make update-image
make boot
```

`make update-image`는 새 커널 모듈과 `overlay/`의 파일만 기존 디스크에 복사합니다.
계정·네트워크 설정과 그 밖의 게스트 데이터는 유지합니다.
모듈은 설치할 때 strip하며 호스트의 원본 `.ko`는 보존합니다.
overlay와 같은 경로에 있는 게스트 파일은 덮어쓰고, overlay에서 지운 파일을 게스트에서 자동 삭제하지는 않습니다.

`make boot`는 이미지를 자동 재생성하거나 모듈을 자동 갱신하지 않습니다.
커널 릴리스가 이미지의 기록과 다르면 `make update-image`를 안내하고 부팅을 멈춥니다.
**릴리스 이름이 같아도 모듈을 다시 빌드했다면 `make update-image`를 실행**합니다.

외부 모듈 실습 예시:

```bash
make lab LAB=my-module     # labs/my-module 빌드 → overlay에 배치
make update-image         # 게스트 종료 상태에서 디스크에 반영
make boot
```

이미 빌드한 파일만 전달할 때는 `make stage LAB=my-module`을 사용합니다.
최초 이미지 생성 전에는 lab/stage 후 `make image`만 실행하면 됩니다.
게스트에서는 `/root/labs/my-module/`에서 파일을 찾습니다.
새 커널 `.c` 파일은 해당 Makefile/Kbuild에도 등록합니다.
이미지 생성·갱신·부팅은 같은 잠금을 사용해 실행 중인 디스크의 중복 사용을 막습니다.

## 6. 패키지와 개인 설정

영구 디스크이므로 게스트 안에서 설치한 패키지도 유지됩니다.

```bash
# 게스트 안에서
apt-get update
apt-get install -y less netcat-openbsd
```

처음부터 포함할 도구나 VM 설정은 Git에서 제외된 `local.mk`에 기록합니다.

```bash
cp local.mk.example local.mk
vim local.mk
```

```makefile
QEMU_MEMORY = 3G
QEMU_CPUS = 2
ROOTFS_SIZE = 4G
EXTRA_PACKAGES = less,netcat-openbsd
# 새 이미지를 만들 때 적용할 root 비밀번호
GUEST_ROOT_PASSWORD = kernel
```

`ROOTFS_SIZE`, `EXTRA_PACKAGES`, 초기 계정 설정은 **새 이미지 생성 시** 적용됩니다.
기존 게스트의 비밀번호는 게스트에서 `passwd`로 바꿉니다.
overlay만 바꿨다면 `make update-image`로 반영합니다.

깨끗한 게스트를 다시 만들려면 QEMU 종료 후 호스트에서:

```bash
make rebuild
# 일회성으로 기본 패키지에 도구를 추가하는 예시
# make rebuild EXTRA_PACKAGES=less,netcat-openbsd
```

새 이미지가 완성되면 기존 디스크를 `disks/rootfs.img.bak.날짜-시간.PID`로 백업하고 교체합니다.
백업에는 대응하는 `.kernel-release` 기록도 함께 남깁니다.
새 게스트에는 이전 게스트에서 직접 만든 파일·설정이 들어가지 않으며, 기존 데이터는 백업에 남습니다.
생성 실패 시 기존 루트 디스크를 유지합니다. 백업 디스크는 필요 여부를 확인해 직접 정리합니다.

## 7. GDB 디버깅

터미널 A에서 `make debug`를 실행합니다. 터미널 B도 같은 `kernel-utils/`로
이동한 뒤 `make gdb`를 실행합니다. GDB에서:

```text
(gdb) hbreak start_kernel
(gdb) continue
(gdb) list
(gdb) info registers
```

기본 연결은 `127.0.0.1:1234`이며 CPU를 멈춘 상태로 시작합니다.
다른 포트는 양쪽 명령 모두 `GDB_PORT=1235`로 지정합니다.
기본 디버그 인자에는 `nokaslr`, `panic=-1`, `oops=panic`이 포함됩니다.

## 8. 실습용 디스크 추가

**루트 디스크 `/dev/vda`와 별도로** 포맷·마운트할 raw 디스크를 만듭니다.
아래 생성 명령은 이미지가 없을 때만 실행합니다.

```bash
test -e disks/lab.img || qemu-img create -f raw disks/lab.img 1G
make boot DISK="$PWD/disks/lab.img"
```

게스트의 `lsblk`로 루트 디스크와 추가 디스크를 확인합니다.
기본 루트는 `/dev/vda`, 위 명령의 추가 디스크는 `/dev/vdb`입니다.
일반 ext4 연습용 **새 추가 디스크에 처음 한 번만**:

```bash
mkfs.ext4 /dev/vdb
mkdir -p /mnt/lab
mount /dev/vdb /mnt/lab
```

이후에는 포맷하지 않고 같은 디스크를 연결해 마운트합니다.
UPB minfs는 ext4 대신 실습의 `mkfs.minfs`로 포맷합니다.
영구 이미지는 정리 대상인 `out/` 바깥, `disks/`에 보관합니다.

## 9. 기존 환경에서 전환

initramfs 방식으로 이미 커널을 빌드했다면 소스를 다시 받을 필요는 없습니다.
저장소 업데이트 후 다음을 실행합니다.

```bash
cd kernel-utils
make deps
make kernel-config
cd linux-5.15.2
make -j$(nproc)
cd ..
make image
make boot
```

예전 `out/amd64/initramfs.cpio`는 새 부팅에 사용하지 않습니다.
새 디스크의 최초 로그인은 `root` / `kernel`입니다.

더 오래된 셸 스크립트 환경의 자료가 남아 있다면 다음과 같이 재사용할 수 있습니다.
기존의 무시된 데이터는 Git 업데이트로 자동 이동하지 않습니다. 대상 경로가 비었는지 먼저 확인합니다.

| 기존 위치 | 새 위치·사용법 |
|---|---|
| `labs/src/linux-5.15.2/` | `kernel-utils/linux-5.15.2/`로 옮긴 뒤 설정 적용·재빌드 |
| `labs/images/rootfs.img` | `kernel-utils/disks/legacy-rootfs.img`로 복사해 보존 |

이전 systemd/ext4 이미지를 루트 디스크로 계속 쓰려면 `local.mk`에
`ROOTFS_IMAGE = $(CURDIR)/disks/legacy-rootfs.img`를 지정하고,
게스트 종료 상태에서 `make update-image`로 현재 커널 모듈과 릴리스 기록을 반영한 뒤 부팅합니다.
기존 계정·비밀번호·패키지 설정은 유지됩니다.

## 10. 정리와 테스트

```bash
make clean          # 현재 아키텍처의 out 하위 임시 생성물 삭제
make distclean      # out 전체 임시 생성물 삭제
make update-image   # 모듈·overlay 갱신, 게스트 데이터 유지
make rebuild        # 기존 루트 디스크 백업 후 새 게스트 생성
make test           # 다운로드·설치·실제 마운트·QEMU 없이 회귀 테스트
```

정리는 `out/` 내부로 제한합니다. **루트 디스크와 백업을 포함한 `disks/`는 유지**합니다.
커널 소스·labs·overlay·캐시도 유지하며 `clean` 후 부팅해도 기존 루트 디스크를 재사용합니다.
원본에서 지원하는 다른 OUTPUT_ROOT로의 정리는 이 프로젝트에서 허용하지 않습니다.
회귀 테스트는 명령 구성·갱신·백업·경로 보호·잠금을 확인하며 실제 커널 빌드와 부팅,
UPB 전체 실습 완료 검증을 대신하지는 않습니다.

## 참고

- [원본 kernel-utils](https://github.com/aweeraman/kernel-utils)
- [Linux 5.15 빌드 요구 사항](https://docs.kernel.org/5.15/process/changes.html)
- [Ubuntu 22.04 mmdebstrap 매뉴얼](https://manpages.ubuntu.com/manpages/jammy/man1/mmdebstrap.1.html)
- [Debian 공식 서명 키](https://ftp-master.debian.org/keys.html)
