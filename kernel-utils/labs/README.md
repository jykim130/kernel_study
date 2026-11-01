# UPB 실습 코드

UPB에서 받은 실습 스켈레톤을 이 디렉토리 아래에 둡니다.
예를 들어 `labs/my-module/Makefile`과 `labs/my-module/my-module.c`를 둔 뒤:

```bash
make lab LAB=my-module
make boot
```

`lab`은 선택한 디렉토리를 외부 커널 모듈로 빌드한 뒤 게스트에 전달합니다.
커널 외부 모듈용 Makefile/Kbuild가 있어야 하며, UPB의 VM 실행용 Makefile을
대신 실행하는 명령은 아닙니다. 사용자 프로그램과 테스트 도구는 호스트에서
별도로 빌드한 뒤 `make stage LAB=my-module`로 함께 전달할 수 있습니다.

게스트에서는 `/root/labs/my-module/`에서 파일을 찾습니다.
공식 과제의 TODO와 테스트 순서는 그대로 따르되 커널 버전별 API 차이를 확인합니다.

실제 UPB 스켈레톤이나 완성 답안은 이 초기에 포함하지 않았습니다.
