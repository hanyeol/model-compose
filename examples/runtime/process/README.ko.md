# Process Runtime

모델 워커를 **별도의 OS 프로세스**(via `multiprocessing`)에서 실행합니다. IPC는 `multiprocessing.Queue`를 통해 이동합니다 — 소켓 없음, 파일시스템 없음.

```yaml
component:
  runtime:
    type: process
    start_timeout: 120s
    env:
      TOKENIZERS_PARALLELISM: "false"
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{"text": "I love this project"}'
```

첫 실행 시 모델을 다운로드합니다 (수백 MB). 이후 실행은 빠릅니다.

## 얻는 것

- 모델 로드와 추론이 컨트롤러가 아닌 자식 프로세스에서 발생합니다.
- 네이티브 라이브러리 크래시(segfault, OOM)는 워커만 죽이며 컨트롤러는 죽이지 않습니다.
- `env:` 값은 자식에게*만* 적용되므로, 컨트롤러 환경을 오염시키지 않고 `TOKENIZERS_PARALLELISM`, `CUDA_VISIBLE_DEVICES` 같은 모델별 손잡이(knob)를 조정할 수 있습니다.

## 비교

| 기능                       | `embedded` | `process` |
|----------------------------|:---------:|:---------:|
| 크래시 격리                 |     ❌    |     ✅    |
| 독립적인 환경 변수           |     ❌    |     ✅    |
| 의존성 격리                 |     ❌    |     ❌    |
| 시작 비용                   |     0     |  ~수 초   |

의존성 격리를 원한다면 [`../virtualenv-python`](../virtualenv-python)을 참고하세요.
