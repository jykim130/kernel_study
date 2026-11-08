# UPB 실습 코드

UPB에서 받은 실습 스켈레톤을 이 디렉토리 아래에 둡니다.
예를 들어 `labs/my-module/Makefile`과 `labs/my-module/my-module.c`를 둔 뒤:

```bash
make lab LAB=my-module
make update-image   # 첫 이미지가 없으면 make image
make boot
```

`lab`은 선택한 디렉토리를 외부 커널 모듈로 빌드한 뒤 게스트에 전달합니다.
커널 외부 모듈용 Makefile/Kbuild가 있어야 하며, UPB의 VM 실행용 Makefile을
대신 실행하는 명령은 아닙니다. 사용자 프로그램과 테스트 도구는 호스트에서
별도로 빌드한 뒤 `make stage LAB=my-module`, `make update-image`로 함께 전달할 수 있습니다.
이미지 갱신 전에는 게스트에서 `poweroff`로 QEMU를 종료합니다.

게스트에서는 `/root/labs/my-module/`에서 파일을 찾습니다.
공식 과제의 TODO와 테스트 순서는 그대로 따르되 커널 버전별 API 차이를 확인합니다.

## 실습 받기와 풀이

이 저장소에는 UPB 스켈레톤만 올리며 완성 답안은 포함하지 않습니다.
`git pull origin main`으로 실습을 받고, 받은 파일을 그대로 수정해 풉니다.
풀이는 커밋하지 않고 각자의 로컬에만 둡니다.

수정한 파일에 업데이트가 있어 pull이 거부되면 아래처럼 받습니다.

```bash
git stash
git pull origin main
git stash pop
```

`git checkout .`이나 `git reset --hard`를 실행하면 커밋하지 않은 풀이는 복구할 수 없습니다.

## 실습 목록

- [Lab 01. 커널 모듈 입문](lab01-kernel-modules/README.md)
