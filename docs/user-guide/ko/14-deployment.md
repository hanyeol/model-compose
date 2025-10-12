# 14. 배포

이 장에서는 model-compose 애플리케이션을 로컬 환경에서 실행하거나 Docker 컨테이너로 배포하는 방법을 설명합니다.

---

## 14.1 로컬 실행

### 14.1.1 기본 실행

model-compose는 기본적으로 네이티브 런타임을 사용하여 로컬 환경에서 직접 실행됩니다.

**컨트롤러 시작:**

```bash
model-compose up
```

기본 동작:
- 현재 디렉토리의 `model-compose.yml` 파일 로드
- 네이티브 런타임으로 서비스 시작
- 포그라운드 모드로 실행 (로그 출력)
- Ctrl+C로 종료 가능

**백그라운드 실행:**

```bash
model-compose up -d
```

백그라운드 모드에서는:
- 서비스가 별도 프로세스로 실행됩니다
- `model-compose down`으로 중지할 수 있습니다

**컨트롤러 중지:**

```bash
model-compose down
```

중지 과정:
1. `.stop` 파일 생성
2. 컨트롤러가 파일을 감지 (1초마다 폴링)
3. 서비스 정상 종료
4. 리소스 정리

### 14.1.2 환경 변수 관리

**`.env` 파일 사용:**

```bash
# .env 파일 생성
cat > .env <<EOF
OPENAI_API_KEY=sk-proj-...
MODEL_CACHE_DIR=/models
LOG_LEVEL=info
EOF

# .env 파일 자동 로드
model-compose up
```

**커스텀 `.env` 파일:**

```bash
model-compose up --env-file .env.production
```

**개별 환경 변수 오버라이드:**

```bash
model-compose up -e OPENAI_API_KEY=sk-proj-... -e LOG_LEVEL=debug
```

환경 변수 우선순위:
1. `--env` / `-e` 플래그로 전달된 값 (최우선)
2. `--env-file`로 지정한 파일
3. 기본 `.env` 파일
4. 시스템 환경 변수

### 14.1.3 설정 파일 지정

**커스텀 설정 파일 사용:**

```bash
model-compose up -f custom-compose.yml
```

**여러 설정 파일 병합:**

```bash
model-compose up -f base.yml -f override.yml
```

### 14.1.4 워크플로우 단독 실행

컨트롤러 없이 워크플로우만 실행:

```bash
model-compose run my-workflow --input '{"text": "Hello"}'
```

특징:
- 컨트롤러를 시작하지 않음
- 워크플로우 한 번만 실행 후 종료
- CI/CD 파이프라인이나 배치 작업에 유용

**JSON 파일로 입력 전달:**

```bash
model-compose run my-workflow --input @input.json
```

### 14.1.5 디버깅 옵션

**상세 로그 출력:**

설정 파일에서 로거 레벨 지정:

```yaml
controller:
  type: http-server
  port: 8080

logger:
  - type: console
    level: debug        # debug, info, warning, error, critical
```

---

## 14.2 Docker 런타임

### 14.2.1 기본 Docker 설정

**간단한 Docker 런타임 설정:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime: docker                 # 문자열 형식
```

이 설정은 다음과 같이 확장됩니다:

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    # 기본 이미지 사용 (자동 빌드)
```

**이미지 지정:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    image: my-registry/model-compose:latest
    container_name: my-controller
```

실행 흐름:
1. 레지스트리에서 이미지 pull 시도
2. Pull 실패 시 로컬 빌드 시도
3. 컨테이너 생성 및 시작
4. 로그 스트리밍 (포그라운드) 또는 detach (백그라운드)

**포트 매핑:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    ports:
      - "5000:8080"                # 호스트:컨테이너
      - 8081                       # 동일 포트 사용 (8081:8081)
```

포트 형식:
- 문자열: `"호스트포트:컨테이너포트"`
- 정수: `포트` (호스트와 컨테이너 동일)
- 객체: 고급 설정 (아래 참조)

### 14.2.2 고급 Docker 옵션

**이미지 빌드 설정:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    build:
      context: .                   # 빌드 컨텍스트 경로
      dockerfile: Dockerfile       # 커스텀 Dockerfile
      args:                        # 빌드 인자
        PYTHON_VERSION: "3.11"
        MODEL_NAME: "llama-2"
      target: production           # 멀티 스테이지 빌드 타겟
      cache_from:                  # 캐시 이미지
        - my-registry/cache:latest
      labels:
        app: model-compose
        version: "1.0"
      network: host                # 빌드 시 네트워크 모드
      pull: true                   # 항상 베이스 이미지 pull
```

**포트 고급 설정:**

```yaml
controller:
  runtime:
    type: docker
    ports:
      - target: 8080               # 컨테이너 포트
        published: 5000            # 호스트 포트
        protocol: tcp              # tcp 또는 udp
        mode: host                 # host 또는 ingress
```

**네트워크 설정:**

```yaml
controller:
  runtime:
    type: docker
    networks:
      - my-network                 # 기존 네트워크 연결
      - bridge                     # Docker 기본 브리지
```

**컨테이너 실행 옵션:**

```yaml
controller:
  runtime:
    type: docker
    hostname: model-compose-host   # 컨테이너 호스트명
    command:                       # CMD 오버라이드
      - python
      - -m
      - mindor.cli.compose
      - up
      - --verbose
    entrypoint: /bin/bash          # ENTRYPOINT 오버라이드
    working_dir: /app              # 작업 디렉토리
    user: "1000:1000"              # 사용자:그룹 ID
```

**리소스 제한:**

```yaml
controller:
  runtime:
    type: docker
    mem_limit: 2g                  # 메모리 제한 (512m, 2g 등)
    memswap_limit: 4g              # 메모리 + 스왑 제한
    cpus: "2.0"                    # CPU 할당 (0.5, 2.0 등)
    cpu_shares: 1024               # 상대적 CPU 가중치
```

**재시작 정책:**

```yaml
controller:
  runtime:
    type: docker
    restart: always                # no, always, on-failure, unless-stopped
```

재시작 정책 설명:
- `no`: 재시작하지 않음 (기본값)
- `always`: 항상 재시작
- `on-failure`: 오류로 종료 시에만 재시작
- `unless-stopped`: 수동 중지 전까지 재시작

**헬스 체크:**

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s                # 체크 간격
      timeout: 10s                 # 타임아웃
      max_retry_count: 3           # 최대 재시도 횟수
      start_period: 40s            # 시작 유예 시간
```

또는 간단하게:

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: "curl -f http://localhost:8080/health || exit 1"
```

**보안 옵션:**

```yaml
controller:
  runtime:
    type: docker
    privileged: false              # 권한 모드 (보안상 비권장)
    security_opt:
      - apparmor=unconfined
      - seccomp=unconfined
```

**로깅 설정:**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

**라벨:**

```yaml
controller:
  runtime:
    type: docker
    labels:
      environment: production
      team: ml-ops
      version: "1.0.0"
```

### 14.2.3 볼륨 및 환경 변수

**볼륨 마운트 - 간단한 형식:**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      - ./models:/models           # 바인드 마운트
      - ./cache:/cache:ro          # 읽기 전용
      - model-data:/data           # Named 볼륨
```

**볼륨 마운트 - 상세 형식:**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      # 바인드 마운트
      - type: bind
        source: ./models           # 호스트 경로
        target: /models            # 컨테이너 경로
        read_only: false
        bind:
          propagation: rprivate

      # Named 볼륨
      - type: volume
        source: model-data         # 볼륨 이름
        target: /data
        volume:
          nocopy: false

      # tmpfs (임시 메모리)
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 1073741824         # 1GB (바이트)
          mode: 1777
```

볼륨 타입 설명:
- `bind`: 호스트 디렉토리/파일을 컨테이너에 마운트
- `volume`: Docker가 관리하는 Named 볼륨
- `tmpfs`: 메모리 기반 임시 파일시스템 (컨테이너 종료 시 삭제)

**환경 변수 설정:**

```yaml
controller:
  runtime:
    type: docker
    environment:
      OPENAI_API_KEY: ${env.OPENAI_API_KEY}   # 호스트 환경 변수 전달
      MODEL_CACHE_DIR: /models
      LOG_LEVEL: info
      WORKERS: 4
```

**환경 변수 파일:**

```yaml
controller:
  runtime:
    type: docker
    env_file:
      - .env                       # 단일 파일
      - .env.production            # 여러 파일
```

---

## 14.3 Docker 컨테이너 빌드 및 배포

### 14.3.1 자동 빌드 프로세스

model-compose는 Docker 런타임 사용 시 자동으로 이미지를 빌드합니다.

**빌드 컨텍스트 준비:**

`model-compose up` 실행 시:
1. `.docker/` 디렉토리 생성
2. 소스 코드 복사 (mindor 패키지)
3. `requirements.txt` 복사/생성
4. `model-compose.yml` 생성 (네이티브 런타임으로 변환)
5. Web UI 디렉토리 복사 (설정 시)
6. Dockerfile 복사 또는 기본 Dockerfile 사용

**기본 Dockerfile:**

```dockerfile
FROM ubuntu:22.04

WORKDIR /app

# Python 3.11 설치
RUN apt update && apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 심볼릭 링크
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# 기본 의존성 설치
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir \
    click pyyaml pydantic python-dotenv \
    aiohttp requests fastapi uvicorn \
    'mcp>=1.10.1' pyngrok ulid gradio Pillow

# 프로젝트 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY src .
COPY webui ./webui
COPY model-compose.yml .

# 기본 명령어
CMD [ "python", "-m", "mindor.cli.compose", "up" ]
```

### 14.3.2 커스텀 Dockerfile 사용

프로젝트에 특화된 Docker 이미지를 사용하려면 커스텀 Dockerfile을 작성할 수 있습니다.

**프로젝트 디렉토리 구조:**

```
my-project/
├── model-compose.yml    # 워크플로우 설정
├── Dockerfile           # 커스텀 Docker 이미지
├── requirements.txt     # Python 의존성 (선택)
└── .env                 # 환경 변수 (선택)
```

**참고**: 커스텀 Dockerfile을 사용하려면 `build` 섹션에서 명시적으로 지정해야 합니다. Dockerfile은 프로젝트 루트 또는 원하는 위치에 배치할 수 있습니다.

**Dockerfile 예시:**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt update && apt install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# model-compose 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 모델 사전 다운로드
RUN python -c "from transformers import AutoModel; AutoModel.from_pretrained('bert-base-uncased')"

# 애플리케이션 복사
COPY . .

CMD [ "model-compose", "up" ]
```

**설정에서 커스텀 Dockerfile 지정 (필수):**

커스텀 Dockerfile을 사용하려면 `build` 섹션을 반드시 지정해야 합니다:

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    build:
      context: .                   # 빌드 컨텍스트 (프로젝트 루트)
      dockerfile: Dockerfile       # 커스텀 Dockerfile (필수)
```

### 14.3.3 멀티 스테이지 빌드

**개발/프로덕션 분리:**

```dockerfile
# Stage 1: 빌드 환경
FROM python:3.11 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY src ./src

# Stage 2: 런타임 환경
FROM python:3.11-slim AS runtime

WORKDIR /app

# 빌더에서 패키지 복사
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app/src ./src

# PATH 업데이트
ENV PATH=/root/.local/bin:$PATH

COPY model-compose.yml .

CMD [ "model-compose", "up" ]

# Stage 3: 개발 환경
FROM runtime AS development

RUN pip install --no-cache-dir pytest black flake8

CMD [ "model-compose", "up", "--verbose" ]
```

**설정에서 타겟 지정:**

```yaml
# 프로덕션
controller:
  runtime:
    type: docker
    build:
      context: .
      target: runtime

---
# 개발
controller:
  runtime:
    type: docker
    build:
      context: .
      target: development
```

### 14.3.4 이미지 레지스트리 사용

**이미지 빌드 및 푸시:**

```bash
# 로컬 빌드
docker build -t my-registry.com/model-compose:1.0 .

# 레지스트리에 푸시
docker push my-registry.com/model-compose:1.0
```

**설정에서 레지스트리 이미지 사용:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    image: my-registry.com/model-compose:1.0
    container_name: model-compose-prod
```

실행 시:
1. 레지스트리에서 이미지 pull
2. 컨테이너 생성 및 시작
3. 로컬 빌드 과정 생략

### 14.3.5 프라이빗 레지스트리 인증

**Docker 로그인:**

```bash
docker login my-registry.com
```

또는 환경 변수:

```bash
export DOCKER_USERNAME=myuser
export DOCKER_PASSWORD=mypass
docker login -u $DOCKER_USERNAME -p $DOCKER_PASSWORD my-registry.com
```

**인증 정보는 `~/.docker/config.json`에 저장됩니다.**

---

## 14.4 프로덕션 환경 고려사항

### 14.4.1 동시성 제어

**컨트롤러 레벨 동시성:**

```yaml
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 10         # 최대 10개 워크플로우 동시 실행
  threaded: false                  # 스레드 기반 실행 (기본: false)
```

동시성 설정:
- `max_concurrent_count: 0`: 무제한 (기본값, 주의 필요)
- `max_concurrent_count: N`: 최대 N개 동시 실행
- `threaded: true`: 각 워크플로우를 별도 스레드에서 실행

**컴포넌트 레벨 동시성:**

```yaml
components:
  - id: api-client
    type: http-client
    base_url: https://api.example.com
    max_concurrent_count: 5        # 이 컴포넌트는 최대 5개 동시 요청
```

### 14.4.2 리소스 제한

**메모리 제한:**

```yaml
controller:
  runtime:
    type: docker
    mem_limit: 4g                  # 최대 4GB 메모리
    memswap_limit: 6g              # 메모리 + 스왑 6GB
```

메모리 단위:
- `b`: 바이트
- `k`: 킬로바이트
- `m`: 메가바이트
- `g`: 기가바이트

**CPU 제한:**

```yaml
controller:
  runtime:
    type: docker
    cpus: "2.0"                    # 최대 2 CPU 코어 사용
    cpu_shares: 1024               # 상대적 CPU 가중치
```

CPU 설정:
- `cpus`: 절대적 CPU 제한 (0.5 = 50%, 2.0 = 200%)
- `cpu_shares`: 상대적 가중치 (기본값 1024)

### 14.4.3 재시작 정책

**자동 재시작 설정:**

```yaml
controller:
  runtime:
    type: docker
    restart: unless-stopped        # 수동 중지 전까지 항상 재시작
```

프로덕션 권장 설정:
- `always`: 항상 재시작 (시스템 재부팅 포함)
- `unless-stopped`: 수동 중지 전까지 재시작
- `on-failure`: 오류 시에만 재시작

### 14.4.4 헬스 체크

**HTTP 엔드포인트 헬스 체크:**

model-compose는 기본적으로 `/health` 엔드포인트를 제공합니다.

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      max_retry_count: 3
      start_period: 40s
```

헬스 체크 응답:

```json
{
  "status": "ok"
}
```

**커스텀 헬스 체크:**

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import requests; requests.get(\"http://localhost:8080/health\")' || exit 1"]
      interval: 20s
```

### 14.4.5 보안 고려사항

**비권한 모드 실행:**

```yaml
controller:
  runtime:
    type: docker
    privileged: false              # 항상 false 권장
    user: "1000:1000"              # 비루트 사용자
```

**시크릿 관리:**

환경 변수로 민감한 정보 전달:

```yaml
controller:
  runtime:
    type: docker
    environment:
      OPENAI_API_KEY: ${env.OPENAI_API_KEY}     # 호스트에서 주입
      DB_PASSWORD: ${env.DB_PASSWORD}
```

실행 시:

```bash
export OPENAI_API_KEY=sk-proj-...
export DB_PASSWORD=secret
model-compose up
```

또는 `.env` 파일 사용 (저장소에 커밋하지 말 것):

```bash
# .env.production
OPENAI_API_KEY=sk-proj-...
DB_PASSWORD=secret
```

```bash
model-compose up --env-file .env.production
```

**네트워크 격리:**

```yaml
controller:
  runtime:
    type: docker
    networks:
      - isolated-network           # 격리된 네트워크 사용
```

### 14.4.6 데이터 영속성

**볼륨 마운트로 데이터 보존:**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      - ./data:/data               # 로컬 데이터 디렉토리
      - model-cache:/cache         # Named 볼륨
      - ./logs:/app/logs           # 로그 디렉토리
```

Named 볼륨 생성:

```bash
docker volume create model-cache
```

볼륨 확인:

```bash
docker volume ls
docker volume inspect model-cache
```

---

## 14.5 모니터링 및 로깅

### 14.5.1 로거 설정

**콘솔 로거:**

```yaml
logger:
  - type: console
    level: info                    # debug, info, warning, error, critical
```

로그 레벨:
- `debug`: 모든 로그 (개발용)
- `info`: 일반 정보 (기본값)
- `warning`: 경고 메시지
- `error`: 오류 메시지
- `critical`: 치명적 오류

**파일 로거:**

```yaml
logger:
  - type: file
    path: ./logs/run.log           # 로그 파일 경로
    level: info
```

디렉토리는 자동으로 생성됩니다.

**여러 로거 사용:**

```yaml
logger:
  - type: console
    level: warning                 # 콘솔에는 경고만

  - type: file
    path: ./logs/all.log
    level: debug                   # 파일에는 모든 로그

  - type: file
    path: ./logs/errors.log
    level: error                   # 오류 전용 로그
```

### 14.5.2 Docker 컨테이너 로그

**실시간 로그 확인:**

```bash
# 포그라운드 실행 시 자동 스트리밍
model-compose up

# 백그라운드 실행 후 로그 확인
docker logs -f <container-name>
```

**로그 저장:**

```yaml
controller:
  runtime:
    type: docker
    container_name: model-compose-prod
    logging:
      driver: json-file
      options:
        max-size: "10m"            # 파일당 최대 크기
        max-file: "5"              # 최대 파일 개수
```

로그 위치: `/var/lib/docker/containers/<container-id>/<container-id>-json.log`

**로그 드라이버 옵션:**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: syslog               # json-file, syslog, journald, gelf, fluentd 등
      options:
        syslog-address: "tcp://192.168.0.42:514"
        tag: "model-compose"
```

### 14.5.3 워크플로우 실행 로깅

**로거 컴포넌트로 로깅:**

```yaml
components:
  - id: logger
    type: logger
    level: info

  - id: api-client
    type: http-client
    base_url: https://api.example.com

workflows:
  - id: process-with-logging
    jobs:
      - id: log-start
        component: logger
        input:
          message: "워크플로우 시작: ${context.run_id}"

      - id: api-call
        component: api-client
        input: ${input}

      - id: log-result
        component: logger
        input:
          message: "결과: ${output}"

      - id: log-end
        component: logger
        input:
          message: "워크플로우 종료"
```

### 14.5.4 메트릭 수집

**실행 시간 추적:**

```yaml
workflows:
  - id: timed-workflow
    jobs:
      - id: start-time
        component: shell
        command: echo $(date +%s%3N)       # 밀리초 타임스탬프
        output: ${stdout.trim()}

      - id: process
        component: api-client
        input: ${input}

      - id: end-time
        component: shell
        command: echo $(date +%s%3N)
        output: ${stdout.trim()}

      - id: log-duration
        component: logger
        input:
          message: "실행 시간: ${output.end-time - output.start-time}ms"
```

**성능 메트릭 로깅:**

```yaml
workflows:
  - id: metrics-workflow
    jobs:
      - id: api-call
        component: api-client
        input: ${input}

      - id: log-metrics
        component: logger
        input:
          run_id: ${context.run_id}
          status: ${output.status}
          response_time: ${output.response_time_ms}
          tokens_used: ${output.usage.total_tokens}
```

### 14.5.5 외부 모니터링 시스템

**Prometheus 연동 예제:**

```yaml
components:
  - id: prometheus-push
    type: http-client
    base_url: http://prometheus-pushgateway:9091
    path: /metrics/job/model-compose
    method: POST
    headers:
      Content-Type: text/plain

workflows:
  - id: monitored-workflow
    jobs:
      - id: process
        component: my-component
        input: ${input}

      - id: push-metrics
        component: prometheus-push
        input:
          body: |
            workflow_execution_duration_seconds ${output.duration}
            workflow_execution_total 1
```

**로그 집계 시스템 (ELK Stack):**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: gelf                 # Graylog Extended Log Format
      options:
        gelf-address: "udp://logstash:12201"
        tag: "model-compose"
        labels: "environment,service"
    labels:
      environment: production
      service: model-compose
```

---

## 14.6 Best Practices

### 환경별 배포 전략

**로컬 개발 환경:**
- 네이티브 런타임으로 빠른 반복 개발
- `.env` 파일로 환경 변수 관리
- 콘솔 로거 사용 (`level: debug`)

**스테이징/테스트 환경:**
- Docker 런타임으로 프로덕션 환경 모방
- 파일 로거로 로그 보존
- 리소스 제한 및 헬스 체크 검증

**프로덕션 환경:**
- Docker 런타임 필수 사용
- `restart: unless-stopped` 설정으로 자동 복구
- 리소스 제한 (`mem_limit`, `cpus`) 적용
- 헬스 체크 구성 및 모니터링
- 볼륨으로 데이터 영속성 보장
- 환경 변수로 시크릿 관리
- 로그 집계 시스템 연동
- 동시성 제어 설정

### 성능 최적화

1. **동시성 튜닝**: 워크로드에 맞는 `max_concurrent_count` 설정
2. **리소스 할당**: CPU/메모리 사용량 모니터링 후 적절한 제한 설정
3. **로그 레벨**: 프로덕션에서는 `info` 이상 (debug 로그 제외)
4. **로그 로테이션**: Docker 로깅 옵션으로 디스크 사용량 제어
5. **볼륨 마운트**: 성능이 중요한 데이터는 tmpfs 사용 고려

### 보안 강화

1. **최소 권한 원칙**: 컨테이너 사용자를 비루트로 설정
2. **시크릿 분리**: 환경 변수 사용, 코드 저장소에 시크릿 커밋 금지
3. **네트워크 격리**: 필요한 경우 전용 네트워크 사용
4. **정기 업데이트**: 베이스 이미지 및 의존성 정기 업데이트
5. **보안 스캔**: 이미지 빌드 시 취약점 스캔 도구 사용

### 안정성 향상

1. **헬스 체크**: 항상 헬스 체크 구성
2. **재시작 정책**: 프로덕션에서는 `always` 또는 `unless-stopped` 사용
3. **그레이스풀 셧다운**: 신호 처리로 정상 종료 보장
4. **백업**: 중요 데이터는 정기 백업
5. **모니터링**: 실시간 메트릭 및 알람 설정

---

## 다음 단계

실습해보세요:
- 프로덕션 환경에 컨트롤러 배포
- Docker Compose로 멀티 컨테이너 구성
- Kubernetes 클러스터 배포
- CI/CD 파이프라인 통합
- 모니터링 대시보드 구축

---

**다음 장**: [15. 실전 예제](./15-practical-examples.md)
