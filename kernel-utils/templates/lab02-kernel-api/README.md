# Lab 02. Kernel API

커널 안에서 쓰는 기본 API를 익힙니다. 메모리 할당(`kmalloc`/`kfree`), 커널 연결 리스트(`struct list_head`),
실행 컨텍스트와 락(spinlock·rwlock·`atomic_t`), 모듈 간 심볼 공개(`EXPORT_SYMBOL`)를 다룹니다.

- 원문: [UPB SO2 Lab 02 - Kernel API](https://linux-kernel-labs.github.io/refs/heads/master/so2/lab2-kernel-api.html)
- 원본 출처: [linux-kernel-labs/linux](https://github.com/linux-kernel-labs/linux) `a251a60`의 `tools/labs/templates/kernel_api` (GPL-2.0)
- 원본은 Linux 5.10.14 기준이고, 이 실습 환경은 Linux 5.15.2입니다.
- 이 디렉토리(`templates/lab02-kernel-api/`)의 소스에는 **정답이 들어 있습니다.** 풀이는 `make skels`로 만든 `labs/lab02-kernel-api/`에서 합니다.

## 준비

**커널 설정:** 2번 문제를 관찰하려면 커널에 `CONFIG_DEBUG_ATOMIC_SLEEP`이 켜져 있어야 합니다.
5.15의 `x86_64_defconfig`는 `PREEMPT_VOLUNTARY`라서, 이 옵션이 없으면 스핀락을 잡아도 선점 카운트가 오르지 않아 원자 컨텍스트에서 잠들어도 오류가 나오지 않습니다.
`make kernel-config`가 이 옵션을 적용하며, 이 변경 전에 커널을 빌드했다면 아래처럼 다시 빌드합니다.

```bash
grep -E 'CONFIG_DEBUG_ATOMIC_SLEEP|CONFIG_PREEMPT_COUNT' linux-5.15.2/.config   # 둘 다 =y인지 확인
make kernel          # 설정 적용 후 커널 다시 빌드
make update-image    # 새 커널에 맞는 모듈 반영
```

**스켈레톤 생성:** 처음 한 번 실행합니다. 이미 있는 파일은 덮어쓰지 않습니다.

```bash
make skels LAB=lab02-kernel-api
```

## 공통 절차

모든 명령은 Ubuntu VM의 `kernel-utils/`에서 실행합니다.
UPB와 같이 **모든 문제를 한 번에 빌드**합니다. `make skels`가 만든 `labs/lab02-kernel-api/Kbuild`가 문제 디렉토리를 모두 나열합니다.

```bash
make lab LAB=lab02-kernel-api   # 전체 문제 빌드 후 게스트로 전달할 파일 준비
make update-image               # 첫 부팅이면 make image
make boot
```

아직 풀지 않은 문제도 스켈레톤 그대로 빌드됩니다.
대신 한 문제라도 컴파일 오류가 있으면 전체 빌드가 실패하므로, 오류 메시지의 파일 경로로 어느 문제인지 확인해 고칩니다.

빌드만 확인하려면 `labs/lab02-kernel-api/`에서 `make`를 실행합니다. 같은 디렉토리의 `Makefile`이 커널 빌드 시스템을 호출해 모든 문제를 빌드하며, `make clean`은 빌드 결과를 지웁니다.
이 `make`는 게스트로 파일을 전달하지 않으므로, 게스트에서 테스트할 때는 `kernel-utils/`에서 `make lab`을 사용합니다.

게스트에 `root` / `kernel`로 로그인한 뒤 문제 디렉토리로 이동합니다. `<문제>` 자리에 `1-mem`처럼 문제 디렉토리 이름을 넣습니다.

```bash
cd /root/labs/lab02-kernel-api/<문제>
```

코드를 고쳐 다시 빌드할 때는 게스트에서 `poweroff`로 QEMU를 종료한 뒤 위 절차를 반복합니다.

## 0. 코드 탐색 (코드 작성 없음)

**목표:** `linux-5.15.2/` 소스에서 아래 심볼의 정의를 찾습니다.

- `struct list_head`, `INIT_LIST_HEAD()`, `list_add()`, `list_for_each`, `list_entry`, `container_of`, `offsetof`

**확인할 것**
- `list_head`는 데이터를 가리키지 않는데, `list_entry`는 어떻게 바깥 구조체를 찾아내는가?
- `container_of`와 `offsetof`는 각각 무엇을 계산하는가?

## 1. 메모리 할당 (`1-mem`, 실행·관찰)

**목표:** `mem.c`에서 `kmalloc()`을 어떻게 쓰는지 읽고, 적재·제거하며 메시지를 확인합니다.

**할 일**
1. `mem.c`를 읽고 할당 크기, GFP 플래그, 해제 위치를 확인합니다.
2. `insmod`로 적재하고 `dmesg`로 메시지를 확인합니다.
3. `rmmod`로 제거합니다.

**확인할 것**
- 출력되는 문자는 어디서 온 값인가? `kmalloc`은 할당한 메모리를 초기화하는가?
- `GFP_KERNEL` 대신 `GFP_ATOMIC`을 써야 하는 경우는 언제인가?
- 글자가 한 줄로 이어지지 않는다면 이유는 무엇인가? (`KERN_CONT`, `pr_cont`를 찾아보세요.)

## 2. 원자 컨텍스트에서 잠들기 (`2-sched-spin`, 코드 수정·분석)

**목표:** 스핀락을 잡은 채 잠들면 어떤 일이 생기는지 관찰합니다.

**할 일**
1. `sched-spin.c`를 읽습니다. `set_current_state()`와 `schedule_timeout()`으로 약 5초 동안 잠듭니다.
2. 그대로 적재·제거해 정상 동작을 확인합니다. 적재에 5초 정도 걸립니다.
3. `TODO 0`에 맞춰 대기 구간을 스핀락으로 감쌉니다.
4. 다시 빌드해 적재하고 `dmesg`의 커널 오류를 확인합니다.

**확인할 것**
- 어떤 메시지가 나오는가? 콜 스택에서 `BUG` 줄과 그 원인이 된 호출을 찾습니다.
- 왜 스핀락을 잡은 채 잠들면 안 되는가? 이 경우 스핀락 대신 무엇을 써야 하는가?

오류가 나오지 않으면 [준비](#준비)의 커널 설정을 확인합니다.

## 3. 커널 메모리 다루기 (`3-memory`, 코드 작성)

**목표:** `struct task_info` 4개를 할당해 프로세스 정보를 담고, 출력한 뒤 해제합니다.

**할 일**
1. **TODO 1:** `task_info_alloc()`에서 구조체를 할당하고, `pid`와 `timestamp`(`jiffies`)를 채웁니다.
2. **TODO 2:** 아래 4개 프로세스에 대해 `task_info_alloc()`을 호출합니다.
   - 현재 프로세스(`current`)
   - 부모 프로세스(`parent` 필드)
   - 다음 프로세스(`next_task()`를 한 번)
   - 다음 프로세스의 다음 프로세스(`next_task()`를 두 번)
3. **TODO 3:** 4개 구조체의 `pid`와 `timestamp`를 출력합니다.
4. **TODO 4:** 4개 구조체를 해제합니다.

**확인할 것**
- 각 PID는 어떤 프로세스인가? 적재할 때마다 무엇이 바뀌는가?
- `struct task_struct`에서 `parent`와 `real_parent`는 어떻게 다른가? 언제 두 값이 달라지는가? (`ptrace`를 찾아보세요.)

## 4. 커널 리스트 (`4-list`, 코드 작성)

**목표:** 3번의 `task_info`를 연결 리스트로 관리합니다.

`task_info_add_for_current()`가 적재 시 리스트를 만들고, `list_exit()`가 제거 시
리스트를 출력한 뒤 `task_info_purge_list()`로 비웁니다.

**할 일**
1. **TODO 1:** `task_info_add_to_list()`에서 `task_info`를 할당해 리스트에 추가합니다.
2. **TODO 2:** `task_info_purge_list()`에서 모든 원소를 삭제하고 해제합니다.
3. 적재·제거하며 메시지를 확인합니다.

**확인할 것**
- 순회하며 삭제할 때 왜 `list_for_each` 대신 `list_for_each_safe`를 쓰는가?
- `list_add()`로 넣은 순서와 출력 순서는 어떻게 다른가?

## 5. 프로세스 정보 리스트 (`5-list-full`, 코드 작성)

**목표:** 4번 리스트에 중복 처리와 만료를 더합니다.

- 각 원소에 `atomic_t count`가 있습니다. 이미 있는 PID를 다시 추가하면 새 원소를 만들지 않고 `timestamp`를 갱신하고 `count`를 올립니다.
- 3초보다 오래되었고 `count`가 5 미만인 원소는 만료로 삭제합니다. 이 동작은 `task_info_remove_expired()`에 구현되어 있습니다.

**할 일**
1. **TODO 1:** `task_info_find_pid()`를 구현합니다. PID가 있으면 해당 `task_info`, 없으면 `NULL`을 반환합니다.
2. **TODO 2:** 제거 시 원소 하나는 만료되지 않도록 `atomic_set()`으로 `count`를 충분히 큰 값으로 바꿉니다.
3. 적재·제거하며 메시지를 확인합니다. 적재 시 5초 동안 잠들기 때문에 시간이 걸립니다.

**확인할 것**
- `after first add`와 `after removing expired`의 리스트는 어떻게 다른가?
- 같은 PID가 두 번 추가되면 리스트는 어떻게 바뀌는가?

## 6. 리스트 동기화 (`6-list-sync`, 코드 작성)

**목표:** 5번 리스트를 spinlock이나 rwlock으로 보호합니다.

**할 일**
1. **TODO 1:** 사용할 락을 정의하고, 리스트에 접근하는 구간마다 락을 잡고 풉니다.
   각 구간이 읽기 접근인지 쓰기 접근인지 판단합니다.
2. 적재·제거하며 동작이 5번과 같은지 확인합니다.

**확인할 것**
- 각 구간을 읽기와 쓰기 중 무엇으로 판단했고, 그 이유는 무엇인가?
- `/* TODO: Guess why this comment was added here */` 자리에는 왜 코드가 필요한가?
- `task_info_alloc()`이 락 밖에서 호출되는 이유는 무엇인가? (`GFP_KERNEL`과 2번 문제를 떠올려 보세요.)
- 원문은 "코드가 아니라 데이터를 잠그라"고 합니다. 이 문제에서 이 말은 무슨 뜻인가?

## 7. 다른 모듈에서 리스트 사용 (`7-list-test`, 코드 수정)

**목표:** `6-list-sync`의 함수를 공개하고, 테스트 모듈 `7-list-test`에서 호출합니다.

**할 일**
1. `6-list-sync`에서 **TODO 2**에 맞춰 함수마다 `EXPORT_SYMBOL()`을 추가합니다. 테스트 모듈이 호출하는 세 함수가 `static`이 아닌지도 확인합니다.
2. `6-list-sync`의 `list_sync_exit()`에서 원소의 만료를 막는 코드를 지웁니다. 이 문제와 충돌하기 때문입니다.
3. `7-list-test/list-test.c`의 **TODO 1**에 맞춰 주석 처리된 호출을 풉니다.
4. 공통 절차대로 전체를 빌드해 게스트로 전달합니다. 같은 빌드 안에서 `7-list-test`가 `6-list-sync`의 공개 심볼을 찾습니다.
5. 게스트에서 `6-list-sync`를 적재하기 전과 후에 `/proc/kallsyms`에서 공개한 심볼을 찾습니다.
6. `6-list-sync`, `7-list-test` 순서로 적재하고 `lsmod`로 두 모듈을 확인합니다.
7. 테스트 모듈을 제거합니다.

**확인할 것**
- `EXPORT_SYMBOL()` 없이 주석만 풀고 빌드하면 어떤 메시지가 나오는가? 이때는 전체 빌드가 실패하므로 메시지를 확인한 뒤 바로 1번을 마칩니다.
- `lsmod`의 `Used by` 열에는 무엇이 나오는가?
- 두 모듈은 어떤 순서로 제거해야 하는가? 반대 순서로 제거하면 어떻게 되는가?

## 스터디에서 확인할 것

- 프로세스 컨텍스트와 원자 컨텍스트를 구분하고, 각각에서 쓸 수 있는 할당·락 API를 설명할 수 있습니다.
- `list_head` 기반 리스트를 만들고, 순회하고, 안전하게 삭제할 수 있습니다.
- 공유 데이터를 보호하는 락을 고른 근거와, 모듈 간 심볼 의존성을 기록합니다.
