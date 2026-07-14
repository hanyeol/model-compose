# VirtualEnv Runtime (`pyenv`)

[`../virtualenv-python`](../virtualenv-python)과 같지만, venv가 **pyenv를 통해 설치된 특정 Python 버전**에 대해 생성됩니다. 컴포넌트가 컨트롤러와 다른 Python 버전을 필요로 할 때 사용합니다.

```yaml
component:
  runtime:
    type: virtualenv
    driver: pyenv
    python: "3.11.9"
    path: .venv/py311
```

## 준비사항

`pyenv`가 설치되어 있어야 하며, 요청한 버전이 이미 존재해야 합니다:

```bash
pyenv install 3.11.9   # one-time
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{}'
# -> {"python_version": "Python 3.11.9\n"}
```

컨트롤러가 무엇을 사용하든 관계없이, 워커 서브프로세스는 `~/.pyenv/versions/3.11.9/bin/python`에서 실행됩니다.

## 언제 사용하나

- 컴포넌트에는 Python 3.9가 필요하지만 컨트롤러는 Python 3.12로 실행 중일 때 (혹은 그 반대).
- 특정 인터프리터 빌드에 대해 버그를 재현할 때.

시스템 수준 의존성까지 고정하려면 컨테이너화하세요 — [`../docker-model`](../docker-model)을 참고하세요.
