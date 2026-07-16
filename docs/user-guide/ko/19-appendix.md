# 19. 부록

이 장에서는 model-compose의 고급 참조 자료를 제공합니다.

---

## 19.1 설정 파일 전체 스키마

### 19.1.1 최상위 구조

```yaml
controller:        # 필수: 컨트롤러 및 어댑터 설정
  adapter:         # 여러 어댑터 타입은 `adapters:`
    type: http-server | mcp-server | queue-subscriber
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
action:            # actions: [ ... ] 대신 (컴포넌트 내에서)
```

### 19.1.2 컨트롤러 스키마

**HTTP 서버**:
```yaml
controller:
  adapter:
    type: http-server
    host: 127.0.0.1                      # 기본값: 127.0.0.1
    port: 8080                           # 기본값: 8080
    base_path: /api                      # 기본값: null
    origins: "*"                         # 기본값: "*" (CORS)
    websocket:                           # 기본값: 활성화
      path: /ws                          # 기본값: /ws
      ping_interval: 30s
      ping_timeout: 10s
  max_concurrent_count: 10             # 기본값: 0 (무제한)
  shutdown_timeout: 30s
  threaded: false

  webui:                               # 선택: Web UI 설정
    driver: gradio | static | dynamic
    host: 127.0.0.1
    port: 8081
    static_dir: webui                  # static 드라이버용, 기본값: "webui"

  runtime:                             # 선택: 대체 런타임
    type: docker
    # ... Docker 옵션
```

**MCP 서버**:
```yaml
controller:
  adapter:
    type: mcp-server
    host: 127.0.0.1                      # 기본값: 127.0.0.1
    port: 8080                           # 기본값: 8080
    base_path: /mcp                      # 기본값: null

  webui:                               # 선택
    driver: gradio
    port: 8081
```

### 19.1.3 컴포넌트 스키마

**모델 컴포넌트**:
```yaml
components:
  - id: model-id
    type: model
    task: text-generation | chat-completion | text-to-text | text-embedding | text-classification | image-to-text | image-text-to-text | text-to-speech | speech-to-text | voice-activity-detection | image-generation | image-upscale | face-detection | pose-detection | face-embedding | music-generation
    driver: huggingface | unsloth | vllm | llamacpp | custom  # 기본값: huggingface
    model: model-name-or-path          # 또는 `{ provider, repository/path, ... }` 객체

    # 모델 설정 (컴포넌트 레벨)
    device: cuda | cpu | mps           # 기본값: cpu
    device_mode: auto | single         # 기본값: auto
    precision: auto | float32 | float16 | bfloat16   # 선택
    quantization: int8 | int4 | fp4 | nf4            # 선택; 또는 전체 ModelQuantizationConfig 객체
    low_cpu_mem_usage: false           # 기본값: false
    preload: true                      # 기본값: true
    on_demand: false                   # 기본값: false; 또는 `{ priority, idle_timeout }`
    fast_tokenizer: true               # 언어 모델 태스크 전용, 기본값: true
    max_seq_length: 2048               # 언어 모델 태스크 전용, 기본값: 2048

    # LoRA / PEFT 어댑터
    peft_adapters:
      - type: lora
        name: adapter-name
        model: path/to/adapter
        weight: 1.0

    # 단일 액션 (입력/출력 매핑 및 추론 옵션)
    action:
      # 입력 (태스크별 상이)
      text: ${input.text as text}
      messages: [ ... ]
      image: ${input.image as image}
      batch_size: 1                    # 액션 레벨
      streaming: false                 # 액션 레벨 (text-generation / chat-completion / text-to-text / image-to-text 만 해당)
      params:
        max_output_length: 100
        temperature: 0.7
        top_p: 0.9
        do_sample: true
```

**HTTP 클라이언트**:
```yaml
components:
  - id: http-client-id
    type: http-client

    # 컴포넌트 레벨
    base_url: https://api.example.com
    headers: { ... }
    rate_limit: "10/s"                 # 선택; 축약형 또는 전체 RateLimitConfig

    # 단일 액션
    action:
      method: GET | POST | PUT | DELETE | PATCH
      path: /resource                  # base_url과 결합됨
      headers: { ... }
      params: { ... }
      body: { ... }
      stream_format: json | text

    # 또는 다중 액션
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

    # 서버 수명 주기 스크립트 (install/build/clean/start 축약형은 컴포넌트 루트에서도 사용 가능)
    manage:
      scripts:
        install:
          - [ pip, install, vllm ]
        start:
          - vllm
          - serve
          - model-name
          - --port
          - "8000"
      working_dir: .
      env: { }

    # 서버 설정
    port: 8000
    base_path: /                 # 선택
    headers: { }                 # 각 액션에 기본 병합

    # 서버 시작 후 호출할 액션
    action:
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

**키-값 스토어**:
```yaml
components:
  - id: kv-store-id
    type: key-value-store
    driver: redis

    # 연결 설정 (url 또는 host/port)
    url: redis://localhost:6379/0
    # host: localhost
    # port: 6379
    # password: ${env.REDIS_PASSWORD}
    # database: 0

    # 액션
    actions:
      - id: set
        method: set
        key: "cache:${input.key}"
        value: ${input.value}
        ttl: 3600

      - id: get
        method: get
        key: "cache:${input.key}"
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
    action:
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
    base_dir: .                  # 선택
    env: { }                     # 선택
    action:
      command:
        - echo
        - ${input.message}
```

### 19.1.4 워크플로우 스키마

**기본 구조**:
```yaml
workflows:
  - id: workflow-id
    title: Workflow Title
    description: Workflow description
    default: false                  # 선택
    private: false                  # 선택

    jobs:
      - id: job-id
        component: component-id
        action: action-id           # 선택: 다중 액션 컴포넌트용
        input: { ... }
        output: { ... }
        depends_on: [ other-job ]   # 선택: 의존성
        repeat_count: 1             # 선택: N회 반복

    output: { ... }                 # 선택: 워크플로우 레벨 출력 매핑
```

**작업 타입**:
```yaml
# 공통 필드 (모든 작업 타입에서 사용 가능)
# - id, name, depends_on, max_run_count
# - interrupt: { before, after }     # 각 항목: false | true | { condition, message, metadata }
# - hook: { before, after }          # 각 항목: 단일 훅 또는 { script } 목록

# 1. Component 작업 (기본 - 컴포넌트 실행)
- id: job1
  type: component        # 생략 가능 (기본값)
  component: component-id
  action: action-id      # 선택: 다중 액션 컴포넌트용
  input: ${input}
  output: ${output}
  repeat_count: 1
  max_run_count: 5
  interrupt:
    before: false        # true 또는 { condition, message, metadata }
    after: false
  hook:
    before:              # 단일 훅 또는 훅 목록
      script: |
        async def hook(input, **kwargs):
            return input
    after:
      - script: |
          async def hook(input, output, **kwargs):
              return output

# 2. If 작업 (조건부 분기)
- id: job2
  type: if
  input: ${input.status}
  operator: eq
  value: active
  if_true: job-success
  if_false: job-fail
  # 또는 여러 조건 사용 시:
  #   conditions:
  #     - { operator: eq, value: a, if_true: job-a }
  #     - { operator: eq, value: b, if_true: job-b }
  #   otherwise: job-default

# 3. Switch 작업 (다중 분기)
- id: job3
  type: switch
  input: ${input.category}
  cases:
    - { value: image, then: process-image }
    - { value: video, then: process-video }
  otherwise: process-unknown

# 4. Random router (균등 또는 가중치)
- id: job4
  type: random-router
  mode: weighted           # 또는 "uniform"
  routings:
    - { to: variant-a, weight: 0.7 }
    - { to: variant-b, weight: 0.3 }

# 5. Delay 작업 (지연)
- id: job5
  type: delay
  mode: time-interval      # 또는 "specific-time"
  duration: 5s             # time-interval 모드
  # specific-time 모드:
  #   time: "2026-01-01T09:00:00"
  #   timezone: Asia/Seoul

# 6. For-each 작업 (반복)
- id: job6
  type: for-each
  input: ${input.items}
  batch_size: 4
  streaming: false
  do:
    component: item-processor
    action: transform
    input: { item: ${item} }
    output: ${result}

# 7. Filter 작업 (출력 재구성)
- id: job7
  type: filter
  output:
    active: ${jobs.load.output.records}
```

If 작업에서 지원되는 연산자: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not-in`, `starts-with`, `ends-with`, `match`.

### 19.1.5 리스너 스키마

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

### 19.1.6 게이트웨이 스키마

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

### 19.1.7 로거 스키마

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

### 19.1.8 트레이서 스키마

**Langfuse 트레이서**:
```yaml
tracers:
  - driver: langfuse
    public_key: ${env.LANGFUSE_PUBLIC_KEY}
    secret_key: ${env.LANGFUSE_SECRET_KEY}
    base_url: https://cloud.langfuse.com   # 선택 사항
    timeout: 30                             # 선택 사항 (초)
    capture:
      input: true                          # 트레이스에 입력 포함
      output: true                         # 트레이스에 출력 포함
      redact_keys:                         # 마스킹할 키
        - Authorization
        - api_key
      max_payload_bytes: 1048576           # 최대 페이로드 크기 (바이트)
```

### 19.1.9 런타임 스키마

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

**이전 장**: [18. 문제 해결](./18-troubleshooting.md)
