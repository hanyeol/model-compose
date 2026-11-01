# Remote Process Runtime (SSH 호스트의 shell)

`shell` 컴포넌트를 SSH로 접근한 **원격 호스트의 워커 프로세스** 안에서 실행합니다. 컨트롤러는 로컬 머신에 남아 있고, 워커는 컨트롤러가 원격 쪽에서 띄운 `python -m mindor.core.component.runtime.process.remote`이며, 쉘 명령은 그 호스트의 워커 로컬 쉘에서 실행됩니다.

의존성 없는 워크로드로 `process + remote` 런타임을 end-to-end로 검증하는 용도로 쓰세요. 이게 돌면 `shell`을 `runtime: process`를 쓰는 다른 어떤 컴포넌트로 바꿔도 됩니다 — 원격 배선은 동일합니다.

## 사전 요구사항

원격 호스트에 필요한 것:

- 키 인증 기반 SSH 접근.
- `import mindor`가 가능한 Python 인터프리터. 가장 간단한 방법은 이 프로젝트를 설치하는 것 (`pip install -e .` 또는 릴리스 시 `pip install model-compose`)인데, 로그인 쉘의 `python`이 보는 시스템/사용자 site-packages에 들어가야 합니다.
- 원격 사용자의 `$PATH`에서 접근 가능한 `python` 실행 파일.

데몬도, 컨테이너도, 볼륨 마운트도 없음 — 그냥 SSH와 Python만.

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

`REMOTE_WORKING_DIR`는 워커가 Python을 띄우기 전에 `cd`하는 디렉터리입니다. `import mindor`가 올바르게 해석되도록 원격의 mindor 체크아웃/설치 위치를 가리키게 하세요.

키는 암호화되지 않았거나 로컬 SSH agent로 접근 가능해야 합니다. agent 폴백 및 암호화된 키는 아직 지원하지 않습니다.

## 실행

```bash
model-compose up
model-compose run --input '{}'
```

예상 출력:

```
hello from <remote-hostname>: Linux <remote-hostname> 6.x.x-generic ... x86_64 GNU/Linux
```

`hostname`과 `uname -a`는 **원격 호스트에서** 평가되므로, 로컬 머신과 결과가 다르다는 건 워커가 거기서 돌고 있다는 뜻입니다.

`model-compose up`이 하는 일:

1. `REMOTE_USER`로 `REMOTE_HOST`에 SSH 연결을 엽니다.
2. 원격 쪽에서 `python -m mindor.core.component.runtime.process.remote`를 띄웁니다. exec 채널의 stdin/stdout이 IPC 스트림(프레이밍된 메시지)을 운반하고, stderr가 로그 출력을 담당합니다.
3. 컴포넌트 config를 IPC START 메시지로 보냅니다. 원격 워커가 `shell` 컴포넌트를 in-process로 띄웁니다.

이후 `model-compose run`을 하면:

- 입력이 SSH exec 채널로 전달되고, 쉘 명령이 원격 호스트에서 실행되며, stdout이 반환됩니다.

`model-compose down`은 SSH 연결을 닫고, 원격 워커 프로세스는 함께 종료됩니다.

## 왜 이 예제인가

`shell`은 모델 가중치도, GPU도, pip 설치도 없습니다 — 원격 프로세스 배관만 다른 모든 요소로부터 격리합니다. 이 왕복이 작동하면 SSH 트랜스포트, exec 채널, 워커 핸드쉐이크가 전부 정상이고, 더 무거운 `process + remote` 워크로드에서 실패가 생기면 그건 워크로드의 문제이지 런타임의 문제가 아닙니다.
