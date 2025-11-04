# 17. 부록

이 장에서는 model-compose의 고급 참조 자료를 제공합니다.

---

## 17.1 설정 파일 전체 스키마

### 17.1.1 최상위 구조

```yaml
controller:        # 필수: HTTP 또는 MCP 서버 설정
  type: http-server | mcp-server
  # ... 상세 설정

components:        # 선택: 재사용 가능한 컴포넌트 목록
  - id: component-id
    type: model | http-client | http-server | ...
    # ... 컴포넌트별 설정

workflows:         # 선택: 워크플로우 정의
  - id: workflow-id
    title: Workflow Title
    # ... 워크플로우 설정

listeners:         # 선택: 비동기 콜백 리스너
  - id: listener-id
    type: http-callback
    # ... 리스너 설정

gateways:          # 선택: HTTP 터널 게이트웨이
  - type: ngrok | cloudflare | ssh-tunnel
    # ... 게이트웨이 설정

loggers:           # 선택: 로거 설정
  - type: console | file
    # ... 로거 설정
```

**단축 문법** (단일 항목):
```yaml
component:         # components: [ ... ] 대신
workflow:          # workflows: [ ... ] 대신
listener:          # listeners: [ ... ] 대신
gateway:           # gateways: [ ... ] 대신
logger:            # loggers: [ ... ] 대신
```

### 17.1.2 컨트롤러 스키마

**HTTP 서버**:
```yaml
controller:
  type: http-server
  port: 8080                           # 기본값: 8080
  host: 0.0.0.0                        # 기본값: 127.0.0.1
  base_path: /api                      # 기본값: /
  max_concurrency: 10                  # 기본값: 무제한

  webui:                               # 선택: Web UI 설정
    driver: gradio | static
    port: 8081
    root: ./static                     # static 드라이버용

  runtime:                             # 선택: Docker 런타임
    type: docker
    image: python:3.11
    # ... Docker 옵션
```

**MCP 서버**:
```yaml
controller:
  type: mcp-server
  port: 8080                           # 선택
  base_path: /mcp                      # 기본값: /

  webui:                               # 선택
    driver: gradio
    port: 8081
```

### 17.1.3 컴포넌트 스키마

**모델 컴포넌트**:
```yaml
components:
  - id: model-id
    type: model
    task: text-generation | chat-completion | translation | ...
    model: model-name-or-path

    # 입력 (태스크별 상이)
    text: ${input.text as text}
    messages: [ ... ]
    image: ${input.image as image}

    # 모델 설정
    device: cuda | cpu | mps
    dtype: float32 | float16 | bfloat16 | int8 | int4
    batch_size: 1
    streaming: false

    # 파라미터
    params:
      max_output_length: 100
      temperature: 0.7
      top_p: 0.9
      do_sample: true

    # LoRA 어댑터
    peft_adapters:
      - type: lora
        name: adapter-name
        model: path/to/adapter
        weight: 1.0
```

**HTTP 클라이언트**:
```yaml
components:
  - id: http-client-id
    type: http-client

    # 엔드포인트
    base_url: https://api.example.com   # 또는
    endpoint: https://api.example.com/v1/resource

    # HTTP 설정
    method: GET | POST | PUT | DELETE | PATCH
    path: /resource
    headers: { ... }
    params: { ... }
    body: { ... }

    # 스트리밍
    stream_format: json | text

    # 고급 설정
    timeout: 30
    max_retries: 3
    retry_delay: 1

    # 다중 액션
    actions:
      - id: action-id
        path: /action-path
        method: POST
        # ...
```

**HTTP 서버** (관리형):
```yaml
components:
  - id: http-server-id
    type: http-server

    # 서버 시작 명령
    start:
      - vllm
      - serve
      - model-name
      - --port
      - "8000"

    # 서버 설정
    port: 8000
    healthcheck:
      path: /health
      interval: 5s
      timeout: 10s
      retries: 3

    # HTTP 클라이언트 설정 (서버 시작 후)
    method: POST
    path: /v1/completions
    body: { ... }
    stream_format: json
```

**벡터 스토어**:
```yaml
components:
  - id: vector-store-id
    type: vector-store
    driver: chroma | milvus | qdrant | faiss

    # 드라이버별 설정
    host: localhost              # milvus, qdrant
    port: 19530                  # milvus, qdrant
    path: ./chroma_db            # chroma

    # 액션
    actions:
      - id: insert
        collection: collection-name
        method: insert
        vector: ${input.vector}
        metadata: ${input.metadata}

      - id: search
        collection: collection-name
        method: search
        query: ${input.vector}
        top_k: 5
        output_fields: [ field1, field2 ]
```

**데이터셋**:
```yaml
components:
  - id: dataset-id
    type: datasets
    provider: huggingface | local

    # HuggingFace
    dataset: dataset-name
    split: train
    subset: subset-name

    # 로컬
    path: ./data
    format: json | csv | parquet

    # 조작
    select: [ column1, column2 ]
    filter: ${condition}
    map: ${transformation}
    shuffle: true
    sample: 100
```

**텍스트 분할**:
```yaml
components:
  - id: text-splitter-id
    type: text-splitter
    text: ${input.text}
    chunk_size: 1000
    chunk_overlap: 200
    separator: "\n\n"
```

**쉘 명령**:
```yaml
components:
  - id: shell-id
    type: shell
    command: echo
    args:
      - ${input.message}
```

### 17.1.4 워크플로우 스키마

**기본 구조**:
```yaml
workflows:
  - id: workflow-id
    title: Workflow Title
    description: Workflow description

    # 단일 컴포넌트
    component: component-id
    input: ${input}
    output: ${output}

    # 또는 다중 작업
    jobs:
      - id: job-id
        component: component-id
        action: action-id        # 선택: 다중 액션 컴포넌트용
        input: { ... }
        output: { ... }
        depends_on: [ job-id ]   # 선택: 의존성
        condition: ${expression} # 선택: 조건부 실행
```

**작업 타입**:
```yaml
# 1. Action 작업 (기본 - 컴포넌트 실행)
- id: job1
  type: action           # 생략 가능 (기본값)
  component: component-id
  action: action-id      # 선택: 다중 액션 컴포넌트용
  input: ${input}
  output: ${output}

# 2. If 작업 (조건부 분기)
- id: job2
  type: if
  operator: eq
  input: ${input.status}
  value: "active"
  if_true: job-success
  if_false: job-fail

# 3. Delay 작업 (지연)
- id: job3
  type: delay
  duration: 5s           # 5초 대기
```

### 17.1.5 리스너 스키마

```yaml
listeners:
  - id: listener-id
    type: http-callback

    # 웹훅 엔드포인트
    path: /webhook
    method: POST

    # 워크플로우 트리거
    workflow: workflow-id

    # 콜백 설정
    callback:
      url: https://api.example.com/callback
      method: POST
      headers: { ... }
      body: { ... }

    # 벌크 처리
    bulk:
      enabled: true
      size: 10
      interval: 60
```

### 17.1.6 게이트웨이 스키마

**ngrok**:
```yaml
gateways:
  - type: ngrok
    port: 8080
    authtoken: ${env.NGROK_AUTHTOKEN}
    region: us | eu | ap | au | sa | jp | in
    domain: custom-domain.ngrok.io
```

**Cloudflare**:
```yaml
gateways:
  - type: cloudflare
    port: 8080
    tunnel_id: ${env.CLOUDFLARE_TUNNEL_ID}
    credentials_file: ~/.cloudflared/credentials.json
```

**SSH 터널**:
```yaml
gateways:
  - type: ssh-tunnel
    port: 8080
    connection:
      host: remote-server.com
      port: 22
      auth:
        type: keyfile
        username: user
        keyfile: ~/.ssh/id_rsa
      # 또는
      auth:
        type: password
        username: user
        password: ${env.SSH_PASSWORD}
```

### 17.1.7 로거 스키마

**콘솔 로거**:
```yaml
loggers:
  - type: console
    level: DEBUG | INFO | WARNING | ERROR
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

**파일 로거**:
```yaml
loggers:
  - type: file
    level: INFO
    path: ./logs/app.log
    format: "%(asctime)s - %(levelname)s - %(message)s"
    rotation:
      max_bytes: 10485760        # 10MB
      backup_count: 5
```

### 17.1.8 런타임 스키마

**Docker 런타임**:
```yaml
controller:
  runtime:
    type: docker

    # 이미지
    image: python:3.11
    build:                       # 선택: 커스텀 빌드
      context: .
      dockerfile: Dockerfile
      args:
        ARG_NAME: value

    # 리소스
    mem_limit: 4g
    cpus: "2.0"
    gpus: all | "device=0,1"
    shm_size: 1g

    # 볼륨
    volumes:
      - ./data:/data
      - model-cache:/cache

    # 환경 변수
    environment:
      VAR_NAME: value
      API_KEY: ${env.API_KEY}

    # 네트워크
    network_mode: bridge | host
    ports:
      - "8080:8080"

    # 정책
    restart: no | always | on-failure | unless-stopped

    # 헬스체크
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:8080/health" ]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 다음 단계

실습해보세요:
- 전체 스키마 참조하여 고급 설정 구성
- 프로젝트에 맞는 컴포넌트 및 워크플로우 설계

---

**이전 장**: [15. 실전 예제](./15-practical-examples.md)
