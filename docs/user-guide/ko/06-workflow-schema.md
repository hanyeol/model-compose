# 6장: 워크플로우 스키마

이 장에서는 model-compose가 각 워크플로우의 입력 및 출력 변수를 자동으로 추론하여 생성하는 워크플로우 스키마에 대해 설명합니다. API를 통해 스키마를 조회하는 방법과 클라이언트 통합, Web UI 렌더링, MCP 도구 매핑에 활용하는 방법을 알아봅니다.

---

## 6.1 워크플로우 스키마란?

**워크플로우 스키마**는 model-compose가 워크플로우 설정으로부터 자동으로 추론하는 메타데이터 구조입니다. 다음을 포함합니다:

- **입력 변수**: 워크플로우 실행 시 필요한 데이터
- **출력 변수**: 워크플로우 완료 시 반환되는 데이터

스키마는 워크플로우의 작업 정의에 있는 변수 바인딩 표현식(`${input.field as type}`)을 분석하여 도출됩니다. 스키마를 직접 작성할 필요 없이 model-compose가 자동으로 생성합니다.

### 스키마의 활용

| 활용처 | 스키마 사용 방식 |
|--------|-----------------|
| Web UI | 입력 폼 자동 생성 (텍스트 필드, 파일 업로드, 드롭다운) |
| MCP 서버 | 워크플로우 입력을 도구 매개변수로 매핑 |
| REST API 클라이언트 | 요청/응답 유효성 검증을 위한 타입 정보 제공 |
| 문서화 | 자체 기술적 API 계약 |

---

## 6.2 스키마 조회 방법

### 단일 워크플로우 스키마

```
GET /workflows/{workflow_id}/schema
```

**예시:**
```bash
curl http://localhost:8080/workflows/my-workflow/schema
```

**응답:**
```json
{
  "workflow_id": "my-workflow",
  "title": "My Workflow",
  "description": "A sample workflow",
  "input": [
    {
      "name": "prompt",
      "type": "text"
    },
    {
      "name": "temperature",
      "type": "number",
      "default": 0.7
    }
  ],
  "output": [
    {
      "name": "result",
      "type": "string"
    }
  ],
  "default": true
}
```

### 전체 워크플로우 스키마

```
GET /workflows?include_schema=true
```

모든 공개 워크플로우의 스키마 객체 배열을 반환합니다.

### 워크플로우 목록 (스키마 미포함)

```
GET /workflows
```

`workflow_id`, `title`, `default` 필드만 포함하는 간략한 목록을 반환합니다.

---

## 6.3 입력 스키마

입력 스키마는 워크플로우 실행 시 제공해야 할 변수를 설명합니다.

### 변수 구조

각 입력 변수는 다음 필드를 가집니다:

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | 변수 이름 (`${input.name}`에서 도출) |
| `type` | string | 변수의 데이터 타입 |
| `subtype` | string? | 부가 타입 한정자 (예: 오디오의 `pcm`) |
| `format` | string? | 전송 포맷 (`base64`, `url`, `path`, `stream`) |
| `default` | any? | 미제공 시 기본값 |

### 지원 타입

**기본 타입:**

| 타입 | 설명 | 사용 예 |
|------|------|---------|
| `string` | 짧은 텍스트 문자열 | 이름, ID, 레이블 |
| `text` | 긴 텍스트 (여러 줄) | 프롬프트, 문서 |
| `integer` | 정수 | 개수, 인덱스 |
| `number` | 부동소수점 숫자 | 온도, 점수 |
| `boolean` | 참/거짓 | 기능 플래그 |
| `list` | 값 배열 | 태그, 키워드 |
| `json` | 임의 JSON 객체 | 복잡한 구조화 데이터 |
| `object[]` | 필드가 투영된 객체 배열 | 테이블 데이터 |

**인코딩 타입:**

| 타입 | 설명 |
|------|------|
| `base64` | Base64 인코딩된 바이너리 데이터 |
| `markdown` | Markdown 포맷 텍스트 |

**미디어 타입:**

| 타입 | 설명 |
|------|------|
| `image` | 이미지 파일 (PNG, JPEG 등) |
| `audio` | 오디오 파일 (WAV, MP3 등) |
| `video` | 비디오 파일 (MP4 등) |
| `file` | 일반 파일 |

**스트리밍 타입:**

| 타입 | 설명 |
|------|------|
| `stream/text` | Server-Sent Events (텍스트 청크) |
| `stream/json` | Server-Sent Events (JSON 청크) |

**UI 타입:**

| 타입 | 설명 |
|------|------|
| `select` | 드롭다운 선택 (subtype으로 옵션 정의) |

### 포맷 값

`format` 필드는 데이터 전송 방식을 지정합니다:

| 포맷 | 설명 |
|------|------|
| `base64` | 요청 본문에 base64 인코딩 |
| `url` | URL로 참조 |
| `path` | 파일 경로로 참조 |
| `stream` | 스트림으로 전달 |

### 입력 스키마 추론 방식

model-compose는 작업의 `input` 필드에 있는 변수 바인딩 표현식을 분석합니다:

```yaml
workflows:
  - id: example
    jobs:
      - id: task
        component: my-component
        input:
          prompt: ${input.prompt as text}
          image: ${input.photo as image;base64}
          count: ${input.count as integer | 5}
```

위 설정은 다음과 같은 입력 스키마를 생성합니다:

```json
{
  "input": [
    { "name": "prompt", "type": "text" },
    { "name": "photo", "type": "image", "format": "base64" },
    { "name": "count", "type": "integer", "default": 5 }
  ]
}
```

**추론 규칙:**
- `${input.name}` → 타입은 기본값 `string`
- `${input.name as type}` → 지정된 타입 사용
- `${input.name as type;format}` → 포맷 포함
- `${input.name as type | default}` → 기본값 포함

---

## 6.4 출력 스키마

출력 스키마는 워크플로우 완료 시 반환되는 데이터를 설명합니다.

- 워크플로우가 명시적인 `output` 매핑을 선언한 경우, 스키마는 **그 매핑에서 직접** 추론됩니다.
- 그렇지 않으면 **터미널 작업** — 다른 작업이 의존하지 않는 작업 — 의 output에서 추론됩니다.

### 워크플로우 수준 출력

워크플로우 자체에 `output`을 정의하면 스키마는 해당 매핑에 포함된 변수를 그대로 반영합니다.

```yaml
workflows:
  - id: summarize
    jobs:
      - id: generate
        component: gpt4o
        input:
          prompt: ${input.text as text}

    output:
      summary: ${jobs.generate.output.text as markdown}
      tokens: ${jobs.generate.output.usage.total_tokens as integer}
```

생성되는 스키마:

```json
{
  "output": [
    { "name": "summary", "type": "markdown" },
    { "name": "tokens", "type": "integer" }
  ]
}
```

### 기본 출력

```yaml
workflows:
  - id: summarize
    jobs:
      - id: generate
        component: gpt4o
        input:
          prompt: ${input.text as text}
        output:
          summary: ${output as markdown}
```

생성되는 스키마:

```json
{
  "output": [
    { "name": "summary", "type": "markdown" }
  ]
}
```

### 다중 출력 변수

```yaml
output:
  text: ${output.content}
  confidence: ${output.score as number}
```

생성되는 스키마:

```json
{
  "output": [
    { "name": "text", "type": "string" },
    { "name": "confidence", "type": "number" }
  ]
}
```

### 그룹 출력 (repeat_count)

작업에서 `repeat_count > 1`을 사용하면 출력 변수가 그룹으로 감싸집니다:

```yaml
jobs:
  - id: generate
    component: gpt4o
    repeat_count: 3
    input:
      prompt: ${input.prompt}
    output: ${output as text}
```

생성되는 스키마:

```json
{
  "output": [
    {
      "name": null,
      "variables": [
        { "name": null, "type": "text" }
      ],
      "repeat_count": 3
    }
  ]
}
```

이는 클라이언트에게 출력이 변수 그룹의 3회 반복을 포함함을 알려줍니다.

---

## 6.5 스키마 활용

### Web UI 폼 자동 생성

`webui`가 활성화되면 model-compose는 입력 스키마를 사용하여 폼 컨트롤을 자동 생성합니다:

| 변수 타입 | UI 컨트롤 |
|-----------|-----------|
| `string` | 텍스트 입력 |
| `text` | 텍스트 영역 |
| `integer` / `number` | 숫자 입력 (어노테이션 시 슬라이더) |
| `boolean` | 체크박스 |
| `image` | 파일 업로드 (이미지) |
| `audio` | 파일 업로드 (오디오) |
| `file` | 파일 업로드 |
| `select` | 드롭다운 |

### MCP 서버 도구 매핑

컨트롤러 타입이 `mcp-server`일 때 워크플로우 입력 변수가 도구 매개변수로 변환됩니다:

```yaml
controller:
  adapter:
    type: mcp-server

workflows:
  - id: translate
    jobs:
      - id: task
        component: translator
        input:
          text: ${input.text as text}
          target_lang: ${input.target_lang as select/en,ko,ja,zh}
```

이는 MCP 도구 `translate`를 다음 매개변수로 등록합니다:
- `text` (string, 필수)
- `target_lang` (enum: en, ko, ja, zh)

### 클라이언트 SDK 연동

스키마 엔드포인트를 사용하여 요청 페이로드를 동적으로 구성할 수 있습니다:

```python
import requests

# 스키마 조회
schema = requests.get("http://localhost:8080/workflows/my-workflow/schema").json()

# 스키마 기반 입력 구성
payload = {}
for var in schema["input"]:
    if var.get("default") is not None:
        payload[var["name"]] = var["default"]
    else:
        payload[var["name"]] = get_user_input(var["name"], var["type"])

# 워크플로우 실행
result = requests.post(
    "http://localhost:8080/workflows/runs",
    json={"workflow_id": "my-workflow", "input": payload}
).json()
```

---

## 6.6 실전 예제

### 예제 1: 텍스트 채팅 워크플로우

```yaml
components:
  - id: gpt4o
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: system
            content: ${input.system_prompt}
          - role: user
            content: ${input.user_prompt}
      output: ${response.choices[0].message.content}

workflows:
  - id: chat
    title: Chat with GPT-4o
    jobs:
      - id: generate
        component: gpt4o
        input:
          system_prompt: ${input.system_prompt as text | You are a helpful assistant.}
          user_prompt: ${input.user_prompt as text}
        output: ${output as markdown}
```

**생성된 스키마:**
```json
{
  "workflow_id": "chat",
  "title": "Chat with GPT-4o",
  "input": [
    { "name": "system_prompt", "type": "text", "default": "You are a helpful assistant." },
    { "name": "user_prompt", "type": "text" }
  ],
  "output": [
    { "name": null, "type": "markdown" }
  ]
}
```

### 예제 2: 이미지 분석 워크플로우

```yaml
workflows:
  - id: analyze-image
    title: Analyze Image
    jobs:
      - id: analyze
        component: vision-model
        input:
          image: ${input.image as image;base64}
          question: ${input.question as text | Describe this image.}
        output:
          description: ${output as markdown}
```

**생성된 스키마:**
```json
{
  "workflow_id": "analyze-image",
  "title": "Analyze Image",
  "input": [
    { "name": "image", "type": "image", "format": "base64" },
    { "name": "question", "type": "text", "default": "Describe this image." }
  ],
  "output": [
    { "name": "description", "type": "markdown" }
  ]
}
```

### 예제 3: 스트리밍 워크플로우

```yaml
workflows:
  - id: stream-chat
    title: Streaming Chat
    jobs:
      - id: generate
        component: gpt4o-stream
        input:
          prompt: ${input.prompt as text}
        output: ${output as stream/text}
```

**생성된 스키마:**
```json
{
  "workflow_id": "stream-chat",
  "title": "Streaming Chat",
  "input": [
    { "name": "prompt", "type": "text" }
  ],
  "output": [
    { "name": null, "type": "stream/text" }
  ]
}
```

`stream/text` 출력 타입은 클라이언트가 Server-Sent Events를 통한 스트리밍 응답을 기대해야 함을 나타냅니다.

---

## 6.7 워크플로우 메타데이터 필드

입출력 변수 외에도 스키마에는 워크플로우 수준의 메타데이터가 포함됩니다:

| 필드 | 타입 | 설명 |
|------|------|------|
| `workflow_id` | string | 고유 식별자 |
| `title` | string? | 사람이 읽을 수 있는 제목 (Web UI에 표시) |
| `description` | string? | 워크플로우에 대한 상세 설명 |
| `default` | boolean | 기본 워크플로우 여부 |

### 비공개 워크플로우

`private: true`로 표시된 워크플로우는 스키마 API에서 제외됩니다:

```yaml
workflows:
  - id: internal-helper
    private: true
    jobs:
      - id: task
        component: helper
```

비공개 워크플로우는 `GET /workflows` 또는 `GET /workflows/{id}/schema`를 통해 접근할 수 없습니다.

---

## 6.8 모범 사례

1. **항상 타입을 지정하세요** — `${input.field}` 대신 `${input.field as type}`을 사용하여 정확한 스키마를 생성합니다.

2. **기본값을 제공하세요** — `${input.field as type | default}`을 사용하여 선택적 매개변수에 기본값을 지정합니다.

3. **설명적인 제목을 사용하세요** — 워크플로우에 `title`을 설정하여 Web UI와 MCP 도구에 의미 있는 이름을 표시합니다.

4. **스키마를 안정적으로 유지하세요** — 입력 변수의 이름이나 타입을 변경하면 클라이언트에 영향을 줍니다. 기본값이 있는 새 변수를 추가하는 것이 좋습니다.

5. **내부 워크플로우에는 private을 사용하세요** — 헬퍼/서브 워크플로우를 `private: true`로 표시하여 공개 스키마를 깔끔하게 유지합니다.

---

> **다음 장**: [7장: 컨트롤러 설정](./07-controller-configuration.md) — HTTP 서버, MCP 서버 및 기타 컨트롤러 유형을 구성하는 방법을 알아봅니다.
