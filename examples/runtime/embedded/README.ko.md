# Embedded Runtime

가장 기본이 되는 예제: shell 컴포넌트가 *컨트롤러 프로세스 자체 안에서* 실행됩니다. IPC 없음, 서브프로세스 스폰 없음, 컨테이너 없음.

```yaml
component:
  runtime:
    type: embedded
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{"name": "Alice"}'
# -> {"greeting": "hello from Alice\n"}
```

## 언제 사용하나

- 개발 / 스모크 테스트.
- 저렴하고 안전하며 의존성 격리가 필요 없는 컴포넌트.
- `runtime:` 블록이 주어지지 않았을 때 `native` 컨트롤러의 기본값.

## 사용하지 말아야 할 때

- 무거운 모델 (컨트롤러 스레드를 점유합니다).
- 컨트롤러를 segfault 시킬 수 있는 취약한 네이티브 의존성을 가진 컴포넌트.
- 컨트롤러와 의존성 버전이 충돌하는 컴포넌트.

그런 경우에는 [`../process`](../process), [`../virtualenv-python`](../virtualenv-python), 또는 [`../docker-model`](../docker-model)을 참고하세요.
