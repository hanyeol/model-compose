# 2장: 핵심 개념

이 장에서는 model-compose의 핵심 개념과 `model-compose.yml` 설정 파일의 구조를 깊이 있게 다룹니다.

---

## 2.1 model-compose.yml 구조

`model-compose.yml`은 model-compose의 중심이 되는 설정 파일입니다. 이 파일은 AI 워크플로우의 모든 측면을 선언적으로 정의합니다.

### 기본 구조

```yaml
controller:
  # 워크플로우를 호스팅하고 실행하는 방법 정의
  type: http-server
  port: 8080

components:
  # 독립적인 실행 모듈 정의
  - id: my-component
    type: http-client

workflows:
  # 워크플로우 파이프라인 정의
  - id: my-workflow
    jobs:
      - component: my-component

listeners:
  # 이벤트 리스너 정의 (선택 사항)

gateways:
  # HTTP 터널링 서비스 정의 (선택 사항)
```

### 주요 섹션

1. **controller** (필수): 워크플로우 실행 환경 설정
2. **components** (선택): 독립적인 실행 모듈 정의
3. **workflows** (선택): 워크플로우 파이프라인 정의
4. **listeners** (선택): 이벤트 리스너 정의
5. **gateways** (선택): 터널링 서비스 정의

### 설정 파일 우선순위

여러 설정 파일을 사용할 수 있으며, 나중에 지정된 파일이 이전 파일을 덮어씁니다:

```bash
model-compose -f base.yml -f override.yml up
```

---

## 2.2 컨트롤러

**컨트롤러**는 워크플로우를 호스팅하고 실행하는 런타임 환경입니다.

### 컨트롤러 타입

#### HTTP Server

워크플로우를 REST API 엔드포인트로 노출합니다.

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio  # 또는 static
    port: 8081
```

**주요 설정:**
- `port`: HTTP 서버 포트 (기본값: 8080)
- `base_path`: API 엔드포인트 기본 경로 (기본값: /api)
- `webui`: 선택적 Web UI 설정
  - `driver`: `gradio` 또는 `static`
  - `port`: Web UI 포트

**API 엔드포인트:**
- `POST /api/workflows/runs` - 워크플로우 실행

#### MCP Server

Model Context Protocol을 통해 워크플로우를 노출합니다.

```yaml
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp
```

**주요 설정:**
- `port`: MCP 서버 포트 (기본값: 8080)
- `base_path`: MCP 엔드포인트 기본 경로

**전송 방식:**
> **참고**: 현재는 SSE (Server-Sent Events) 전송 방식만 지원합니다.
>
> SSE는 서버에서 클라이언트로 단방향 실시간 데이터 스트리밍을 제공하는 HTTP 기반 프로토콜입니다. 이는 다음을 의미합니다:
> - MCP 클라이언트는 HTTP 연결을 통해 서버에 연결해야 합니다
> - stdio 전송 방식(표준 입출력)은 아직 지원되지 않습니다
> - Claude Desktop 등의 MCP 클라이언트에서 사용 시 `@modelcontextprotocol/server-stdio` 어댑터가 필요합니다
>
> **실제 사용 예제**:
> ```json
> // Claude Desktop 설정 (claude_desktop_config.json)
> {
>   "mcpServers": {
>     "my-workflow": {
>       "command": "npx",
>       "args": ["-y", "@modelcontextprotocol/server-stdio", "http://localhost:8080/mcp"]
>     }
>   }
> }
> ```

### 런타임 설정

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: native  # 또는 docker
  max_concurrent_count: 10  # 동시 실행 제한
```

**런타임 타입:**
- `native`: 현재 환경에서 직접 실행
- `docker`: Docker 컨테이너에서 실행

---

## 2.3 컴포넌트

**컴포넌트**는 하나 이상의 액션을 정의하는 재사용 가능한 빌딩 블록입니다. 각 컴포넌트는 특정 서비스나 기능에 대한 액션들을 그룹화합니다.

### 단일 액션 컴포넌트

가장 간단한 형태로, 컴포넌트가 하나의 액션만 정의하는 경우 `action:` (단수형)을 사용합니다:

```yaml
components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output:
        response: ${response.choices[0].message.content}
```

### 다중 액션 컴포넌트

하나의 컴포넌트에 여러 액션을 정의할 수 있습니다:

```yaml
components:
  - id: slack-api
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
```

워크플로우에서는 `component.action` 형식으로 특정 액션을 실행합니다:

```yaml
workflow:
  jobs:
    - id: send
      component: slack-api
      action: send-message
      input:
        channel: "#general"
        text: "Hello!"
```

### 주요 컴포넌트 타입

#### 1. HTTP Client

외부 API를 호출합니다.

```yaml
- id: api-call
  type: http-client
  endpoint: https://api.example.com/v1/endpoint
  method: POST
  headers:
    Authorization: Bearer ${env.API_KEY}
  body:
    data: ${input.data}
  output:
    result: ${response.result}
```

#### 2. Model

로컬 AI 모델을 실행합니다.

```yaml
- id: local-llm
  type: model
  source: huggingface
  model_id: meta-llama/Llama-3.2-3B-Instruct
  task: chat-completion
  device: cuda
  input:
    messages: ${input.messages}
  output:
    response: ${output.content}
```

#### 3. Shell

셸 명령어를 실행합니다.

```yaml
- id: run-script
  type: shell
  command: python process.py
  args:
    - ${input.file_path}
  output:
    result: ${stdout}
```

#### 4. Workflow

다른 워크플로우를 컴포넌트로 호출합니다.

```yaml
- id: sub-workflow
  type: workflow
  workflow_id: preprocessing
  input: ${input}
  output: ${output}
```

### 입력/출력 매핑

컴포넌트는 입력을 받아 출력을 생성합니다:

```yaml
- id: translator
  type: http-client
  endpoint: https://api.translate.com/v1/translate
  body:
    text: ${input.text}      # 입력에서 가져옴
    target: ${input.language} # 입력에서 가져옴
  output:
    translated: ${response.translation}  # 출력으로 추출
```

---

## 2.4 워크플로우

**워크플로우**는 완전한 AI 파이프라인을 정의하는 명명된 작업 시퀀스입니다.

### 기본 워크플로우

```yaml
workflows:
  - id: generate-text
    title: Text Generation
    description: Generate text using GPT-4o
    default: true
    jobs:
      - id: generate
        component: chatgpt
        input:
          prompt: ${input.prompt}
        output:
          result: ${output.response}
```

### 워크플로우 속성

- `id` (필수): 워크플로우의 고유 식별자
- `title`: 사람이 읽을 수 있는 제목
- `description`: 워크플로우 설명
- `default`: 기본 워크플로우로 설정 (true/false)
- `jobs`: 실행할 작업 목록

### 단순화된 워크플로우

단일 워크플로우의 경우 `workflows` (복수형 배열) 대신 `workflow` (단수형 객체)를 사용할 수 있습니다:

```yaml
# 명시적 방식 (workflows)
workflows:
  - id: chat
    title: Chat with GPT
    jobs:
      - component: chatgpt

# 단순화 방식 (workflow)
workflow:
  title: Chat with GPT
  component: chatgpt  # 단일 컴포넌트 워크플로우
```

---

## 2.5 작업

**작업**은 워크플로우 내의 개별 단계입니다.

### 작업 정의

```yaml
jobs:
  - id: step1
    component: chatgpt
    input:
      prompt: ${input.query}
    output:
      answer: ${output.response}
```

### 작업 속성

- `id`: 작업의 고유 식별자 (다른 작업에서 참조할 때 사용)
- `component`: 실행할 컴포넌트 ID
- `input`: 컴포넌트에 전달할 입력 매핑
- `output`: 컴포넌트 출력을 워크플로우 출력으로 매핑
- `depends_on`: 의존성 정의 (이 작업 전에 완료되어야 하는 작업들)

### 작업 간 데이터 전달

```yaml
jobs:
  - id: generate-quote
    component: quote-generator
    input:
      topic: ${input.topic}
    output:
      quote: ${output.text}

  - id: convert-to-speech
    component: text-to-speech
    input:
      text: ${jobs.generate-quote.output.quote}  # 이전 작업의 출력 사용
    output:
      audio: ${output as audio/mp3;base64}
    depends_on: [ generate-quote ]  # 의존성 명시
```

### 작업 실행 순서

기본적으로 작업은 순차적으로 실행됩니다:

```yaml
jobs:
  - id: step1      # 1번째 실행
    component: comp1

  - id: step2      # 2번째 실행 (step1 완료 후)
    component: comp2
    depends_on: [ step1 ]

  - id: step3      # 3번째 실행 (step2 완료 후)
    component: comp3
    depends_on: [ step2 ]
```

병렬 실행도 가능합니다 (의존성이 없는 경우):

```yaml
jobs:
  - id: parallel1
    component: comp1

  - id: parallel2  # parallel1과 동시 실행 가능
    component: comp2

  - id: final      # parallel1, parallel2 모두 완료 후 실행
    component: comp3
    depends_on: [ parallel1, parallel2 ]
```

---

## 2.6 데이터 흐름 및 변수 바인딩

**변수 바인딩**은 `${...}` 구문을 사용하여 워크플로우의 각 단계 간 데이터를 연결합니다. 환경 변수, 사용자 입력, 컴포넌트 출력, 이전 작업 결과를 참조할 수 있으며, 타입 변환, 기본값 설정, 포맷 지정 등의 기능을 제공합니다. 이를 통해 코드 없이 선언적으로 복잡한 데이터 파이프라인을 구성할 수 있습니다.

### 변수 소스

#### 1. 환경 변수

```yaml
${env.VARIABLE_NAME}
```

예시:
```yaml
headers:
  Authorization: Bearer ${env.OPENAI_API_KEY}
```

#### 2. 워크플로우 입력

```yaml
${input.field}
```

예시:
```yaml
body:
  prompt: ${input.user_question}
  temperature: ${input.temperature | 0.7}  # 기본값 0.7
```

#### 3. 컴포넌트 응답

**중요**: 컴포넌트 타입에 따라 응답 변수가 다릅니다.

```yaml
${response.field}   # HTTP 기반 컴포넌트 (http-client, http-server, vector-store 등)
${result.field}     # 로컬 실행 컴포넌트 (model, datasets, text-splitter 등)
${stdout}           # 셸 명령 (shell)
${output}           # 워크플로우 (workflow)
```

예시:
```yaml
# HTTP 클라이언트
output:
  message: ${response.choices[0].message.content}
  tokens: ${response.usage.total_tokens}

# 로컬 모델
output:
  generated_text: ${result}

# 셸 명령
output:
  command_output: ${stdout}
```

> 💡 **컴포넌트별 상세 변수 참조**: 모든 컴포넌트 타입의 변수 소스는 [12.2.2 컴포넌트별 응답 변수 소스](./12-variable-binding.md#1222-컴포넌트별-응답-변수-소스)를 참조하세요.

#### 4. 이전 작업 출력

```yaml
${jobs.job-id.output.field}
```

예시:
```yaml
input:
  text: ${jobs.generate-text.output.content}
  language: ${jobs.detect-language.output.lang}
```

### 변수 변환

#### 타입 캐스팅

```yaml
${input.value as number}     # 숫자로 변환
${input.value as text}       # 텍스트로 변환
${input.value as boolean}    # 불린으로 변환
```

#### Base64 인코딩

```yaml
${output as base64}                      # Base64로 인코딩
```

#### Base64 디코딩

```yaml
${output as audio/mp3;base64}           # Base64로 디코딩해서 오디오로 변환
${output as image/png;base64}           # Base64로 디코딩해서 이미지로 변환
```

#### 기본값 설정

```yaml
${input.temperature | 0.7}               # input.temperature가 없으면 0.7 사용
${env.PORT | 8080}                       # PORT 환경 변수가 없으면 8080 사용
${input.model | gpt-4o}                  # 기본 모델 지정
```

### 전체 데이터 흐름 예제

```yaml
controller:
  type: http-server
  port: 8080

components:
  - id: generate-quote
    type: http-client
    endpoint: https://api.openai.com/v1/chat/completions
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.topic}
    output:
      quote: ${response.choices[0].message.content}

  - id: text-to-speech
    type: http-client
    endpoint: https://api.elevenlabs.io/v1/text-to-speech/${input.voice_id}?output_format=mp3_44100_128
    method: POST
    headers:
      xi-api-key: ${env.ELEVENLABS_API_KEY}
      Content-Type: application/json
    body:
      text: ${input.text}
      model_id: eleven_multilingual_v2
    output: ${response as base64}

workflow:
  title: Quote to Voice
  jobs:
    - id: create-quote
      component: generate-quote
      input:
        topic: ${input.topic}
      output:
        text: ${output.quote}

    - id: create-voice
      component: text-to-speech
      input:
        text: ${jobs.create-quote.output.text}
        voice_id: ${input.voice_id | JBFqnCBsd6RMkjVDRZzb}
      output:
        quote: ${jobs.create-quote.output.text}
        audio: ${output as audio/mp3;base64}
      depends_on: [ create-quote ]
```

**데이터 흐름:**
1. 사용자가 `topic`과 `voice_id` 입력 제공
2. `create-quote` 작업:
   - `${input.topic}`을 GPT-4o에 전달
   - 응답에서 인용구를 `${output.quote}`로 추출
3. `create-voice` 작업:
   - `${jobs.create-quote.output.text}`로 이전 작업의 인용구 가져옴
   - `${input.voice_id}`에서 음성 ID 가져옴 (없으면 기본값 사용)
   - TTS API에 전달하여 오디오 생성
   - 인용구와 오디오를 반환

---

## 2.7 작업과 컴포넌트의 차이

model-compose에서 **컴포넌트**와 **작업(Job)**은 서로 다른 역할을 합니다. 이 차이를 이해하는 것이 효과적인 워크플로우 설계의 핵심입니다.

### 컴포넌트 (Component)

**컴포넌트**는 **재사용 가능한 기능의 정의**입니다.

- **정의**: `components` 섹션에서 선언
- **역할**: 특정 서비스나 기능에 접근하는 방법을 정의 (예: API 호출, 모델 실행)
- **재사용성**: 여러 워크플로우와 여러 작업에서 재사용 가능
- **실행**: 컴포넌트 자체는 실행되지 않으며, 작업을 통해 실행됨
- **분산 배포**: 컴포넌트를 원격 서버에 배포하여 분산 환경 구축 가능

```yaml
components:
  - id: gpt4o
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
```

### 작업 (Job)

**작업**은 **워크플로우 내에서 컴포넌트의 실제 실행 인스턴스**입니다.

- **정의**: `workflow.jobs` 섹션에서 선언
- **역할**: 컴포넌트를 실행하고, 입력 데이터를 전달하며, 출력을 수집
- **실행 순서**: `depends_on`을 통해 다른 작업과의 실행 순서 정의
- **데이터 흐름**: 이전 작업의 결과를 다음 작업의 입력으로 전달

```yaml
workflow:
  jobs:
    - id: generate-text
      component: gpt4o
      input:
        prompt: "Write a haiku"
      output: ${output}

    - id: analyze-sentiment
      component: gpt4o
      input:
        prompt: "Analyze sentiment: ${jobs.generate-text.output}"
      depends_on: [generate-text]
```

### 주요 차이점 요약

| 구분 | 컴포넌트 (Component) | 작업 (Job) |
|------|---------------------|-----------|
| **정의 위치** | `components` 섹션 | `workflow.jobs` 섹션 |
| **역할** | 기능 정의 (템플릿) | 실행 인스턴스 |
| **재사용성** | 여러 워크플로우에서 재사용 | 특정 워크플로우에 종속 |
| **실행** | 직접 실행 불가 | 워크플로우 실행 시 실행됨 |
| **데이터** | 입력/출력 스키마 정의 | 실제 데이터 전달 및 처리 |
| **의존성** | 없음 | `depends_on`으로 작업 간 순서 정의 |

### 실전 예제

```yaml
# 컴포넌트 정의: OpenAI API 호출 방법
components:
  - id: openai-chat
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output:
        text: ${response.choices[0].message.content}

# 워크플로우: 동일한 컴포넌트를 여러 작업에서 재사용
workflows:
  - id: content-pipeline
    jobs:
      # 작업 1: 제목 생성
      - id: generate-title
        component: openai-chat
        input:
          prompt: "Create a catchy title for a blog about AI"
        output: ${output}

      # 작업 2: 본문 생성 (제목을 사용)
      - id: generate-body
        component: openai-chat
        input:
          prompt: "Write a blog post with this title: ${jobs.generate-title.output.text}"
        depends_on: [generate-title]
        output: ${output}

      # 작업 3: 요약 생성 (본문을 사용)
      - id: generate-summary
        component: openai-chat
        input:
          prompt: "Summarize this text: ${jobs.generate-body.output.text}"
        depends_on: [generate-body]
        output: ${output}
```

위 예제에서:
- **컴포넌트** `openai-chat`: OpenAI API 호출 방법을 한 번 정의
- **작업들** (`generate-title`, `generate-body`, `generate-summary`): 동일한 컴포넌트를 서로 다른 프롬프트와 데이터로 세 번 실행

---

## 다음 단계

실습해보세요:
- 여러 작업으로 구성된 워크플로우 만들기
- 다양한 변수 바인딩 패턴 실험하기
- 컴포넌트 재사용 패턴 탐색하기

---

**다음 장**: [3. CLI 사용법](./03-cli-usage.md)
