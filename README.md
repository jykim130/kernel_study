# 커널 스터디: Linux 빌드와 QEMU 실습

VMware에 설치한 **Ubuntu 22.04 LTS amd64**에서 Linux **5.15.2**를 빌드하고,
QEMU 안에서 부팅하는 실습 환경입니다.

```text
실제 컴퓨터
└─ VMware(Oracle VirtualBox로 진행해도 무방합니다.)
   └─ Ubuntu 22.04 — 아래 명령을 실행하는 개발 환경
      └─ QEMU
         └─ 직접 빌드한 Linux 5.15.2 + Debian Bookworm 사용자 공간
```

아래 명령은 모두 **VMware 우분투의 터미널**에서 실행합니다.
프로젝트를 받은 뒤에는 **kernel_study 루트 디렉터리**를 기준으로 명령을 실행합니다.
실습 설정·스크립트·소스·빌드 결과는 모두 labs 아래에 저장합니다.
스크립트는 필요한 작업에서만 `sudo`를 사용하므로 명령 전체에 `sudo`를 붙이지 않습니다.

## 1. VMware에 우분투 준비

1. [Ubuntu 22.04 LTS amd64 설치 이미지](https://releases.ubuntu.com/22.04/)로 VM을 만듭니다.
2. 실습 시작용 자원으로 CPU 4개, RAM 8GB, 디스크 60GB를 권장합니다.
   커널 소스·디버그 정보·빌드 결과가 공간을 사용하므로 여유 공간을 확보합니다.
3. VMware 네트워크는 NAT로 설정하고 우분투 설치와 인터넷 연결을 완료합니다.
4. 우분투 사용자에게 `sudo` 권한이 있는지 확인합니다.

기본 실행은 QEMU의 **TCG 소프트웨어 에뮬레이션**입니다. VMware에서 중첩 가상화를
활성화하지 않아도 사용할 수 있습니다. KVM은 `/dev/kvm`이 실제로 제공되는 환경에서만
선택적으로 사용합니다.

현재 스크립트의 대상은 Ubuntu 22.04와 GCC 11입니다. 다른 우분투 버전의 호환성은 별도 검증이 필요합니다.

## 2. 프로젝트 받기

```bash
sudo apt-get update
sudo apt-get install -y git

mkdir -p ~/work
cd ~/work
git clone https://github.com/jykim130/kernel_study.git
cd kernel_study
```

아직 변경 사항을 GitHub에 올리지 않았다면 이 프로젝트 폴더를 우분투의
`~/work/kernel_study`로 복사한 뒤 그 안에서 진행합니다.
VMware 공유 폴더 대신 **우분투 홈 디렉터리 안**에 소스와 빌드 결과를 둡니다.

## 3. 빌드·실행 도구 설치

```bash
bash labs/scripts/install-deps.sh
```

GCC 11, make, bison, flex, ncurses·OpenSSL·ELF 개발 라이브러리,
debootstrap, Debian 아카이브 키, GnuPG, QEMU, GDB 등을 설치합니다.
커널 빌드는 일반 사용자로 진행하고 디스크 이미지 마운트와 사용자 공간 구성에 관리자 권한을 사용합니다.

## 4. 커널 다운로드와 빌드

```bash
bash labs/scripts/build-kernel.sh
```

스크립트가 다음 작업을 수행합니다.

1. kernel.org에서 `linux-5.15.2.tar.xz`를 다운로드합니다.
2. 공식 체크섬과 일치하는 SHA-256인지 확인합니다.
3. `labs/src/linux-5.15.2`에 소스를 풀고 `labs/build/linux-5.15.2`에 빌드합니다.
4. 최초 실행에서는 `x86_64_defconfig`를 만들고 실습용 설정을 적용합니다.
5. 부팅용 `bzImage`, GDB용 `vmlinux`, 커널 모듈을 빌드합니다.

설정에는 ext4, virtio 디스크·네트워크, 시리얼 콘솔을 커널에 내장하는 옵션과
DWARF 4 디버그 정보가 포함됩니다. 따라서 별도의 initramfs 없이 `/dev/vda`에서 부팅합니다.
재실행하면 기존 소스와 `.config`를 유지한 채 필요한 부분을 다시 빌드합니다.

메모리가 부족하거나 우분투가 느려지면 병렬 빌드 수를 줄입니다.

```bash
BUILD_JOBS=2 bash labs/scripts/build-kernel.sh
```

완료 후 결과물을 확인합니다.

```bash
ls -lh labs/build/linux-5.15.2/arch/x86/boot/bzImage
ls -lh labs/build/linux-5.15.2/vmlinux
cat labs/build/linux-5.15.2/include/config/kernel.release
```

기본 커널 릴리스 이름은 `5.15.2-kernel-study`입니다.

## 5. QEMU용 루트 파일시스템 생성

```bash
bash labs/scripts/make-rootfs.sh
```

이미지를 만들기 전에 Debian 공식 사이트에서 Bookworm 서명 키를 받아,
스크립트에 고정한 공개키 지문과 일치하는지 확인합니다.
확인된 키는 `labs/.cache/debian-bookworm.gpg`에 모아 `debootstrap`의 서명 검증에 사용합니다.
Ubuntu 22.04의 오래된 시스템 키 파일에 Bookworm 키가 없는 경우도 이 과정에서 처리합니다.

`debootstrap`으로 **Debian Bookworm amd64** 사용자 공간을 구성하고,
4GB의 sparse raw ext4 디스크 이미지인 `labs/images/rootfs.img`를 만듭니다.
systemd, 시리얼 로그인, 네트워크와 기본 실습 명령을 설정한 뒤 방금 빌드한 커널 모듈을 설치합니다.
4GB는 가상 디스크의 최대 크기이며 파일은 데이터가 쓰이는 만큼 호스트 공간을 사용합니다.

- 게스트 로그인: `root`
- 초기 비밀번호: `kernel`
- 호스트 이름: `kernel-study`
- 네트워크: QEMU user networking, DHCP

이 계정은 로컬 실습용입니다. SSH 서버와 외부에서 들어오는 포트 포워딩은 구성하지 않습니다.
로그인 후 비밀번호는 `passwd`로 바꿀 수 있습니다.
초기 이미지 생성 시 다른 비밀번호를 사용하려면 다음과 같이 입력합니다.

```bash
read -rsp '게스트 root 비밀번호: ' GUEST_ROOT_PASSWORD; echo
export GUEST_ROOT_PASSWORD
bash labs/scripts/make-rootfs.sh
unset GUEST_ROOT_PASSWORD
```

이미지가 이미 있으면 스크립트는 덮어쓰지 않고 종료합니다.
중간에 실패하면 최종 `rootfs.img` 대신 임시 이미지 경로를 출력합니다.
오류를 해결하고 다시 실행하면 새 임시 이미지로 재시도합니다.
Bookworm이라는 배포판 이름은 고정하지만 설치 패키지는 해당 저장소의 업데이트를 받습니다.

## 6. QEMU에서 부팅

```bash
bash labs/scripts/run-qemu.sh
```

별도 GUI 창 대신 현재 터미널에 부팅 로그와 로그인 프롬프트가 나타납니다.
기본값은 TCG, 가상 CPU 2개, RAM 1024MB입니다.
로그는 `labs/logs/qemu-*.log`에도 저장됩니다.

로그인 후 **QEMU 게스트 안에서** 다음을 확인합니다.

```bash
uname -r
cat /etc/os-release
findmnt /
ip -br address
```

- `uname -r`: `5.15.2-kernel-study`
- 사용자 공간: Debian Bookworm
- 루트 파일시스템: `/dev/vda`, ext4

우분투의 다른 터미널에서 `uname -r`을 실행하면 우분투 자체의 커널 버전이 나옵니다.
게스트와 개발 환경을 구분해서 확인합니다.

게스트를 종료할 때는 게스트 안에서 실행합니다.

```bash
poweroff
```

QEMU 강제 종료 단축키는 **Ctrl+A를 누른 뒤 X**입니다.
디스크 변경을 저장하려면 `poweroff`로 정상 종료합니다.

## 7. 소스 수정 후 다시 실행

QEMU를 종료한 뒤 `labs/src/linux-5.15.2`의 코드를 수정합니다.

```bash
bash labs/scripts/build-kernel.sh
bash labs/scripts/make-rootfs.sh --update-modules
bash labs/scripts/run-qemu.sh
```

`--update-modules`는 기존 이미지의 사용자 파일을 유지하면서 커널 모듈을 갱신합니다.
호스트의 `/lib/modules`에는 설치하지 않습니다.
이미지 생성·모듈 갱신·QEMU 실행은 같은 잠금 파일을 사용하므로 동시에 실행되지 않습니다.

추가 커널 설정은 다음 명령으로 편집합니다.

```bash
make -C labs/src/linux-5.15.2 O="$PWD/labs/build/linux-5.15.2" ARCH=x86 CC=gcc-11 HOSTCC=gcc-11 menuconfig
bash labs/scripts/build-kernel.sh
```

루트 디스크·ext4·시리얼 콘솔 관련 내장 옵션을 끄면 initramfs 없이 부팅할 수 없습니다.
원래 실습 설정으로 다시 시작하려면 빌드 스크립트에 `--reset-config`를 지정합니다.
기존 `.config`는 빌드 디렉터리에 자동으로 백업합니다.

## 8. GDB로 커널 진입점 관찰

우분투 터미널 A에서 실행합니다.

```bash
bash labs/scripts/run-qemu.sh --debug
```

게스트 CPU는 시작부터 멈추고 `127.0.0.1:1234`에서 GDB 연결을 기다립니다.
우분투 터미널 B에서 같은 프로젝트로 이동해 실행합니다.

```bash
cd ~/work/kernel_study
gdb labs/build/linux-5.15.2/vmlinux
```

GDB 안에서 실행합니다.

```text
(gdb) target remote 127.0.0.1:1234
(gdb) hbreak start_kernel
(gdb) continue
(gdb) list
(gdb) info registers
```

부팅 인자에 `nokaslr`를 지정해 코드 주소가 무작위로 이동하지 않게 합니다.
`continue`하면 다음 중단점까지 실행합니다. 디버거 연결을 해제할 때는 `detach`를 사용합니다.

## 실행 옵션과 설정

```bash
# QEMU 명령만 출력; 이미지나 커널을 만들기 전에도 사용 가능
bash labs/scripts/run-qemu.sh --dry-run

# 게스트 변경 사항을 이미지에 저장하지 않는 일회용 실행
bash labs/scripts/run-qemu.sh --snapshot

# VMware 우분투에서 /dev/kvm 접근이 가능한 경우에만 선택
bash labs/scripts/run-qemu.sh --accel kvm

# QEMU 자원 조절
QEMU_MEMORY=2048 QEMU_CPUS=2 bash labs/scripts/run-qemu.sh

# 다른 디버깅 포트 사용; GDB에서도 같은 포트로 연결
bash labs/scripts/run-qemu.sh --debug --gdb-port 1235
```

기본 설정은 `labs/config/lab.conf.sh`에 있습니다. 커널 버전과 다운로드 체크섬은 서로 일치해야 합니다.
커널을 다른 버전으로 바꾸면 빌드·설정·사용자 공간 호환성도 다시 확인해야 합니다.

```text
kernel_study/
├─ README.md                  설치·실행 안내
├─ .gitattributes
├─ .gitignore
└─ labs/
   ├─ config/lab.conf.sh       버전·리소스·경로 기본값
   ├─ scripts/
   │  ├─ common.sh            공통 경로·유틸리티
   │  ├─ install-deps.sh      우분투 패키지 설치
   │  ├─ build-kernel.sh      소스 다운로드·설정·빌드
   │  ├─ make-rootfs.sh       Debian 이미지 생성·모듈 갱신
   │  ├─ prepare-debian-keyring.sh  Bookworm 공식 서명 키 준비
   │  └─ run-qemu.sh          일반 실행·GDB 대기·명령 미리 보기
   ├─ tests/test_scripts.py   스크립트 테스트
   ├─ .cache/                 다운로드·임시 파일 (Git 제외)
   ├─ src/                    커널 소스 (Git 제외)
   ├─ build/                  설정·bzImage·vmlinux·모듈 (Git 제외)
   ├─ images/                 게스트 디스크 (Git 제외)
   └─ logs/                   빌드·부팅 로그 (Git 제외)
```

## 문제가 생기면

| 증상 | 확인할 항목 |
| --- | --- |
| `Linux x86_64` 환경이 필요하다는 오류 | Windows PowerShell 대신 VMware 우분투 터미널에서 실행 |
| `gcc-11` 또는 빌드 도구 없음 | 3단계의 의존성 설치 완료 여부 |
| 빌드 중 프로세스가 `Killed`로 종료됨 | VM 메모리와 여유 공간 확인, `BUILD_JOBS=2` 또는 `1` 사용 |
| `VFS: Unable to mount root fs` | virtio·ext4 내장 옵션, `/dev/vda`, 이미지 생성 완료 여부 |
| 로그인 화면 없이 QEMU가 대기함 | `--debug`라면 GDB에서 연결한 뒤 `continue` 실행 |
| `Kernel release mismatch` | 커널 빌드 후 `make-rootfs.sh --update-modules` 실행 |
| 잠금 파일 사용 중 | 다른 QEMU·빌드·이미지 작업이 끝났는지 확인. 파일을 삭제해서 우회하지 않음 |
| 이미지 생성 후 정리 실패 안내 | 안내된 마운트 지점을 `findmnt`로 확인하고 `sudo umount -R <안내된 경로>`로 해제한 뒤 재시도 |
| `--accel kvm` 실행 실패 | 기본 TCG로 실행하거나 VMware의 중첩 가상화와 `/dev/kvm` 접근 권한 확인 |

### Bookworm 서명 키 오류 복구

`Release signed by unknown key (key id F8D2585B8783D481)`은
Bookworm 릴리스 서명을 검증할 키가 현재 키 파일에 없다는 뜻입니다.
키 ID는 Debian 공식 릴리스 키 지문 `4D64 FEC1 19C2 0290 67D6 E791 F8D2 585B 8783 D481`의 끝부분입니다.

수정된 프로젝트 파일을 우분투에 반영한 뒤, 프로젝트 루트에서 실행합니다.

```bash
sudo apt-get update
sudo apt-get install -y gnupg curl ca-certificates
bash labs/scripts/make-rootfs.sh
```

새 스크립트가 공식 키를 준비하고 새 임시 이미지로 다시 생성합니다.
커널을 다시 빌드하거나 실패한 `.rootfs.*.img`를 최종 이미지로 옮길 필요는 없습니다.
최종 `labs/images/rootfs.img`가 이미 존재한다면 덮어쓰지 않고 종료합니다.
`--no-check-gpg`로 서명 검증을 생략하지 않습니다.

정적 검사와 실행 명령·실패 경로 테스트는 다음 명령으로 수행합니다.

```bash
python3 -m unittest discover -s labs/tests -v
```

이 테스트는 실제 커널 컴파일·이미지 생성·부팅을 대체하지 않습니다.
최초 우분투 검증은 위 3~6단계를 실행한 뒤 `uname -r`과 로그인 성공 여부로 확인합니다.

## 참고 자료

- [Linux 5.15 빌드 요구 사항](https://docs.kernel.org/5.15/process/changes.html)
- [kernel.org 공식 SHA-256 목록](https://www.kernel.org/pub/linux/kernel/v5.x/sha256sums.asc)
- [debootstrap 사용법](https://manpages.debian.org/bookworm/debootstrap/debootstrap.8.en.html)
- [Debian 공식 아카이브·릴리스 서명 키](https://ftp-master.debian.org/keys.html)
- [QEMU 실행 옵션](https://www.qemu.org/docs/master/system/invocation.html)
- [QEMU GDB 사용법](https://www.qemu.org/docs/master/system/gdb.html)

