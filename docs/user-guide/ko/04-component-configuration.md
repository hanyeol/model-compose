# 4장: 컴포넌트 구성

이 장에서는 model-compose의 다양한 컴포넌트 타입과 정의 방법, 입력/출력 매핑, 재사용 패턴을 다룹니다.

---

## 4.1 컴포넌트 타입

model-compose는 다양한 작업을 수행할 수 있는 여러 컴포넌트 타입을 제공합니다.

### 사용 가능한 컴포넌트 타입

| 타입 | 용도 | 주요 사용 사례 |
|------|------|---------------|
| `agent` | 자율 AI 에이전트 | 워크플로우를 도구로 활용하는 ReAct 루프 |
| `http-client` | 외부 API 호출 | OpenAI, ElevenLabs 등 REST API 통합 |
| `http-server` | HTTP 서비스 제공 | 커스텀 HTTP API 엔드포인트 구현 |
| `websocket-client` | WebSocket 클라이언트 | 원격 WebSocket 서버로 실시간 스트리밍 |
| `websocket-server` | WebSocket 서비스 제공 | 실시간 앱용 WebSocket 엔드포인트 호스팅 |
| `mcp-server` | MCP 서비스 제공 | Model Context Protocol 서버 구현 |
| `mcp-client` | MCP 클라이언트 | MCP 서버와 통신 |
| `model` | 로컬 AI 모델 실행 | 텍스트 생성, 이미지 분석 등 로컬 모델 추론 |
| `model-memory` | 모델 대화 메모리 | 세션 기반 대화 히스토리 저장/윈도우/요약 |
| `model-tokenizer` | 모델 토크나이저 | 모델 토크나이저를 사용한 토큰 인코딩, 디코딩, 카운팅 |
| `model-trainer` | 모델 훈련 | 파인튜닝, LoRA 훈련 |
| `datasets` | 데이터셋 로드 | 훈련/평가 데이터셋 로드 및 처리 |
| `vector-store` | 벡터 DB 연동 | Chroma, Milvus 등 RAG 시스템 |
| `graph-store` | 그래프 DB 연동 | Neo4j, ArangoDB를 사용한 지식 그래프, 소셜 네트워크 |
| `search-engine` | 풀텍스트 검색 | SQLite FTS5 기반 BM25 키워드 검색 |
| `key-value-store` | 키-값 저장소 | Redis를 사용한 캐싱, 세션 관리 |
| `file-store` | 파일/객체 저장소 | 로컬 파일시스템, AWS S3, GCP Storage, Azure Blob 스트리밍 I/O |
| `workflow` | 워크플로우 호출 | 다른 워크플로우를 서브루틴으로 실행 |
| `shell` | 셸 명령 실행 | 스크립트 실행, 시스템 명령 |
| `text-splitter` | 텍스트 분할 | 문서를 청크로 분할 |
| `image-processor` | 이미지 처리 | 이미지 변환, 리사이즈, PNG 압축 등 |
| `video-scene-detector` | 비디오 장면 감지 | PySceneDetect, FFmpeg, TransNetV2를 사용한 장면 전환 감지 |
| `video-converter` | 비디오 변환 | 비디오 트랜스코딩/포맷 변환 (컨테이너, 코덱, 해상도 등) |
| `video-frame-extractor` | 비디오 프레임 추출 | 비디오를 PIL 이미지 프레임으로 디코딩하며 샘플링과 시간 범위 지원 |
| `audio-extractor` | 오디오 추출 | 비디오/미디어에서 오디오 스트림 추출 |
| `audio-converter` | 오디오 변환 | 오디오 트랜스코딩/포맷 변환 (코덱, 샘플레이트, 채널 등) |
| `audio-feature-extractor` | 오디오 특징 추출 | 시각화용 프레임별 스펙트럼 밴드 / 파형 포인트 |
| `web-scraper` | 웹 스크래핑 | CSS/XPath를 사용한 웹 데이터 추출 |
| `web-browser` | 브라우저 자동화 | Chrome DevTools Protocol을 통한 브라우저 제어 |

### 컴포넌트 선택 가이드

**외부 API 통합**
- OpenAI, Anthropic 등 → `http-client`
- 커스텀 REST API → `http-client`

**로컬 AI 모델**
- 로컬 추론 → `model`
- 비전 태스크 (로컬 이미지의 얼굴/포즈 감지) → `model` + `task: face-detection` 또는 `task: pose-detection` ([Model Component 레퍼런스](../../reference/compose/components/model.md) 참고)
- vLLM, Ollama 등 백엔드 사용 → `http-server`
- 훈련 → `model-trainer`

**데이터 처리**
- 대화 메모리 → `model-memory`
- 벡터 저장 → `vector-store`
- 그래프 저장 → `graph-store`
- 풀텍스트 검색 → `search-engine`
- 키-값 저장 → `key-value-store`
- 텍스트 분할 → `text-splitter`
- 이미지 처리 → `image-processor`
- 비디오 장면 감지 → `video-scene-detector`
- 비디오 프레임 추출 → `video-frame-extractor`
- 오디오 특징 추출 (시각화용 스펙트럼 / 파형) → `audio-feature-extractor`
- 웹 스크래핑 → `web-scraper`

**브라우저 자동화**
- 브라우저 제어 (CDP) → `web-browser`

**AI 에이전트**
- 도구를 활용하는 자율 에이전트 → `agent`

**워크플로우 조합**
- 서브 워크플로우 → `workflow`
- 시스템 작업 → `shell`

---

## 4.2 컴포넌트 정의 방법

### 기본 구조

모든 컴포넌트는 다음 기본 구조를 따릅니다:

```yaml
components:
  - id: unique-component-id
    type: component-type
    # 타입별 설정...
    output:
      # 출력 매핑...
```

### 필수 속성

- `id`: 컴포넌트의 고유 식별자
- `type`: 컴포넌트 타입

### 선택 속성

- `output`: 출력 데이터 매핑
- `actions`: 여러 액션 정의 (다중 액션 컴포넌트)

### 단일 액션 vs 다중 액션 컴포넌트

컴포넌트는 단일 액션 또는 다중 액션으로 정의할 수 있습니다.

#### 단일 액션 컴포넌트

하나의 작업만 수행하는 컴포넌트는 액션 관련 필드를 `action:` 아래에 감쌉니다:

```yaml
components:
  - id: send-email
    type: http-client
    action:
      endpoint: https://api.email.com/send
      method: POST
      headers:
        Authorization: Bearer ${env.EMAIL_API_KEY}
      body:
        to: ${input.to}
        subject: ${input.subject}
        body: ${input.body}
      output: ${response}
```

사용:
```yaml
workflow:
  jobs:
    - component: send-email
      input:
        to: "user@example.com"
        subject: "Welcome"
        body: "Hello!"
```

#### 다중 액션 컴포넌트

하나의 컴포넌트에 여러 작업을 정의:

```yaml
components:
  - id: email-service
    type: http-client
    base_url: https://api.email.com
    headers:
      Authorization: Bearer ${env.EMAIL_API_KEY}
      Content-Type: application/json
    actions:
      - id: send
        path: /send
        method: POST
        body:
          to: ${input.to}
          subject: ${input.subject}
          body: ${input.body}
        output: ${response}

      - id: get-status
        path: /status/${input.message_id}
        method: GET
        output: ${response.status}

      - id: list-templates
        path: /templates
        method: GET
        output: ${response.templates}
```

사용:
```yaml
workflow:
  jobs:
    - id: send
      component: email-service
      action: send
      input:
        to: "user@example.com"
        subject: "Welcome"
        body: "Hello!"
      output:
        message_id: ${output.id}

    - id: check
      component: email-service
      action: get-status
      input:
        message_id: ${jobs.send.output.message_id}
```

#### 언제 다중 액션을 사용할까?

**다중 액션 사용이 적합한 경우:**
- 동일한 API 서비스의 여러 엔드포인트를 사용
- 공통 인증/헤더를 공유
- 관련된 작업들을 논리적으로 그룹화

**단일 액션 사용이 적합한 경우:**
- 단순하고 독립적인 작업
- 재사용이 제한적인 특정 작업
- 빠른 프로토타이핑

---

## 4.3 입력/출력 매핑

### 입력 매핑

컴포넌트에 데이터를 전달하는 방법:

#### 방법 1: 직접 매핑

```yaml
components:
  - id: translator
    type: http-client
    action:
      endpoint: https://api.translate.com/v1/translate
      body:
        text: ${input.text}
        target_lang: ${input.language}
```

워크플로우에서 사용:
```yaml
workflow:
  jobs:
    - component: translator
      input:
        text: "Hello"
        language: "ko"
```

#### 방법 2: 전체 입력 전달

```yaml
components:
  - id: processor
    type: http-client
    action:
      endpoint: https://api.example.com/process
      body: ${input}  # 전체 입력을 그대로 전달
```

### 출력 매핑

컴포넌트의 결과를 추출하는 방법:

#### 기본 출력

```yaml
components:
  - id: chatgpt
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      body:
        model: gpt-4o
        messages: ${input.messages}
      output:
        content: ${response.choices[0].message.content}
        tokens: ${response.usage.total_tokens}
```

워크플로우에서 사용:
```yaml
workflow:
  jobs:
    - component: chatgpt
      output:
        answer: ${output.content}  # 컴포넌트 출력의 content 필드
        usage: ${output.tokens}     # 컴포넌트 출력의 tokens 필드
```

#### 전체 응답 출력

```yaml
components:
  - id: api-call
    type: http-client
    action:
      endpoint: https://api.example.com/data
      output: ${response}  # 전체 응답
```

#### 타입 변환과 함께

```yaml
components:
  - id: image-gen
    type: http-client
    action:
      endpoint: https://api.images.com/generate
      output: ${response.image as base64}
```

### 입출력 흐름 예제

```yaml
components:
  - id: step1
    type: http-client
    action:
      endpoint: https://api1.com/process
      body:
        data: ${input.raw_data}
      output:
        processed: ${response.result}

  - id: step2
    type: http-client
    action:
      endpoint: https://api2.com/analyze
      body:
        data: ${input.processed_data}
      output:
        analysis: ${response.insights}

workflow:
  jobs:
    - id: process
      component: step1
      input:
        raw_data: ${input.data}
      output:
        result: ${output.processed}

    - id: analyze
      component: step2
      input:
        processed_data: ${jobs.process.output.result}
      output:
        final: ${output.analysis}
```

---

## 4.4 재사용 패턴

### 패턴 1: 모델별 컴포넌트 분리

모델이나 서비스별로 컴포넌트를 분리하여 명확한 책임 부여:

```yaml
components:
  # OpenAI GPT-4o 전용
  - id: gpt4o
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages: ${input.messages}
        temperature: ${input.temperature | 0.7}
      output:
        content: ${response.choices[0].message.content}
        tokens: ${response.usage.total_tokens}

  # Anthropic Claude 전용
  - id: claude
    type: http-client
    action:
      endpoint: https://api.anthropic.com/v1/messages
      headers:
        x-api-key: ${env.ANTHROPIC_API_KEY}
        anthropic-version: "2023-06-01"
        Content-Type: application/json
      body:
        model: claude-3-5-sonnet-20241022
        messages: ${input.messages}
        max_tokens: ${input.max_tokens | 1024}
      output:
        content: ${response.content[0].text}

  # 음성 합성 전용
  - id: elevenlabs-tts
    type: http-client
    action:
      endpoint: https://api.elevenlabs.io/v1/text-to-speech/${input.voice_id}
      headers:
        xi-api-key: ${env.ELEVENLABS_API_KEY}
        Content-Type: application/json
      body:
        text: ${input.text}
        model_id: eleven_multilingual_v2
      output: ${response as base64}
```

### 패턴 2: 다중 액션 컴포넌트

하나의 서비스에 여러 액션을 정의:

```yaml
components:
  - id: slack
    type: http-client
    base_url: https://slack.com/api
    headers:
      Authorization: Bearer ${env.SLACK_TOKEN}
    actions:
      - id: send-message
        path: /chat.postMessage
        method: POST
        body:
          channel: ${input.channel}
          text: ${input.text}
        output: ${response}

      - id: list-channels
        path: /conversations.list
        method: GET
        output: ${response.channels}

      - id: get-user
        path: /users.info
        method: GET
        params:
          user: ${input.user_id}
        output: ${response.user}
```

사용:
```yaml
workflow:
  jobs:
    - id: send
      component: slack
      action: send-message
      input:
        channel: "#general"
        text: "Hello!"

    - id: list
      component: slack
      action: list-channels
```

### 패턴 3: 컴포넌트 체이닝

작은 컴포넌트를 조합하여 복잡한 로직 구성:

```yaml
components:
  - id: fetch-data
    type: http-client
    action:
      endpoint: https://api.data.com/fetch
      output: ${response.data}

  - id: process-data
    type: shell
    command: [ python, process.py, "${input.data}" ]
    output:
      result: ${result.stdout}

  - id: save-result
    type: http-client
    action:
      endpoint: https://api.storage.com/save
      method: POST
      body:
        data: ${input.data}
      output: ${response}

workflow:
  jobs:
    - id: fetch
      component: fetch-data
      output:
        raw: ${output}

    - id: process
      component: process-data
      input:
        data: ${jobs.fetch.output.raw}
      output:
        processed: ${output.result}

    - id: save
      component: save-result
      input:
        data: ${jobs.process.output.processed}
```

구조 다이어그램:
```mermaid
graph LR
    fetch["Job: fetch"]
    process["Job: process"]
    save["Job: save"]

    fetch -->|raw data| process
    process -->|processed data| save

    fetch -.-> comp1[[Component:<br/>fetch-data]]
    process -.-> comp2[[Component:<br/>process-data]]
    save -.-> comp3[[Component:<br/>save-result]]
```

### 패턴 4: 환경별 컴포넌트

환경에 따라 다른 엔드포인트 사용:

```yaml
# base.yml
components:
  - id: api-client
    type: http-client
    action:
      endpoint: ${env.API_ENDPOINT}/process
      headers:
        Authorization: Bearer ${env.API_KEY}
      body: ${input}
      output: ${response}
```

```bash
# 개발 환경
export API_ENDPOINT=https://dev-api.example.com
export API_KEY=dev-key
model-compose up

# 프로덕션 환경
export API_ENDPOINT=https://api.example.com
export API_KEY=prod-key
model-compose up
```

### 패턴 5: 워크플로우 모듈화

워크플로우를 컴포넌트로 재사용:

```yaml
components:
  - id: preprocess
    type: workflow
    workflow: preprocessing

workflows:
  - id: preprocessing
    jobs:
      - id: clean
        component: data-cleaner
      - id: normalize
        component: normalizer

  - id: main
    jobs:
      - id: preprocess
        component: preprocess
        input: ${input.raw_data}

      - id: analyze
        component: analyzer
        input: ${jobs.preprocess.output}
```

구조 다이어그램:
```mermaid
graph LR
    subgraph main["Workflow: main"]
        direction TB
        job1["Job: preprocess"]
        job2["Job: analyze"]
    end

    subgraph wf2["Workflow: preprocessing"]
        direction TB
        job3["Job: clean"]
        job4["Job: normalize"]
    end

    comp1[[Component:<br/>preprocess]]

    job1 -.->|①| comp1
    comp1 -.->|②| wf2
    job3 -->|③| job4
    wf2 -.->|④| job1
    job1 -->|⑤| job2
```

---

## 4.5 런타임 구성

컴포넌트는 필요에 따라 다른 런타임 환경에서 실행할 수 있습니다. 런타임은 컴포넌트가 어디서 어떻게 실행되는지를 결정합니다.

### 사용 가능한 런타임

model-compose는 네 가지 런타임 타입을 지원합니다:

| 런타임 | 격리 수준 | 속도 | 오버헤드 | 적합한 용도 |
|--------|----------|------|----------|------------|
| `embedded` | 없음 | 빠름 | 최소 | 가벼운 작업, 기본 선택 |
| `process` | 프로세스 수준 | 중간 | 중간 | 무거운 모델, GPU 격리 |
| `virtualenv` | 프로세스 + 의존성 | 중간 (최초 실행은 느림) | 중간 | 컴포넌트별 Python 버전이나 의존성 충돌 분리 |
| `docker` | 컨테이너 수준 | 느림 | 높음 | 프로덕션 배포 |

### Embedded 런타임 (기본값)

컨트롤러와 같은 프로세스에서 컴포넌트를 실행합니다.

```yaml
components:
  - id: text-generator
    type: model
    runtime: embedded  # 또는 생략 가능 (embedded가 기본값)
    task: text-generation
    model: gpt2
```

**사용 시기:**
- 간단한 API 호출
- 가벼운 모델
- 빠른 응답 필요
- 개발 및 테스트

### Process 런타임

별도의 Python 프로세스에서 컴포넌트를 실행하여 메모리를 격리합니다.

```yaml
components:
  - id: heavy-model
    type: model
    runtime: process
    task: text-generation
    model: meta-llama/Llama-3.1-70B
```

**사용 시기:**
- 대형 모델 (70B+ 파라미터)
- 다중 GPU 활용
- 블로킹 작업
- 크래시 격리 필요

**고급 설정:**

```yaml
components:
  - id: model-gpu-0
    type: model
    runtime:
      type: process
      env:
        CUDA_VISIBLE_DEVICES: "0"
      start_timeout: 120
      stop_timeout: 30
    task: image-generation
    model: stabilityai/stable-diffusion-xl-base-1.0
```

**다중 GPU 예시:**

```yaml
components:
  - id: model-gpu-0
    type: model
    runtime:
      type: process
      env:
        CUDA_VISIBLE_DEVICES: "0"
    model: gpt2-large

  - id: model-gpu-1
    type: model
    runtime:
      type: process
      env:
        CUDA_VISIBLE_DEVICES: "1"
    model: stabilityai/stable-diffusion-v1-5

workflows:
  - id: multi-gpu-workflow
    jobs:
      - id: text
        component: model-gpu-0
        action: generate
      - id: image
        component: model-gpu-1
        action: generate
```

### Virtualenv 런타임

격리된 Python 가상환경 안에서 컴포넌트를 실행하여, 컴포넌트마다 독자적인 의존성 스택을 가질 수 있게 합니다. Docker 없이도 의존성 격리가 가능합니다.

```yaml
components:
  - id: training-job
    type: shell
    runtime: virtualenv
    command: [python, train.py]
```

**사용 시기:**
- 특정 Python 버전이 필요한 컴포넌트
- pip 의존성이 호스트나 다른 컴포넌트와 충돌하는 경우
- Docker보다 가볍지만 단순 서브프로세스보다 강한 격리가 필요할 때

**동작 방식:**
- `.runtime/components/<id>/venv` 경로에 venv 생성 (`path`로 변경 가능)
- 호스트의 `mindor` 소스를 복사하고 `requirements.txt`를 venv에 설치
- 워커 서브프로세스는 venv의 Python으로 실행되며, 컨트롤러와는 파이프 기반 채널로 통신
- 최초 실행은 pip install로 인해 느리지만, 호스트 `mindor` 버전이 같으면 다음 실행부터는 재주입을 건너뜀

**고급 설정:**

```yaml
components:
  - id: training-job
    type: shell
    runtime:
      type: virtualenv
      driver: pyenv          # 'python' (현재 인터프리터) 또는 'pyenv' (지정 버전)
      python: "3.12.0"       # driver가 'pyenv'일 때 필수
      path: .venv/training   # 기본값: .runtime/components/<id>/venv
      env:
        CUDA_VISIBLE_DEVICES: "0"
      start_timeout: 300s
      stop_timeout: 30s
    command: [python, train.py]
```

깨끗하게 재설치하려면 `.runtime/components/<id>/` 아래(또는 `path`에 지정한 경로의) venv 디렉토리를 삭제하면 됩니다.

### Docker 런타임

격리된 Docker 컨테이너에서 컴포넌트를 실행합니다.

```yaml
components:
  - id: isolated-model
    type: model
    runtime: docker
    task: text-generation
    model: meta-llama/Llama-3.1-70B
```

**사용 시기:**
- 프로덕션 배포
- 보안이 중요한 워크로드
- 재현 가능한 환경
- 멀티 테넌트 시나리오

### 런타임 선택 가이드

**Embedded** → 대부분의 사용 사례에서 시작
**Process** → 격리 또는 무거운 워크로드가 필요할 때 업그레이드
**Virtualenv** → 컴포넌트마다 고유한 Python 버전이나 pip 의존성이 필요할 때 선택
**Docker** → 프로덕션 및 보안 요구사항에 사용

---

## 4.6 컴포넌트 모범 사례

### 1. 명확한 네이밍

```yaml
# Good
- id: openai-gpt4o-chat
- id: elevenlabs-tts-multilingual
- id: slack-send-message

# Bad
- id: comp1
- id: api
- id: process
```

### 2. 입출력 문서화

```yaml
components:
  - id: translator
    type: http-client
    # Input: { text: string, target_lang: string }
    # Output: { translated: string, detected_lang: string }
    action:
      endpoint: https://api.translate.com/v1/translate
      body:
        text: ${input.text}
        target: ${input.target_lang}
      output:
        translated: ${response.translation}
        detected_lang: ${response.source_language}
```

### 3. 환경 변수 사용

```yaml
# Good - 환경 변수 사용
components:
  - id: api-client
    type: http-client
    action:
      endpoint: ${env.API_ENDPOINT}
      headers:
        Authorization: Bearer ${env.API_KEY}

# Bad - 하드코딩
components:
  - id: api-client
    type: http-client
    action:
      endpoint: https://api.example.com
      headers:
        Authorization: Bearer sk-hardcoded-key
```

---

## 다음 단계

실습해보세요:
- 다양한 컴포넌트 타입 실험하기
- 재사용 가능한 컴포넌트 라이브러리 구축하기
- 복잡한 워크플로우를 작은 컴포넌트로 분해하기

---

**다음 장**: [5. 워크플로우 작성](./05-writing-workflows.md)
