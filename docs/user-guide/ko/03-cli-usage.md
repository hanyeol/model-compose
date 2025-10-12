# 3장: CLI 사용법

이 장에서는 model-compose의 모든 CLI 명령어와 옵션을 상세히 다룹니다.

---

## 3.1 기본 명령어

model-compose는 다음 5가지 핵심 명령어를 제공합니다:

- `up` - 서비스 시작 및 실행
- `down` - 서비스 종료 및 정리
- `start` - 서비스 시작
- `stop` - 서비스 중지
- `run` - 워크플로우 일회성 실행

### 명령어 기본 구조

```bash
model-compose [전역옵션] <명령어> [명령어옵션] [인수]
```

### 전역 옵션

모든 명령어에서 사용 가능한 전역 옵션:

```bash
model-compose --file <설정파일> <명령어>
model-compose -f <설정파일> <명령어>
```

**옵션:**
- `--file`, `-f`: 설정 파일 지정 (반복 가능, 여러 파일 병합)
- `--version`: 버전 정보 출력
- `--help`: 도움말 출력

**예제:**
```bash
# 단일 설정 파일
model-compose -f config.yml up

# 여러 설정 파일 병합
model-compose -f base.yml -f override.yml up

# 버전 확인
model-compose --version
```

---

## 3.2 up 명령어

서비스를 시작하고 실행합니다. 새로운 환경을 설정하고 모든 필요한 서비스를 시작합니다.

### 사용법

```bash
model-compose up [옵션]
```

### 옵션

- `-d`, `--detach`: 백그라운드에서 실행
- `--env-file <파일>`: 환경 변수 파일 지정 (반복 가능)
- `-e`, `--env <KEY=VALUE>`: 환경 변수 직접 지정 (반복 가능)
- `-v`, `--verbose`: 상세 출력 활성화

### 예제

**기본 실행:**
```bash
model-compose up
```

**백그라운드 실행:**
```bash
model-compose up -d
```

**환경 변수 파일 사용:**
```bash
model-compose up --env-file .env --env-file .env.production
```

**환경 변수 직접 지정:**
```bash
model-compose up -e OPENAI_API_KEY=sk-xxx -e PORT=9000
```

**상세 로그 출력:**
```bash
model-compose up --verbose
```

**여러 옵션 조합:**
```bash
model-compose -f config.yml up -d --env-file .env -v
```

### 동작

1. 설정 파일 로드 및 검증
2. 환경 변수 로드 및 병합
3. 컴포넌트 설정 및 시작
4. 리스너 및 게이트웨이 설정
5. 컨트롤러 시작
6. Web UI 시작 (설정된 경우)

---

## 3.3 down 명령어

실행 중인 서비스를 종료하고 모든 리소스를 정리합니다.

### 사용법

```bash
model-compose down [옵션]
```

### 옵션

- `--env-file <파일>`: 환경 변수 파일 지정 (반복 가능)
- `-e`, `--env <KEY=VALUE>`: 환경 변수 직접 지정 (반복 가능)
- `-v`, `--verbose`: 상세 출력 활성화

### 예제

**기본 종료:**
```bash
model-compose down
```

**환경 변수와 함께:**
```bash
model-compose down --env-file .env
```

**상세 로그:**
```bash
model-compose down --verbose
```

### 동작

1. 설정 파일 로드
2. 실행 중인 서비스 확인
3. 컨트롤러 중지
4. 컴포넌트 정리
5. 리스너 및 게이트웨이 정리
6. 리소스 해제

---

## 3.4 start 명령어

이미 설정된 서비스를 시작합니다. `up`과 달리 새로운 설정 없이 시작만 수행합니다.

### 사용법

```bash
model-compose start [옵션]
```

### 옵션

- `--env-file <파일>`: 환경 변수 파일 지정 (반복 가능)
- `-e`, `--env <KEY=VALUE>`: 환경 변수 직접 지정 (반복 가능)
- `-v`, `--verbose`: 상세 출력 활성화

### 예제

```bash
model-compose start
model-compose start --verbose
model-compose start --env-file .env
```

### up vs start

| 명령어 | 용도 | 동작 |
|--------|------|------|
| `up` | 초기 설정 및 시작 | 설정 생성 + 서비스 시작 |
| `start` | 기존 서비스 시작 | 서비스 시작만 |

---

## 3.5 stop 명령어

실행 중인 서비스를 중지합니다. 설정은 유지되며 `start`로 재시작할 수 있습니다.

### 사용법

```bash
model-compose stop [옵션]
```

### 옵션

- `--env-file <파일>`: 환경 변수 파일 지정 (반복 가능)
- `-e`, `--env <KEY=VALUE>`: 환경 변수 직접 지정 (반복 가능)
- `-v`, `--verbose`: 상세 출력 활성화

### 예제

```bash
model-compose stop
model-compose stop --verbose
```

### stop vs down

| 명령어 | 용도 | 동작 |
|--------|------|------|
| `stop` | 일시 중지 | 서비스 중지 (설정 유지) |
| `down` | 완전 종료 | 서비스 중지 + 리소스 정리 |

---

## 3.6 run 명령어

워크플로우를 일회성으로 실행합니다. CLI에서 직접 워크플로우를 테스트하거나 스크립트에서 사용하기 적합합니다.

### 사용법

```bash
model-compose run [워크플로우ID] [옵션]
```

### 인수

- `워크플로우ID`: 실행할 워크플로우 ID (선택, 기본값은 default 워크플로우)

### 옵션

- `-i`, `--input <JSON>`: 워크플로우 입력 데이터 (JSON 형식)
- `--env-file <파일>`: 환경 변수 파일 지정 (반복 가능)
- `-e`, `--env <KEY=VALUE>`: 환경 변수 직접 지정 (반복 가능)
- `-o`, `--output <파일>`: 출력을 파일로 저장
- `-v`, `--verbose`: 상세 출력 활성화

### 예제

**기본 워크플로우 실행:**
```bash
model-compose run
```

**특정 워크플로우 실행:**
```bash
model-compose run generate-text
```

**입력 데이터와 함께:**
```bash
model-compose run generate-text --input '{"prompt": "안녕하세요"}'
```

**입력 JSON 포맷팅:**
```bash
model-compose run generate-text --input '{
  "prompt": "AI에 대해 설명해줘",
  "temperature": 0.7
}'
```

**출력을 파일로 저장:**
```bash
model-compose run generate-text \
  --input '{"prompt": "Hello"}' \
  --output result.json
```

**환경 변수 지정:**
```bash
model-compose run generate-text \
  --input '{"prompt": "Test"}' \
  --env OPENAI_API_KEY=sk-xxx
```

**여러 옵션 조합:**
```bash
model-compose -f config.yml run my-workflow \
  --input '{"data": "test"}' \
  --env-file .env \
  --output output.json \
  --verbose
```

### 출력 형식

워크플로우 실행 결과는 JSON 형식으로 출력됩니다:

```json
{
  "response": "워크플로우 실행 결과..."
}
```

에러 발생 시:
```json
{
  "error": "에러 메시지..."
}
```

---

## 3.7 환경 변수 관리

model-compose는 다양한 방법으로 환경 변수를 관리할 수 있습니다.

### 방법 1: .env 파일

`.env` 파일에 환경 변수를 정의:

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key
PORT=8080
```

사용:
```bash
model-compose up --env-file .env
```

### 방법 2: 여러 .env 파일

환경별로 분리된 파일 사용:

```bash
# .env.base
PORT=8080
LOG_LEVEL=info

# .env.production
OPENAI_API_KEY=sk-prod-key
```

사용 (나중 파일의 값이 우선 적용됨):
```bash
model-compose up --env-file .env.base --env-file .env.production
```

### 방법 3: 명령줄 직접 지정

```bash
model-compose up -e OPENAI_API_KEY=sk-xxx -e PORT=9000
```

### 방법 4: 시스템 환경 변수

설정 파일에서 시스템 환경 변수 직접 참조:

```bash
export OPENAI_API_KEY=sk-xxx
model-compose up
```

### 우선순위

환경 변수는 다음 순서로 우선순위가 적용됩니다 (높은 순):

1. 명령줄 `-e` 옵션
2. `--env-file` 파일 (나중 파일이 우선)
3. 시스템 환경 변수

### 보안 권장사항

- `.env` 파일을 `.gitignore`에 추가
- 프로덕션 키는 별도 파일로 관리
- 민감한 정보는 명령줄에 직접 입력하지 않기
- CI/CD에서는 시스템 환경 변수 사용

---

## 3.8 설정 파일 지정

### 단일 설정 파일

```bash
model-compose -f model-compose.yml up
```

### 여러 설정 파일 병합

나중 파일의 값이 우선 적용됩니다:

```bash
model-compose -f base.yml -f override.yml up
```

**예제:**

`base.yml`:
```yaml
controller:
  type: http-server
  port: 8080

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
```

`override.yml`:
```yaml
controller:
  port: 9000  # base.yml의 port를 덮어씀

components:
  - id: custom-component
    type: http-client
```

결과: 포트는 9000, 컴포넌트는 모두 포함

### 기본 설정 파일

설정 파일을 지정하지 않으면 현재 디렉토리에서 다음 순서로 찾습니다:

1. `model-compose.yml`
2. `model-compose.yaml`

```bash
# 자동으로 model-compose.yml 사용
model-compose up
```

### 환경별 설정

```bash
# 개발 환경
model-compose -f base.yml -f dev.yml up

# 스테이징 환경
model-compose -f base.yml -f staging.yml up

# 프로덕션 환경
model-compose -f base.yml -f production.yml up
```

---

## 3.9 디버깅 옵션

### Verbose 모드

모든 명령어에서 `-v` 또는 `--verbose` 플래그를 사용하여 상세 로그를 활성화할 수 있습니다:

```bash
model-compose up --verbose
model-compose run my-workflow --input '{}' --verbose
```

**Verbose 모드에서 출력되는 정보:**
- 설정 파일 로딩 과정
- 환경 변수 병합 과정
- 컴포넌트 초기화 로그
- HTTP 요청/응답 상세 정보
- 워크플로우 실행 단계별 로그
- 에러 스택 트레이스

### 에러 메시지

model-compose는 명확한 에러 메시지를 제공합니다:

```bash
❌ Invalid JSON provided for --input
❌ Configuration file not found: config.yml
❌ Environment variable OPENAI_API_KEY is required
```

### 일반적인 문제 해결

**문제: 설정 파일을 찾을 수 없음**
```bash
# 해결: 파일 경로 확인
model-compose -f ./configs/model-compose.yml up
```

**문제: 환경 변수 누락**
```bash
# 해결: 환경 변수 지정
model-compose up --env-file .env
```

**문제: JSON 파싱 에러**
```bash
# 잘못된 예
model-compose run --input '{prompt: "test"}'  # ❌

# 올바른 예
model-compose run --input '{"prompt": "test"}'  # ✅
```

---

## 3.10 실전 사용 예제

### 개발 워크플로우

```bash
# 1. 개발 환경 설정 파일 준비
# dev.yml

# 2. 서비스 시작
model-compose -f base.yml -f dev.yml up

# 3. 워크플로우 테스트
model-compose run test-workflow --input '{"test": true}' --verbose

# 4. 수정 후 재시작
model-compose stop
model-compose start
```

### 프로덕션 배포

```bash
# 1. 프로덕션 환경 변수 설정
export OPENAI_API_KEY=sk-prod-xxx
export ELEVENLABS_API_KEY=prod-xxx

# 2. 프로덕션 설정으로 시작
model-compose -f base.yml -f production.yml up -d

# 3. 상태 확인 (로그 확인)
docker logs <container-id>  # Docker 런타임인 경우
```

### CI/CD 파이프라인

```bash
#!/bin/bash
# deploy.sh

# 환경 변수 로드
source .env.production

# 서비스 배포
model-compose -f base.yml -f production.yml up -d

# 헬스 체크
curl http://localhost:8080/health

# 테스트 실행
model-compose run smoke-test --input '{}' --verbose
```

### 스크립팅

```bash
#!/bin/bash
# batch-process.sh

# 여러 입력에 대해 워크플로우 실행
for file in inputs/*.json; do
  echo "Processing $file..."
  model-compose run process-data \
    --input "$(cat $file)" \
    --output "outputs/$(basename $file)" \
    --verbose
done
```

---

## 3.11 명령어 빠른 참조

### 기본 명령어

| 명령어 | 설명 | 주요 옵션 |
|--------|------|----------|
| `up` | 서비스 시작 및 실행 | `-d`, `--env-file`, `-v` |
| `down` | 서비스 종료 및 정리 | `--env-file`, `-v` |
| `start` | 서비스 시작 | `--env-file`, `-v` |
| `stop` | 서비스 중지 | `--env-file`, `-v` |
| `run` | 워크플로우 실행 | `-i`, `-o`, `--env-file`, `-v` |

### 전역 옵션

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--file` | `-f` | 설정 파일 지정 |
| `--version` | - | 버전 정보 출력 |
| `--help` | - | 도움말 출력 |

### 공통 옵션

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--env-file` | - | 환경 변수 파일 |
| `--env` | `-e` | 환경 변수 직접 지정 |
| `--verbose` | `-v` | 상세 출력 |

### run 명령어 전용 옵션

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--input` | `-i` | 입력 JSON 데이터 |
| `--output` | `-o` | 출력 파일 경로 |

---

## 다음 단계

실습해보세요:
- 다양한 명령어 조합 실험하기
- 환경별 설정 파일 구성하기
- 스크립트에서 model-compose 활용하기

---

**다음 장**: [4. 컴포넌트 구성](./04-component-configuration.md)
