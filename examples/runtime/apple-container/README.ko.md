# Apple Container Runtime

macOS 전용 백엔드입니다. Docker Desktop 대신 Apple의 네이티브 [`container`](https://github.com/apple/container) CLI를 사용합니다. IPC는 Docker 백엔드와 동일한 방식으로 부트스트랩되지만, `container start -a -i <name>` 서브프로세스의 stdin/stdout을 통해 이동합니다.

```yaml
component:
  runtime:
    type: apple-container
```

## 준비사항

- Apple의 `container` CLI가 설치되고 구성된 macOS.
- Apple Silicon (M 시리즈) 권장.

확인:

```bash
container --version
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{}'
# -> {"uname": "Linux <container-id> ... aarch64 GNU/Linux"}
```

## 언제 사용하나

- Docker Desktop을 실행하지 않고 네이티브 컨테이너화를 사용하고 싶은 macOS 환경.
- `../docker-shell`을 사용하는 모든 용도지만, Docker Desktop 오버헤드 없이 Apple Silicon에서 실행.

## 참고

- `apple-container`의 DSL은 `docker`와 매우 유사하므로(image, volumes, ports, environment 등), 둘 사이의 마이그레이션은 대부분 `runtime.type`을 변경하는 것으로 충분합니다.
- `image:`는 `container` CLI가 pull 할 수 있는 어떤 OCI 이미지든 가리킬 수 있습니다.
