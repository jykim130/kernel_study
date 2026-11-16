# UPB 실습 코드

Lab 02부터는 UPB와 같은 방식으로 실습을 받습니다. `templates/`에 **정답이 포함된 원본**이 있고,
`make skels`가 정답 줄을 지운 스켈레톤을 이 `labs/` 디렉토리에 만듭니다.

```bash
make skels LAB=lab02-kernel-api   # templates/ → labs/ 스켈레톤 생성
make lab LAB=lab02-kernel-api     # 실습의 모든 문제를 빌드하고 게스트로 전달할 파일 준비
make update-image                 # 첫 이미지가 없으면 make image
make boot
```

`lab`은 선택한 디렉토리를 외부 커널 모듈로 빌드한 뒤 게스트에 전달합니다.
Lab 02부터는 UPB와 같이 실습 단위로 모든 문제를 한 번에 빌드하며, Lab 01은 문제 디렉토리 단위로 빌드합니다.
커널 외부 모듈용 Makefile/Kbuild가 있어야 하며, UPB의 VM 실행용 Makefile을
대신 실행하는 명령은 아닙니다. 사용자 프로그램과 테스트 도구는 호스트에서
별도로 빌드한 뒤 `make stage LAB=...`, `make update-image`로 함께 전달할 수 있습니다.
이미지 갱신 전에는 게스트에서 `poweroff`로 QEMU를 종료합니다.

게스트에서는 `/root/labs/<LAB>/`에서 파일을 찾습니다.
공식 과제의 TODO와 테스트 순서는 그대로 따르되 커널 버전별 API 차이를 확인합니다.

## 스켈레톤 생성 (`make skels`)

- `LAB`에는 실습 전체(`lab02-kernel-api`)나 문제 하나(`lab02-kernel-api/4-list`)를 지정합니다.
- 원본의 `/* TODO n/m: ... */` 주석 아래 `m`줄(생략하면 1줄)이 정답이며, 생성 시 지워집니다.
  주석은 `/* TODO n: ... */`로 남아 무엇을 채울지 알려 줍니다.
- **이미 있는 파일은 덮어쓰지 않습니다.** 풀던 파일은 그대로 두고 없는 파일만 새로 만듭니다.
  특정 파일을 처음 상태로 되돌리려면 그 파일을 다른 이름으로 옮긴 뒤 다시 실행합니다.
- `TODO=n`을 주면 번호가 `n`보다 작은 TODO는 정답을 남깁니다. 기본값은 `0`(모두 지움)입니다.
- 실습 최상위의 `Kbuild`(예: `labs/lab02-kernel-api/Kbuild`)는 문제 목록이라 실행할 때마다 새로 만듭니다.

## 실습 받기와 풀이

`git pull origin main`으로 새 실습과 원본 수정을 받은 뒤 `make skels`를 실행합니다.
`make skels`로 만든 `labs/` 아래 디렉토리는 Git에서 제외되므로, 풀이가 pull과 충돌하지 않고 커밋되지도 않습니다.
정답은 `templates/`에 있으니 막혔을 때나 풀이를 마친 뒤 비교해 봅니다.
`git clean -x`는 Git에서 제외된 파일도 지우므로 풀이가 사라집니다.

Lab 01은 이 방식 이전의 실습이라 스켈레톤이 저장소에 직접 들어 있습니다.
Lab 01 파일을 수정한 뒤 pull이 거부되면 아래처럼 받습니다.

```bash
git stash
git pull origin main
git stash pop
```

`git checkout .`이나 `git reset --hard`를 실행하면 커밋하지 않은 Lab 01 풀이는 복구할 수 없습니다.

## 실습 목록

- [Lab 01. 커널 모듈 입문](lab01-kernel-modules/README.md)
- [Lab 02. Kernel API](../templates/lab02-kernel-api/README.md)
