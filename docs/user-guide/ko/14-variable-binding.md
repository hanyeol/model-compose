# 14. 변수 바인딩

이 장에서는 model-compose의 변수 바인딩 문법을 상세히 설명합니다. 변수 바인딩은 `${...}` 구문을 사용하여 데이터를 참조하고 변환하는 핵심 기능입니다.

---

## 14.1 문법 개요

변수 바인딩은 **데이터 소스**(`key.path`)를 지정하고, 필요에 따라 **타입 변환**(`as type/subtype[attrs];format`), **기본값**(`| default`), **메타데이터**(`@(annotation)`)를 추가할 수 있습니다.

**전체 문법**:
```
${key.path as type/subtype[attrs];format | default @(annotation)}
```

데이터 소스(`key.path`) 이외의 모든 요소는 선택적입니다.

**사용 예시**:
```yaml
${input.name}                              # 데이터 소스만
${input.avatar as image/png}               # 타입과 서브타입 지정
${input.photo as image;base64}             # 포맷 지정
${input.count | 0}                         # 기본값 설정
${input.email @(description "이메일")}      # 메타데이터 추가
${input.profile as image/jpeg;url | ${env.DEFAULT_AVATAR} @(description "프로필 사진")}  # 모든 요소 조합
```

| 요소 | 설명 | 예시 |
|------|------|------|
| **key** | 데이터 소스 | `input`, `response`, `result`, `env`, `jobs` |
| **path** | 점 표기법으로 중첩 필드 접근, 배열 인덱스 지원 | `.user.name`, `.data[0].id` |
| **type** | 데이터 타입 ([14.4](#144-타입-변환)) | `image`, `audio`, `text`, `json` |
| **subtype** | 타입의 세부 형식 | `jpeg`, `png`, `mp3`, `pcm` |
| **attrs** | 대괄호 안의 추가 파라미터 | `sample_rate=24000,channels=1` |
| **format** | 데이터의 인코딩 상태 ([14.5](#145-포맷과-컨텍스트-의미)) | `base64`, `url`, `path`, `stream/json` |
| **default** | 값이 없을 때 사용할 기본값 ([14.6](#146-기본값)) | `0`, `"gpt-4o"`, `${env.FALLBACK}` |
| **annotation** | MCP/UI용 메타데이터 ([14.7](#147-메타데이터와-ui-힌트)) | `@(description "사용자명")` |

---

## 14.2 변수 소스

### 14.2.1 워크플로우 입력

```yaml
${input}                    # 전체 입력 객체
${input.field}              # 입력의 field 필드
${input.user.email}         # 중첩 경로
```

### 14.2.2 컴포넌트 응답 변수

컴포넌트 타입에 따라 응답 데이터를 참조하는 변수가 다릅니다.

| 컴포넌트 타입 | 변수 소스 | 스트리밍 변수 | 설명 |
|--------------|----------|--------------|------|
| `http-client` | `${response}` | `${response[]}` | HTTP 응답 데이터 |
| `http-server` | `${response}` | `${response[]}` | 관리형 HTTP 서버 응답 |
| `websocket-client` | `${response}` | `${response[]}` | WebSocket 수신 데이터 |
| `websocket-server` | `${response}` | `${response[]}` | 관리형 WebSocket 서버 데이터 |
| `mcp-client` | `${response}` | - | MCP 응답 데이터 |
| `mcp-server` | `${response}` | - | 관리형 MCP 서버 응답 |
| `model` | `${result}` | `${result[]}` | 모델 추론 결과 |
| `model-trainer` | `${result}` | - | 훈련 결과 메트릭 |
| `vector-store` | `${response}` | - | 벡터 검색/삽입 결과 |
| `datasets` | `${result}` | - | 데이터셋 샘플 |
| `text-splitter` | `${result}` | - | 분할된 텍스트 청크 |
| `image-processor` | `${result}` | - | 처리된 이미지 |
| `workflow` | `${output}` | - | 서브 워크플로우 출력 |
| `shell` | `${stdout}`, `${stderr}` | - | 명령 실행 결과 |

**핵심 규칙**:
- HTTP 기반 컴포넌트 (`http-client`, `http-server`, `vector-store`, `mcp-client`) → `${response}`
- 로컬 실행 컴포넌트 (`model`, `datasets`, `text-splitter`, `image-processor`) → `${result}`
- 셸 명령 → `${stdout}` 또는 `${stderr}`
- 워크플로우 호출 → `${output}`

### 14.2.3 이전 작업 출력

```yaml
${jobs.job-id.output}           # 특정 작업 출력
${jobs.job-id.output.field}     # 작업 출력의 특정 필드
```

### 14.2.4 환경 변수

```yaml
${env.OPENAI_API_KEY}       # 환경 변수
${env.PORT | 8080}          # 기본값 포함
```

### 14.2.5 스트리밍 청크 참조

변수명에 `[]`를 붙이면 단일 값이 아닌 청크 스트림으로 데이터를 수신합니다.

```yaml
${response[]}               # HTTP 스트리밍 청크
${result[]}                 # 모델 스트리밍 청크
```

스트리밍을 지원하는 컴포넌트:
- `http-client` / `http-server` → `${response[]}`
- `websocket-client` / `websocket-server` → `${response[]}`
- `model` (streaming: true 설정 시) → `${result[]}`

---

## 14.3 경로 접근

변수 경로는 중첩 객체에 대한 점 표기법과 배열 인덱싱을 지원합니다.

```yaml
${response.choices[0].message.content}     # 중첩 객체 + 배열 인덱스
${response.data[-1].id}                    # 음수 인덱스 (마지막 요소)
${input.users[0].name}                     # 첫 번째 요소의 name 필드
```

### 14.3.1 배열 와일드카드 (`[*]`)

경로에서 `[*]`를 사용하면 배열의 모든 요소에서 특정 필드를 선택합니다. 결과는 그 필드만 담은 새 배열입니다.

```yaml
${response.items[*].id}
# items = [{id: 1, name: "a"}, {id: 2, name: "b"}]
# 결과: [1, 2]

${response.messages[*].tool_calls[*].id}   # 중첩 배열에서 와일드카드 연쇄 사용
```

`[*]`는 필드를 뽑을 뿐 요소 구조를 재구성하지 않습니다. 요소마다 새로운 객체를 만들려면 [객체 배열 프로젝션](#1442-객체-배열-프로젝션) 또는 [맵 표현식](#149-맵-표현식)을 사용하세요.

---

## 14.4 타입 변환

`as` 키워드를 사용하여 변수 값을 특정 데이터 타입으로 변환합니다.

### 14.4.1 기본 타입

| 타입 | 설명 | 예제 |
|------|------|------|
| `text` | 문자열로 변환 | `${input.message as text}` |
| `number` | 실수로 변환 | `${input.price as number}` |
| `integer` | 정수로 변환 | `${input.count as integer}` |
| `boolean` | 불리언으로 변환 (`"true"`, `"1"` → true) | `${input.enabled as boolean}` |
| `json` | JSON 문자열을 객체로 파싱 | `${input.data as json}` |

### 14.4.2 객체 배열 프로젝션

`subtype`에 쉼표로 구분된 필드 경로를 지정하여 객체 배열에서 특정 필드만 추출합니다.

```yaml
# 객체 배열에서 특정 필드만 추출
${response.users as object[]/id,name}
# 결과: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# 중첩 경로 지원 (마지막 세그먼트가 키 이름)
${response.data as object[]/user.id,user.email,status}
# 결과: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 14.4.3 미디어 타입

| 타입 | 서브타입 | 포맷 | 예제 |
|------|---------|------|------|
| `image` | `png`, `jpg`, `webp` | `base64`, `url`, `path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`, `wav`, `ogg`, `pcm` | `base64`, `url`, `path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`, `webm` | `base64`, `url`, `path` | `${result as video/mp4}` |
| `file` | 임의 | `base64`, `url`, `path` | `${input.document as file}` |

### 14.4.4 속성

대괄호 구문 `type/subtype[key=value,...]`으로 추가 키-값 파라미터를 제공합니다. 속성은 타입, 서브타입과 함께 딕셔너리로 전달되어 타입 변환 및 후속 처리에 추가적인 컨텍스트를 제공합니다.

```yaml
# PCM 오디오와 인코딩 파라미터
${response[] as audio/pcm[sample_rate=24000,channels=1,bit_depth=16]}
```

### 14.4.5 Base64 타입 vs Base64 포맷

이 둘은 다른 개념입니다:

- **`base64` 타입** (`${value as base64}`) — 값을 base64 문자열로 **인코딩**합니다. 컨텍스트와 무관하게 항상 수행됩니다.
- **`base64` 포맷** (`${value as image;base64}`) — 값이 **이미 base64로 인코딩되어 있음**을 나타냅니다. 입력 컨텍스트에서는 시스템이 디코딩하고, 출력 컨텍스트에서는 메타데이터로 보존됩니다.

```yaml
# 바이너리 데이터를 base64로 인코딩 (타입)
${output as base64}

# 이 데이터가 base64로 인코딩되어 있음을 명시 (포맷) — 입력 컨텍스트에서 디코딩됨
${input.photo as image;base64}
```

---

## 14.5 포맷과 컨텍스트 의미

포맷 지정자는 데이터의 **인코딩 상태**를 기술합니다. 동일한 `as type;format` 구문이 사용 위치에 따라 다르게 동작합니다.

### 14.5.1 포맷 값

| 포맷 | 설명 | 예시 |
|------|------|------|
| `base64` | 데이터가 base64로 인코딩됨 | `${input.photo as image;base64}` |
| `url` | 데이터가 가져올 URL임 | `${input.avatar as image;url}` |
| `path` | 데이터가 파일 경로임 | `${output.path as audio;path}` |
| `stream` | 데이터가 스트림임 | `${output as audio;stream}` |

> **참고:** `stream/text`와 `stream/json`은 포맷이 아닌 **타입**입니다. 값을 SSE 스트림으로 변환하려면 `${output as stream/text}` 또는 `${output as stream/json}`을 사용하세요.

### 14.5.2 입력 컨텍스트

컴포넌트 액션 `input`에서 포맷은 **수신 데이터의 현재 인코딩 방식**을 알려주고, 시스템이 컴포넌트가 기대하는 형태로 변환합니다.

| 타입 | 포맷 | 입력 값 | 처리 결과 |
|------|------|---------|----------|
| `image` | `base64` | base64 문자열 | 디코딩하여 임시 파일로 저장 |
| `image` | `url` | URL 문자열 | 다운로드하여 임시 파일로 저장 |
| `image` | `path` | 파일 경로 | 파일 참조로 직접 사용 |
| `image` | (없음) | bytes / stream | 임시 파일로 저장 |
| `audio` | `base64` | base64 문자열 | 디코딩하여 임시 파일로 저장 |
| `audio` | `url` | URL 문자열 | 다운로드하여 임시 파일로 저장 |

```yaml
# "이 데이터는 base64로 인코딩된 이미지" → 시스템이 파일로 디코딩
input:
  image: ${input.photo as image;base64}
```

### 14.5.3 컴포넌트/작업 출력 컨텍스트

컴포넌트/작업 액션 `output`에서 미디어 파일 변환은 **수행되지 않습니다**. 값은 기본적인 타입 변환(예: `integer`, `json`, `base64` 인코딩)만 적용되어 그대로 전달됩니다. 포맷은 다운스트림 소비자를 위한 메타데이터로 보존됩니다.

| 타입 | 포맷 | 처리 결과 |
|------|------|----------|
| `image` | `base64` | 값을 그대로 전달 (디코딩 없음) |
| `audio` | `path` | 파일 객체를 파일 경로로 렌더링 |
| `stream/text` | (없음) | 값을 SSE 텍스트 스트림으로 래핑 |
| `stream/json` | (없음) | 값을 SSE JSON 스트림으로 래핑 |
| `base64` | (모든) | 값을 base64 문자열로 인코딩 (항상 수행) |

```yaml
# "이 데이터가 base64로 인코딩된 이미지임을 소비자에게 알림"
output: ${result as image;base64}
```

### 14.5.4 워크플로우 출력 컨텍스트

워크플로우 출력 변수는 워크플로우 스키마에 `type`과 `format`을 정의합니다. **컨트롤러 어댑터**가 이를 소비하여 데이터의 표시 및 전송 방식을 결정합니다:

| 소비자 | 포맷 | 동작 |
|--------|------|------|
| **Web UI** | `stream/text` | 텍스트 청크를 점진적으로 누적 |
| **Web UI** | `stream/json` | 각 청크를 JSON으로 파싱, `subtype` 경로로 필드 추출 |
| **Web UI** | `base64` | base64를 디코딩하여 이미지/오디오 표시 |
| **Web UI** | `url` | URL을 가져와 이미지/오디오 표시 |
| **Web UI** | `path` | 파일 경로를 직접 사용 |
| **HTTP API** | (모든) | 포맷 미사용; 출력 데이터 타입에 의해 전송 방식 결정 |

```yaml
# Web UI는 텍스트 청크를 누적; HTTP API는 SSE로 전송
workflow:
  output: ${output as stream/text}
```

---

## 14.6 기본값

기본값은 변수가 누락되었거나 null일 때 대체 데이터를 제공합니다. 파이프(`|`) 연산자를 사용하여 리터럴 값이나 환경 변수를 지정할 수 있습니다.

### 14.6.1 리터럴 기본값

```yaml
${input.temperature | 0.7}             # 숫자
${input.model | "gpt-4o"}              # 문자열
${input.enabled | true}                # 불리언
```

### 14.6.2 환경 변수 기본값

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # 환경 변수를 기본값으로 사용
${input.api_key | ${env.API_KEY}}             # 환경 변수를 기본값으로 사용
```

### 14.6.3 중첩 기본값 (환경 변수 + 리터럴)

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 14.7 메타데이터와 UI 힌트

### 14.7.1 어노테이션

MCP 서버에서 파라미터 설명을 제공할 때 사용합니다.

```yaml
${input.channel @(description Slack channel ID)}
${input.limit as integer | 10 @(description Maximum number of results)}
```

```yaml
input:
  prompt: ${input.prompt as text @(description The text prompt for generation)}
  temperature: ${input.temperature as number | 0.7 @(description Controls randomness (0-2))}
  max_tokens: ${input.max_tokens as integer | 100 @(description Maximum tokens to generate)}
```

### 14.7.2 Select (드롭다운)

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 14.7.3 Slider

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# 형식: slider/min,max,step | default
```

### 14.7.4 Textarea

```yaml
${input.prompt as text}
# Web UI가 text 타입을 textarea 위젯으로 렌더링
```

---

## 14.8 스프레드 연산자

스프레드 연산자는 값의 내용을 주변 dict나 list에 인라인으로 병합합니다. 두 가지 형태를 지원합니다.

### 14.8.1 Dict 스프레드 (`"..."`)

dict 안에서 `"..."` 키는 참조한 dict의 필드를 주변 dict에 병합합니다. 명시적인 형제 키가 있으면 스프레드 필드를 덮어씁니다.

```yaml
body:
  "...": ${input}          # input의 모든 필드를 body에 복사
  model: gpt-4o            # 특정 필드 덮어쓰기 / 추가
```

스프레드 값은 dict(또는 `null`, 이 경우 무시)여야 합니다.

### 14.8.2 List 스프레드 (`...${x}`)

list 안에서 `...${source}` 형태의 문자열 아이템은 참조한 list의 모든 요소를 주변 list에 이어붙입니다.

```yaml
messages:
  - role: system
    content: You are a helpful assistant.
  - ...${input.history}    # 이전 메시지 전체 이어붙이기
  - role: user
    content: ${input.prompt}
```

스프레드 값은 list(또는 `null`, 이 경우 무시)여야 합니다.

---

## 14.9 맵 표현식

맵 표현식은 소스 리스트의 모든 요소를 새로운 값으로 변환합니다. dict의 `"*"` 키에 소스 리스트를 두고 나머지 필드가 각 요소에 적용될 템플릿이 됩니다. 템플릿 내부에서 현재 요소는 `${item}`으로 참조합니다.

### 14.9.1 기본 맵

```yaml
tools:
  "*": ${tools}
  type: function
  function: ${item}
# 결과: [{type: "function", function: <tool0>}, {type: "function", function: <tool1>}, ...]
```

### 14.9.2 스프레드와 결합

맵과 dict 스프레드를 조합해서 원본 필드는 유지하고 필요한 필드만 덮어쓸 수 있습니다.

```yaml
messages:
  "*": ${messages}
  "...": ${item}                  # 원본 필드 유지
  tool_calls:                     # tool_calls는 중첩 맵으로 재작성
    "*": ${item.tool_calls}
    id: ${item.id}
    type: function
    function:
      name: ${item.name}
      arguments: ${item.arguments}
```

### 14.9.3 중첩 맵과 `${item}` 스코프

맵은 중첩 가능합니다. `${item}`은 항상 **가장 안쪽** 맵의 요소를 참조합니다. 안쪽 맵이 끝나면 `${item}`은 다시 바깥 요소로 돌아옵니다.

```yaml
"*": ${orders}                    # 바깥: item = 주문
customer: ${item.customer}
lines:
  "*": ${item.lines}              # 안쪽: item = 그 주문의 라인
  sku: ${item.sku}
  qty: ${item.qty}
```

### 14.9.4 항등 맵

템플릿이 비어 있으면 소스 리스트를 그대로 반환합니다. 유용하진 않지만 에러는 아닙니다.

```yaml
messages:
  "*": ${messages}
# 결과: ${messages} (변경 없음)
```

### 14.9.5 맵 vs 객체 배열 프로젝션

둘 다 dict의 리스트를 재구성하지만 용도가 다릅니다:

| 기능 | `as object[]/...` ([14.4.2](#1442-객체-배열-프로젝션)) | 맵 (`"*"`) |
|------|------------------------------------------------------|-----------|
| 위치 | `${...}` 표현식 내부 | YAML dict 레이아웃 |
| 의미 | 각 요소에서 필드 선택 | 템플릿에 따라 요소마다 새 값 생성 |
| 상수/래퍼 | ✗ | ✓ (리터럴이나 중첩 구조 자유) |
| 중첩 변환 | ✗ | ✓ (맵 안의 맵) |

단순한 필드 선택에는 `object[]/`, 상수 추가·요소 감싸기·중첩 변환이 필요하면 맵 표현식을 사용하세요.

> **`${item}`은 예약된 소스 이름입니다.** 맵 템플릿 내부에서는 항상 현재 요소를 가리키고, 맵 밖에서는 일반적으로 해석됩니다 (예: `for-each` 작업이 등록한 `item` 소스).

---

## 14.10 실전 예제

### 14.10.1 OpenAI API 호출

```yaml
body:
  model: ${input.model as select/gpt-4o,gpt-4o-mini,o1-mini | gpt-4o}
  messages:
    - role: user
      content: ${input.prompt as text}
  temperature: ${input.temperature as slider/0,2,0.1 | 0.7}
  max_tokens: ${input.max_tokens as integer | 1000}
output:
  message: ${response.choices[0].message.content}
```

### 14.10.2 이미지 처리 파이프라인

```yaml
jobs:
  - id: analyze
    component: vision-model
    input:
      image: ${input.image as image/jpg}
    output: ${output}

  - id: enhance
    component: image-editor
    input:
      image: ${input.image as image/jpg}
      prompt: ${jobs.analyze.output.description}
    output: ${output as image/png;base64}
```

### 14.10.3 스트리밍 응답

```yaml
workflow:
  output: ${output as stream/text}

component:
  type: http-client
  action:
    body:
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

### 14.10.4 벡터 검색 결과 포맷

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# 결과: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 14.10.5 조건부 기본값

```yaml
component:
  type: http-client
  action:
    headers:
      Authorization: Bearer ${input.api_key | ${env.OPENAI_API_KEY}}
    body:
      model: ${input.model | ${env.DEFAULT_MODEL | "gpt-4o"}}
```

---

**다음 장**: [15. 시스템 통합](./15-system-integration.md)
