# Lab 03. 문자 장치 드라이버 (Character Device Drivers)

사용자 프로그램이 `/dev/so2_cdev`를 열고·읽고·쓰면 커널 모듈의 함수가 호출되는 문자 장치 드라이버를 만듭니다.
장치 번호(major/minor)와 등록, `struct cdev`·`struct file_operations`, 사용자 메모리 접근(`copy_to_user`/`copy_from_user`),
`ioctl`, 대기 큐(wait queue)를 다룹니다.

- 원문: [UPB SO2 Lab 03 - Character device drivers](https://linux-kernel-labs.github.io/refs/heads/master/so2/lab3-device-drivers.html)
- 원본 출처: [linux-kernel-labs/linux](https://github.com/linux-kernel-labs/linux) `a251a60`의 `tools/labs/templates/device_drivers` (GPL-2.0)
- 원본은 Linux 5.10.14 기준이고, 이 실습 환경은 Linux 5.15.2입니다.
- 이 디렉토리(`templates/lab03-device-drivers/`)의 소스에는 **정답이 들어 있습니다.** 풀이는 `make skels`로 만든 `labs/lab03-device-drivers/`에서 합니다.

## Lab 02와 다른 점

| | Lab 02 | Lab 03 |
| --- | --- | --- |
| 모듈 | 문제마다 디렉토리와 `.ko`가 따로 있음 | **모듈 하나** (`kernel/so2_cdev.c`)에서 TODO 1→6을 차례로 채움 |
| 사용자 프로그램 | 없음 | `user/so2_cdev_test.c` (ioctl 테스트용, 완성본이라 고칠 필요 없음) |
| 공용 헤더 | 없음 | `include/so2_cdev.h` (ioctl 번호, 커널·사용자 코드가 함께 씀) |
| 장치 파일 | 해당 없음 | 게스트에서 `mknod`로 직접 만듦 |

```txt
lab03-device-drivers/
├── Makefile            labs/ 안에서 make로 모듈만 빌드할 때 사용
├── include/so2_cdev.h  ioctl 명령 번호와 BUFFER_SIZE
├── kernel/
│   ├── Kbuild
│   └── so2_cdev.c      풀이할 드라이버 (TODO 1~7)
└── user/
    ├── Makefile
    └── so2_cdev_test.c ioctl 테스트 프로그램
```

## 준비

**스켈레톤 생성:** 처음 한 번 실행합니다. 이미 있는 파일은 덮어쓰지 않습니다.

```bash
make skels LAB=lab03-device-drivers
```

TODO가 한 파일에 누적되므로, 중간 문제부터 시작하려면 `TODO=n`을 씁니다. 예를 들어 `TODO=4`로 만들면 TODO 1~3의 정답이 채워진 상태로 생성됩니다.

```bash
make skels LAB=lab03-device-drivers TODO=4   # 문제 5(read)부터 시작
```

**테스트 프로그램 빌드:** 게스트에는 gcc가 없으므로 Ubuntu VM에서 빌드해 함께 전달합니다.
`make lab`은 커널 모듈만 빌드하므로 이 단계는 직접 실행해야 합니다. 테스트 프로그램은 고칠 일이 없어서 한 번만 하면 됩니다.

```bash
make -C labs/lab03-device-drivers/user     # labs/lab03-device-drivers/user/so2_cdev_test 생성
```

게스트(x86-64)에 맞춰 원본 `user/Makefile`의 `-m32`를 뺐습니다. `-static`으로 빌드하므로 게스트의 라이브러리 버전과 상관없이 실행됩니다.

## 공통 절차

모든 명령은 Ubuntu VM의 `kernel-utils/`에서 실행합니다.

```bash
make lab LAB=lab03-device-drivers   # so2_cdev.ko 빌드 후 user/ 포함 전체를 게스트로 전달할 준비
make update-image                   # 첫 부팅이면 make image
make boot
```

게스트에 `root` / `kernel`로 로그인한 뒤 장치 파일을 만듭니다.
`/dev`는 부팅할 때마다 새로 만들어지므로 **부팅할 때마다 한 번씩** 실행합니다.

```bash
mknod /dev/so2_cdev c 42 0
ls -l /dev/so2_cdev                 # 첫 글자 c(문자 장치), "42, 0" 확인
cd /root/labs/lab03-device-drivers
```

모듈은 `kernel/so2_cdev.ko`, 테스트 프로그램은 `user/so2_cdev_test`에 있습니다.
코드를 고쳐 다시 빌드할 때는 게스트에서 `poweroff`로 QEMU를 종료한 뒤 위 절차를 반복합니다.

**`open`의 10초 대기:** 원본의 `so2_cdev_open()`에는 처음부터 `schedule_timeout(10 * HZ)`가 들어 있어서, 장치를 열 때마다 10초씩 멈춥니다.
문제 4에서 두 프로세스가 동시에 여는 상황을 만들기 위한 코드입니다. `cat`이 바로 끝나지 않는 것은 정상입니다.
문제 4를 확인한 뒤에는 이 두 줄을 지우거나 주석 처리해도 됩니다. 추가 문제에서도 장치를 열 때마다 10초씩 기다리게 됩니다.

**콘솔이 하나뿐일 때:** 원문은 두 번째 콘솔(Alt+F2)이나 SSH를 쓰라고 하지만, 이 게스트는 시리얼 콘솔 하나뿐입니다.
동시에 두 프로세스가 필요하면 셸의 `&`로 하나를 백그라운드에서 실행합니다.

## 0. 코드 탐색 (코드 작성 없음)

**목표:** `linux-5.15.2/` 소스에서 아래 정의를 찾습니다.

- `struct file`, `struct file_operations`, `generic_ro_fops`, `vfs_read()`

**확인할 것**
- `struct file_operations`에는 어떤 함수 포인터들이 있는가? 이번 실습에서 채울 것은 무엇인가?
- `vfs_read()`는 어떤 과정을 거쳐 드라이버의 `.read`를 호출하는가?
- `struct file`의 `f_pos`, `private_data`는 각각 무엇에 쓰이는가?

## 1. 장치 등록·해제 (TODO 1)

**목표:** major `MY_MAJOR`(42), minor `MY_MINOR`(0)인 장치 번호 영역을 `so2_cdev`라는 이름으로 등록합니다.

**할 일**
1. **TODO 1:** `so2_cdev_init()`에서 `register_chrdev_region()`으로 등록하고, `so2_cdev_exit()`에서 `unregister_chrdev_region()`으로 해제합니다.
2. 적재하고 `/proc/devices`에서 등록을 확인한 뒤 제거합니다.

```bash
insmod kernel/so2_cdev.ko
cat /proc/devices | grep so2_cdev
rmmod so2_cdev
```

**확인할 것**
- `/proc/devices`의 `42 so2_cdev`는 무엇을 뜻하는가?
- 모듈을 적재해도 `/dev/so2_cdev`가 생기지 않는 이유는 무엇인가? `mknod`는 무엇을 만드는가?

## 2. 이미 쓰이는 major로 등록하기 (코드 수정·관찰)

**목표:** 이미 다른 드라이버가 쓰는 major로 등록하면 어떻게 되는지 확인합니다.

**할 일**
1. 게스트에서 `cat /proc/devices`로 이미 쓰이는 major 하나를 고릅니다 (예: `4 tty`).
2. `MY_MAJOR`를 그 값으로 바꿔 빌드하고 적재합니다.
3. 오류 메시지와 반환값을 확인한 뒤 `MY_MAJOR`를 **42로 되돌립니다.**

**확인할 것**
- `insmod`가 어떤 오류를 내는가? 반환된 오류 번호는 `include/uapi/asm-generic/errno-base.h`의 무엇인가?
- 고정 major 대신 `alloc_chrdev_region()`을 쓰면 무엇이 달라지는가?

## 3. open과 release (TODO 2)

**목표:** 장치 구조체에 `struct cdev`를 넣고 커널에 등록해, 장치 파일을 열고 닫을 때 드라이버 함수가 불리게 합니다.

**할 일**
1. **TODO 2:** `struct so2_device_data`에 `struct cdev` 멤버를 추가합니다.
2. **TODO 2:** `so2_cdev_open()`, `so2_cdev_release()`에서 메시지를 출력하고, `so2_fops`에 두 함수를 연결합니다.
3. **TODO 2:** `so2_cdev_init()`에서 `cdev_init()`·`cdev_add()`, `so2_cdev_exit()`에서 `cdev_del()`을 호출합니다.
4. 적재하고 장치 파일을 연 뒤 `dmesg`로 메시지를 확인합니다.

```bash
insmod kernel/so2_cdev.ko
cat /dev/so2_cdev       # 아직 read가 없으므로 읽기는 실패하거나 이상하게 동작할 수 있음
dmesg | tail
```

**확인할 것**
- `open called!`과 `close called!`가 나오는가? `cat` 한 번에 각각 몇 번 나오는가?
- `cdev_add()`의 장치 번호와 `mknod`의 번호가 다르면 어떻게 되는가?

## 4. 접근 제한 (TODO 3)

**목표:** 장치를 한 번에 하나의 프로세스만 열 수 있게 합니다.

**할 일**
1. **TODO 3:** `struct so2_device_data`에 `atomic_t access`를 추가하고, `so2_cdev_init()`에서 0으로 초기화합니다.
2. **TODO 3:** `so2_cdev_open()`에서 `inode->i_cdev`와 `container_of()`로 장치 구조체를 구해 `file->private_data`에 저장합니다.
3. **TODO 3:** `so2_cdev_open()`에서 `atomic_cmpxchg()`로 `access`가 0일 때만 1로 바꾸고, 이미 열려 있으면 `-EBUSY`를 반환합니다.
4. **TODO 3:** `so2_cdev_release()`에서 `atomic_set()`으로 `access`를 0으로 되돌립니다.
5. 두 프로세스가 동시에 열도록 해 봅니다. 첫 번째 `open`이 10초 동안 잠들어 있는 사이에 두 번째를 실행합니다.

```bash
cat /dev/so2_cdev &     # 10초 동안 장치를 잡고 있음
cat /dev/so2_cdev       # 바로 실행
```

**확인할 것**
- 두 번째 `cat`은 어떤 메시지를 내는가?
- `container_of(inode->i_cdev, struct so2_device_data, cdev)`는 Lab 02의 `list_entry`와 어떤 점이 같은가?
- `atomic_read()`로 확인한 뒤 `atomic_set()`으로 바꾸면 왜 안 되는가?

## 5. read (TODO 4)

**목표:** 장치 버퍼의 내용을 사용자 공간으로 복사해, `cat /dev/so2_cdev`가 `hello`를 출력하고 끝나게 합니다.

**할 일**
1. **TODO 4:** `struct so2_device_data`에 `BUFSIZ` 크기의 `buffer`를 추가하고, `so2_cdev_init()`에서 `MESSAGE`로 채웁니다.
2. **TODO 4:** `so2_cdev_read()`에서 `copy_to_user()`로 복사합니다. `size`와 `*offset`을 고려해 남은 양만 복사하고, `*offset`을 갱신합니다.
3. **TODO 4:** `so2_fops`에 `.read`를 연결합니다.
4. `cat`이 끝나는지 확인합니다. 끝나지 않으면 `Ctrl+C`로 멈추고 `*offset` 처리를 확인합니다.

```bash
cat /dev/so2_cdev
```

**확인할 것**
- `cat`은 `read`를 몇 번 호출하는가? 마지막 호출에서 `0`을 반환해야 하는 이유는 무엇인가? (`pr_info("Offset: %lld\n", *offset);`로 확인해 보세요.)
- `copy_to_user()` 대신 `memcpy()`로 사용자 버퍼에 바로 쓰면 왜 안 되는가?

## 6. write (TODO 5)

**목표:** 사용자가 쓴 내용으로 장치 버퍼를 바꿉니다.

**할 일**
1. **TODO 5:** `so2_cdev_write()`에서 `copy_from_user()`로 `buffer`에 복사하고 `size`를 갱신합니다. `BUFSIZ`를 넘지 않게 합니다.
2. **TODO 5:** `so2_fops`에 `.write`를 연결합니다.

```bash
echo "arpeggio" > /dev/so2_cdev
cat /dev/so2_cdev
```

**확인할 것**
- `cat`이 `arpeggio`를 출력하는가?
- `write`가 요청보다 적은 바이트 수를 반환하면 `echo`는 어떻게 동작하는가?

## 7. ioctl (TODO 6)

**목표:** `MY_IOCTL_PRINT` 명령을 받으면 `IOCTL_MESSAGE`를 출력합니다.

**할 일**
1. `include/so2_cdev.h`에서 `MY_IOCTL_PRINT`가 `_IOC()`로 어떻게 정의되었는지 읽습니다.
2. **TODO 6:** `so2_cdev_ioctl()`에서 `MY_IOCTL_PRINT`를 처리하고, `so2_fops`에 `.unlocked_ioctl`을 연결합니다.
3. 테스트 프로그램으로 호출합니다.

```bash
user/so2_cdev_test p
dmesg | tail            # Hello ioctl 확인
```

**확인할 것**
- `_IOC(dir, type, nr, size)`의 네 값은 각각 무엇을 뜻하는가? `'k'`는 어디서 정한 값인가?
- 모르는 명령이 들어오면 원본은 `-EINVAL`을 반환합니다. 원문은 `-ENOTTY`를 권합니다. 두 값은 어떻게 다른가?

## 추가 문제 (TODO 7)

추가 문제는 `EXTRA` 매크로를 켜야 동작합니다. `kernel/Kbuild`에 `ccflags-y += -DEXTRA`를 추가하거나 `so2_cdev.c` 맨 위에 `#define EXTRA`를 넣습니다.
`EXTRA`가 켜지면 문제 4의 접근 제한이 빠지고, 장치 버퍼는 빈 상태로 시작합니다.

### 7-1. ioctl로 버퍼 읽고 쓰기

**할 일:** `MY_IOCTL_SET_BUFFER`로 사용자 버퍼를 장치 버퍼에 쓰고, `MY_IOCTL_GET_BUFFER`로 읽어 옵니다. 크기는 `BUFFER_SIZE`로 고정입니다.

```bash
user/so2_cdev_test s "hello ioctl"
user/so2_cdev_test g
```

### 7-2. ioctl과 대기 큐

**할 일:** 장치 구조체에 `wait_queue_head_t`와 `flag`를 추가하고 `init_waitqueue_head()`로 초기화합니다.
`MY_IOCTL_DOWN`은 `flag`가 0이 아닐 때까지 잠들고, `MY_IOCTL_UP`은 `flag`를 1로 바꾸고 깨웁니다.

```bash
user/so2_cdev_test d &   # 잠든 상태로 남음
ps                       # so2_cdev_test가 남아 있는지 확인
user/so2_cdev_test u     # 깨우면 위 프로세스가 끝남
```

### 7-3. O_NONBLOCK 읽기

**할 일:** 버퍼가 비었을 때 `O_NONBLOCK`으로 열렸으면 `-EAGAIN`을 반환하고, 아니면 데이터가 써질 때까지 대기 큐에서 잠듭니다. `write`는 데이터를 쓴 뒤 깨웁니다.

```bash
user/so2_cdev_test n                # 버퍼가 비었으므로 read 실패
cat /dev/so2_cdev &                 # 데이터가 올 때까지 잠듦
echo "data" > /dev/so2_cdev         # 위 cat이 깨어나 출력
user/so2_cdev_test n
```

**확인할 것**
- `cat /dev/so2_cdev`는 어떤 플래그로 장치를 여는가? (`strace -e openat cat /dev/so2_cdev`로 확인해 보세요.)
- `wait_event_interruptible()`이 0이 아닌 값을 반환하는 것은 언제인가?

## 스터디에서 확인할 것

- 사용자 프로그램의 `open`/`read`/`write`/`ioctl`이 `file_operations`의 어느 함수로 연결되는지 설명할 수 있습니다.
- `inode`·`file`·`cdev`와 내 장치 구조체의 관계, `private_data`를 쓰는 이유를 설명할 수 있습니다.
- `read`/`write`의 반환값과 `*offset` 처리 규칙, 사용자 메모리에 직접 접근하면 안 되는 이유를 기록합니다.
