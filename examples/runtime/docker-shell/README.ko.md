# Docker Runtime (표준 이미지)

**표준 mindor 런타임 이미지**인 `mindor/component:<version>`으로 빌드된 Docker 컨테이너 안에서 워커를 실행합니다. IPC는 docker 데몬의 attach stdin/stdout 스트림을 통해 이동하므로, 별도의 설정 없이 Linux 네이티브 및 macOS Docker Desktop 모두에서 동작합니다.

```yaml
component:
  runtime:
    type: docker
    # no image / build → the standard image is used
```

## 준비사항

- Docker 데몬이 실행 중이어야 합니다 (macOS/Windows는 Docker Desktop, Linux는 dockerd).

## 실행 방법

```bash
model-compose up
model-compose run --input '{}'
# -> {"uname": "Linux <container-id> ... #1 SMP ... GNU/Linux"}
```

첫 `up` 실행 시 표준 이미지를 로컬에서 빌드하거나(수 분 소요), 이미 게시되어 있다면 pull 합니다. 이후 실행에서는 몇 초 만에 컨테이너가 시작됩니다.

## 이미지 종류

| 종류      | 트리거                                                        |
|-----------|-------------------------------------------------------------|
| STANDARD  | `image:` / `build:` / 프로젝트 수준 `requirements.txt` 없음.  |
| DERIVED   | 프로젝트에 비어있지 않은 `requirements.txt` 존재 (그 위에 추가로 얹음).|
| CUSTOM    | `image:` 또는 `build:` 지정됨 ([../docker-custom-image](../docker-custom-image) 참조). |

## 언제 사용하나

- 어디서나 동일한 런타임 이미지를 사용하고 싶은 CI 환경.
- 호스트 시스템 라이브러리(`libc`, `libstdc++`, ...)로부터 컴포넌트를 격리하고자 할 때.
- macOS에서 Linux 전용 라이브러리를 필요로 하는 컴포넌트를 실행할 때.

## 비교

| 기능                 | `virtualenv` | `docker` |
|----------------------|:-----------:|:--------:|
| 시스템 라이브러리 격리 |      ❌     |     ✅   |
| 크로스 아키텍처/플랫폼 |      ❌     |     ✅   |
| 시작 비용             |    ~5-30s   |  ~5-30s  |
| 콜드 스타트 비용       |   1-3 분    | 1-10 분  |
