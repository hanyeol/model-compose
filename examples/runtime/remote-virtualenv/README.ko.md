# Remote VirtualEnv Runtime (원격 venv 안의 shell)

`shell` 컴포넌트를 SSH로 접근한 **원격 호스트의 venv 격리 워커** 안에서 실행합니다. 컨트롤러는 로컬 머신에 남아 있고, venv는 SSH 사용자의 ``working_dir`` 아래 원격 파일시스템에 생성되며, 워커는 그 venv에서 띄운 `python -m mindor.core.component.runtime.virtualenv.remote`입니다.

`virtualenv + remote` 런타임을 end-to-end로 검증하는 용도로 쓰세요. venv provisioning은 지연 수행 — 첫 `up`이 venv를 만들고 `mindor` + runtime 요구사항을 설치하며, 이후 실행은 몇 초 만에 같은 venv를 재사용합니다.

## 사전 요구사항

원격 호스트에 필요한 것:

- 키 인증 기반 SSH 접근.
- 사용자의 interactive 쉘에서 `import mindor`가 가능한 Python 인터프리터 (pyenv, 시스템 python, `.bashrc`에서 activate된 venv 모두 OK). 런타임이 `sys.executable`로 해석합니다.
- `python -m venv` 사용 가능 (표준 라이브러리 — 별도 설치 불필요).
- 선택: `$PATH`의 `uv`가 있으면 requirement 설치가 극적으로 빨라지고 venv 간 wheel 캐시 공유도 됩니다. `uv`가 없으면 venv의 `pip`로 폴백합니다.

원격의 mindor는 venv의 site-packages에 있는 `mindor.pth` 파일로 연결됩니다 (editable-install 방식). 따라서 설정 중 호스트와 원격 사이의 바이트 전송은 발생하지 않습니다.

## 설정

`.env.sample`을 `.env`로 복사하고 SSH 세부 정보를 채워 넣으세요:

```bash
cp .env.sample .env
```

```bash
REMOTE_HOST=gpu-box.example.com
REMOTE_USER=hanyeol
REMOTE_SSH_KEY=~/.ssh/id_ed25519
REMOTE_WORKING_DIR=/home/hanyeol/Projects/model-compose
```

`REMOTE_WORKING_DIR`는 두 가지 역할을 합니다:
- python / mindor를 해석하기 전에 SSH 세션이 `cd`하는 디렉터리.
- venv 경로의 앵커 (`{working_dir}/.runtime/components/<id>/venv`).

`import mindor`가 올바르게 해석되도록 원격의 mindor 체크아웃/설치 위치를 가리키게 하세요.

## 실행

```bash
model-compose up
model-compose run --input '{}'
```

예상 출력:

```
hello from <remote-hostname>: Linux <remote-hostname> ... x86_64 GNU/Linux via /home/.../.runtime/components/__component__/venv/bin/python
```

`hostname`, `uname -a`, `sys.executable` 모두 **원격 호스트에서** 평가되며, python 경로는 **venv의** 인터프리터를 가리킵니다 — 쉘 명령이 venv 안에서 실행됐다는 증거입니다.

첫 실행에서 `model-compose up`이 하는 일:

1. `REMOTE_USER`로 `REMOTE_HOST`에 SSH 연결을 엽니다.
2. 원격 사용자의 python을 해석하고 (interactive-shell의 `sys.executable`), `import mindor`가 가리키는 디렉터리를 찾습니다.
3. `<remote-python> -m venv ...`로 `{REMOTE_WORKING_DIR}/.runtime/components/__component__/venv`를 생성합니다 (이미 있으면 skip).
4. 원격 mindor 소스를 가리키는 `mindor.pth`를 venv의 site-packages에 작성합니다.
5. mindor runtime 요구사항을 `uv pip install` (또는 venv pip)로 설치합니다. 두 번째 실행부턴 3–5가 전부 skip됩니다.
6. venv에서 `python -m mindor.core.component.runtime.virtualenv.remote`를 exec 채널로 띄웁니다. stdio가 IPC 스트림을 운반합니다.

이후 `model-compose run`을 하면:

- 입력이 SSH exec 채널로 전달되고, 쉘 명령이 원격 호스트의 venv 안에서 실행되며, stdout이 반환됩니다.

`model-compose down`은 SSH 연결을 닫고 워커는 함께 종료됩니다. 디스크의 venv는 다음 `up`을 위해 그대로 남아 있습니다.

## 왜 이 예제인가

`shell`은 모델 가중치도, GPU도, 프로젝트별 요구사항도 없습니다 — 원격 venv 배관만 다른 모든 요소로부터 격리합니다. 이 왕복이 작동하면 SSH 트랜스포트, venv provisioning, mindor 소스 연결, 워커 핸드쉐이크가 전부 정상이고, 더 무거운 `virtualenv + remote` 워크로드에서 실패가 생기면 그건 워크로드의 문제이지 런타임의 문제가 아닙니다.
