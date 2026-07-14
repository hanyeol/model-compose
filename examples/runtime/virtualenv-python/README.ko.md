# VirtualEnv Runtime (Python `venv`)

`python -m venv`로 생성된 **전용 Python 가상 환경** 안에서 모델 워커를 실행합니다. 이 디렉토리의 `requirements.txt`는 `transformers` + `torch`를 해당 venv에만 설치하며, 컨트롤러의 site-packages는 절대로 건드리지 않습니다.

```yaml
component:
  runtime:
    type: virtualenv
    driver: python
    path: .venv/classifier
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{"text": "You are a wonderful person"}'
```

첫 `up`은:
- 이 파일 옆에 `.venv/classifier/`를 생성하고,
- `requirements.txt`를 해당 venv에 pip-install 하며,
- mindor를 venv의 site-packages에 주입하고,
- `.venv/classifier/bin/python`에서 워커를 실행(spawn)합니다.

이후 `up`은 mindor 버전이나 `requirements.txt`가 변경되지 않는 한 venv를 재사용합니다.

## 얻는 것

- `process`가 제공하는 모든 것에 더해:
- 컴포넌트별 독립적인 의존성 버전.
- 어떤 컴포넌트가 호환되지 않는 `torch`를 끌어와서 컨트롤러 설치를 망칠 위험이 없습니다.

## 비교

| 기능                   | `process` | `virtualenv-python` |
|------------------------|:---------:|:-------------------:|
| OS 수준 격리           |     ✅    |          ✅         |
| 의존성 격리            |     ❌    |          ✅         |
| Python 버전 고정        |     ❌    |          ❌         |

Python 버전 고정이 필요하면 [`../virtualenv-pyenv`](../virtualenv-pyenv)를 참고하세요.
시스템 수준 격리가 필요하면 [`../docker-model`](../docker-model)을 참고하세요.
