# Linux 커널 스터디 실습 환경

**Ubuntu 22.04 LTS x86-64 VM**에서 **Linux 5.15.2**를 직접 빌드하고,
[aweeraman/kernel-utils](https://github.com/aweeraman/kernel-utils)의 Makefile로
Debian Bookworm **initramfs**를 만들어 QEMU에서 실행합니다.

```text
실제 PC → VMware 또는 VirtualBox → Ubuntu 개발 VM
                                      └─ QEMU: Linux 5.15.2 + Debian initramfs
```

커널 소스 수정·빌드는 Ubuntu에서 하고 QEMU 게스트에서 모듈 적재와 테스트를 합니다.
아래 명령은 모두 **Windows가 아닌 Ubuntu VM의 터미널**에서 실행합니다.
VM 시작 사양은 CPU 4개, RAM 8GB, 디스크 60GB를 권장합니다.
QEMU 기본값은 TCG, CPU 2개, RAM 2GB입니다. 프로젝트 경로에는 공백·쉼표를 사용하지 않습니다.

## 디렉토리 구조

환경 준비 후의 로컬 구조입니다. 커널 소스와 생성물은 Git에 포함하지 않습니다.

```text
kernel_study/
├─ README.md
└─ kernel-utils/
   ├─ Makefile              # 프로젝트 기본값
   ├─ upstream.mk           # 고정한 원본 Makefile + 실습확장
   ├─ study.mk              # 커널 준비·실습 전달·환경 확인
   ├─ COPYING, UPSTREAM.md  # 원본 라이선스와 버전·변경점
   ├─ local.mk.example      # 개인 설정 예시
   ├─ scripts/, tests/      # 준비 도구와 모의 실행 테스트
   ├─ linux-5.15.2/         # 생성: 소스·.config·빌드 결과
   ├─ labs/                 # 호스트에서 관리할 실습 코드
   ├─ overlay/              # 게스트에 포함할 파일
   ├─ .cache/               # 생성: 다운로드·검증한 서명 키
   ├─ out/amd64/            # 생성: initramfs.cpio·콘솔 로그
   └─ disks/                # 추후 생성: 영구 디스크 이미지
```

원본은 파일로 포함했으며 중첩 Git 저장소나 서브모듈은 사용하지 않습니다.
고정한 커밋과 수정점은 [UPSTREAM.md](kernel-utils/UPSTREAM.md)에 기록합니다.

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

GCC 11, 커널 빌드 도구, QEMU, GDB, mmdebstrap, bsdtar, uidmap 등을 설치합니다.
이후 기본 작업 위치는 **`kernel-utils/`**입니다. 명령 전체에 `sudo`를 붙이지 않습니다.
initramfs 생성은 `mmdebstrap --mode=unshare`를 사용하므로 일반 사용자의
user namespace와 `/etc/subuid`, `/etc/subgid` 범위가 필요합니다.

## 2. 커널 소스와 설정

```bash
make source
make kernel-config
```

`make source`는 kernel.org의 tar.xz를 받아 고정된 SHA-256을 확인하고
`linux-5.15.2/`에 풉니다. 기존 소스를 덮어쓰지 않습니다.
`make kernel-config`는 `.config`가 없을 때 `x86_64_defconfig`를 생성하고,
initramfs·모듈·시리얼 콘솔·procfs·sysfs·debugfs·virtio·ext4·GDB 옵션을 적용합니다.
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
커널 빌드는 이 프로젝트의 준비 도구이며 원본 kernel-utils의 기능은 아닙니다.

## 4. initramfs 생성과 부팅

```bash
make print-config
make image
make boot
```

Debian Bookworm 사용자 공간, 빌드한 커널 모듈, `overlay/`의 파일을
`out/amd64/initramfs.cpio`에 묶습니다. Ubuntu의 오래된 Debian 키링 문제를 피하기 위해
공식 Bookworm 키의 fingerprint를 검증해 사용합니다.
모듈은 이미지에 설치할 때 strip하고 호스트의 원본 `.ko`는 보존합니다.

`make boot`는 `bzImage`와 initramfs로 QEMU를 부팅합니다. 이미지가 없거나
커널 결과·설정·overlay가 바뀌면 다시 패키징합니다. root로 자동 로그인합니다.
virtio NIC와 QEMU user networking을 사용하고 게스트의 `/init`에서 DHCP를 시도합니다.

게스트에서 확인합니다.

```bash
uname -r
cat /etc/os-release
cat /proc/mounts
ip -br address
```

루트 `/`는 RAM에 풀린 initramfs입니다. 게스트에서 만든 파일·설정은 다음 부팅에
유지되지 않으므로 소스와 결과는 호스트에서 관리합니다.
종료 단축키는 **Ctrl+A를 누른 뒤 X**입니다. 영구 디스크를 연결했다면 먼저
파일 작업을 끝내고 `sync`·`umount`로 정리합니다.

`make boot-log`는 콘솔을 `out/amd64/console.log` 파일로 보냅니다.
이 모드에서는 터미널의 대화형 로그인 대신 로그 파일을 확인합니다.

## 5. 커널 수정 후 다시 실행

QEMU를 종료한 뒤 호스트에서 실행합니다.

```bash
cd linux-5.15.2
make -j$(nproc) // 커널 내부 수정이나 내용 추가 시 진행
cd ..
make boot
```

새 `.c` 파일을 추가하면 해당 Makefile/Kbuild에도 등록합니다.
빌드 결과가 갱신되면 initramfs의 커널 모듈도 다시 패키징됩니다.

## 6. 패키지와 개인 설정

```bash
make rebuild EXTRA_PACKAGES=less,netcat-openbsd
```

기본 패키지에 추가해 이미지를 다시 만듭니다. 일회성 변수는 다음 명령에 유지되지
않으므로 계속 쓸 설정은 Git에서 제외된 `local.mk`에 기록합니다.

```bash
cp local.mk.example local.mk
vim local.mk
```

```makefile
QEMU_MEMORY = 3G
QEMU_CPUS = 2
EXTRA_PACKAGES = less,netcat-openbsd
```

설정 변경 후 `make rebuild`를 실행합니다. 파일은 게스트와 같은 경로로
overlay에 둡니다. 예를 들어 `overlay/root/test.txt`는 `/root/test.txt`가 됩니다.

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

## 8. 가상 디스크 추가

파일시스템 실습이나 영구 저장이 필요할 때 새 raw 디스크를 만듭니다.
아래 생성 명령은 이미지가 없을 때만 실행합니다.

```bash
test -e disks/lab.img || qemu-img create -f raw disks/lab.img 1G
make boot DISK="$PWD/disks/lab.img"
```

게스트의 `lsblk`로 새 실습 디스크가 맞는지 확인합니다. 다른 디스크가 없으면
보통 `/dev/vda`입니다. 일반 ext4 연습용 새 디스크에 **처음 한 번만**:

```bash
mkfs.ext4 /dev/vda
mkdir -p /mnt/lab
mount /dev/vda /mnt/lab
```

이후에는 포맷하지 않고 같은 디스크를 연결해 마운트합니다.
UPB minfs는 ext4 대신 실습의 `mkfs.minfs`로 포맷합니다.
루트는 initramfs로 유지하고 추가 디스크만 마운트합니다.
영구 이미지는 정리 대상인 `out/` 바깥, `disks/`에 보관합니다.

## 9. 기존 환경 자료 재사용

기존 Ubuntu 체크아웃에 수정한 커널·디스크가 있다면 새 위치가 비었는지 확인하고
아래 대상으로 이동합니다. 기존의 무시된 데이터는 Git 업데이트로 자동 이동하지 않습니다.

| 기존 위치 | 새 위치 |
|---|---|
| `labs/src/linux-5.15.2/` | `kernel-utils/linux-5.15.2/` |
| `labs/images/rootfs.img` | `kernel-utils/disks/legacy-rootfs.img` — 데이터 보존용 |

기존 커널은 `make kernel-config` 후 다시 빌드합니다. 기존 rootfs 이미지는
initramfs에 넣지 않고, 나중에 데이터 디스크로 연결해 파일을 꺼낼 수 있습니다.
이전 로그·별도 빌드 자료는 보존 여부를 확인한 뒤 사용자가 정리합니다.

## 10. 정리와 테스트

```bash
make clean       # 현재 아키텍처의 out 하위 생성물 삭제
make distclean   # out 전체 생성물 삭제
make rebuild     # initramfs 다시 생성
make test        # 실제 다운로드·설치·QEMU 없이 모의 실행 테스트
```

정리는 `out/` 내부로 제한합니다. 커널 소스·labs·overlay·disks·캐시는 유지합니다.
원본에서 지원하는 다른 OUTPUT_ROOT로의 정리는 이 프로젝트에서 허용하지 않습니다.
테스트는 명령 구성·패키징·파일 전달·경로 보호를 확인하며 실제 커널 빌드와 부팅,
UPB 전체 실습 완료 검증을 대신하지는 않습니다.

## 참고

- [원본 kernel-utils](https://github.com/aweeraman/kernel-utils)
- [Linux 5.15 빌드 요구 사항](https://docs.kernel.org/5.15/process/changes.html)
- [initramfs 설명](https://docs.kernel.org/5.15/filesystems/ramfs-rootfs-initramfs.html)
- [Debian 공식 서명 키](https://ftp-master.debian.org/keys.html)
