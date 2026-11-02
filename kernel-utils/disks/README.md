# 실습용 영구 디스크

`make image`는 systemd로 부팅하는 기본 루트 디스크 `rootfs.img`를 생성합니다.
게스트에서 저장한 파일·설정·설치한 패키지는 다음 부팅에도 유지됩니다.
이미지 파일은 Git에서 제외하며 `make clean`과 `make distclean`으로 지우지 않습니다.

`make update-image`는 게스트 종료 후 모듈과 overlay만 갱신합니다.
`make rebuild`는 새 루트 디스크를 완성한 뒤 기존 디스크를
`rootfs.img.bak.날짜-시간.PID`로 백업하고 교체합니다.
백업에도 `.kernel-release` 기록을 함께 보존합니다.
백업을 부팅하려면 대응하는 커널·모듈 릴리스도 맞아야 합니다.

추가 실습 디스크는 `lab.img` 같은 다른 이름으로 만들고 `make boot DISK=...`로 연결합니다.
기본 루트 디스크는 `/dev/vda`, 추가 디스크는 `/dev/vdb`입니다.
`*.lock`, `*.kernel-release`는 이미지 잠금과 커널 릴리스 확인용 메타데이터입니다.
