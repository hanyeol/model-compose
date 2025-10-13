# 12. 변수 바인딩

이 장에서는 model-compose의 변수 바인딩 문법을 상세히 설명합니다. 변수 바인딩은 `${...}` 구문을 사용하여 데이터를 참조하고 변환하는 핵심 기능입니다.

---

## 12.1 기본 문법

변수 바인딩은 `${...}` 구문을 사용하여 데이터를 참조하고 변환합니다.

### 기본 구조

변수 바인딩은 **데이터 소스**(`key.path`)를 지정하고, 필요에 따라 **타입 변환**(`as type/subtype;format`), **기본값**(`| default`), **메타데이터**(`@(annotation)`)를 추가할 수 있습니다.

**전체 문법**:
```
${key.path as type/subtype;format | default @(annotation)}
```

데이터 소스(`key.path`) 이외의 모든 요소는 선택적입니다.

**사용 예시**:

```yaml
# 가장 간단한 형태
${input.name}

# 타입과 서브타입 지정
${input.avatar as image/png}

# 포맷 지정
${input.photo as image;base64}

# 기본값 설정
${input.count | 0}

# 메타데이터 추가
${input.email @(description "이메일 주소")}

# 모든 요소 조합
${input.profile as image/jpeg;url | ${env.DEFAULT_AVATAR} @(description "프로필 사진")}
```

### 구성 요소 상세 설명

| 요소 | 설명 | 예시 |
|------|------|------|
| **key** | 데이터 소스 (`input`, `response`, `result`, `env` 등) | `input`, `response`, `jobs` |
| **path** | 점 표기법으로 중첩 필드 접근, 배열 인덱스 지원 | `.user.name`, `.data[0].id` |
| **type** | 데이터 타입 (상세 목록은 아래 참조) | `image`, `audio`, `text`, `json` |
| **subtype** | 타입의 세부 형식 (MIME subtype 또는 파일 확장자) | `jpeg`, `png`, `mp3`, `wav` |
| **format** | 데이터 포맷 (상세 목록은 아래 참조) | `base64`, `url`, `sse-json` |
| **default** | 값이 없을 때 사용할 기본값 | `"기본값"`, `0`, `${env.FALLBACK}` |
| **annotation** | 변수에 대한 메타데이터 (UI 힌트, 설명, 검증 규칙 등) | `@(description "사용자명")` |

**데이터 타입(`type`) 상세 목록**:

| 카테고리 | 타입 | 설명 |
|----------|------|------|
| **기본형** | `string` | 일반 문자열 |
| | `text` | 긴 텍스트 (textarea) |
| | `integer` | 정수 |
| | `number` | 숫자 (정수/실수) |
| | `boolean` | 참/거짓 |
| | `list` | 배열 |
| | `json` | JSON 객체 |
| | `object[]` | 객체 배열 |
| **인코딩** | `base64` | Base64 인코딩 데이터 |
| | `markdown` | 마크다운 텍스트 |
| **미디어** | `image` | 이미지 파일 |
| | `audio` | 오디오 파일 |
| | `video` | 비디오 파일 |
| | `file` | 일반 파일 |
| **UI** | `select` | 드롭다운 선택 |

**데이터 포맷(`format`) 상세 목록**:

| 카테고리 | 포맷 | 설명 |
|----------|------|------|
| **인코딩** | `base64` | Base64 인코딩 형식 |
| **소스** | `url` | URL 주소 형식 |
| | `path` | 파일 경로 형식 |
| | `stream` | 스트림 데이터 |
| **스트리밍 출력** | `sse-text` | Server-Sent Events 텍스트 형식 |
| | `sse-json` | Server-Sent Events JSON 형식 |

**간단한 예시**:
```yaml
${input.name}                                      # 기본: 이름 필드만
${input.avatar as image/png}                       # 타입 변환: PNG 이미지로
${input.bio as markdown}                           # 타입 지정: 마크다운 텍스트
${input.photo as image;base64}                     # 포맷 지정: base64 인코딩
${input.count | 0}                                 # 기본값: 없으면 0
${input.email @(description "이메일 주소")}           # 주석: UI에 레이블 표시
```

---

## 12.2 변수 참조

변수 참조는 점 표기법(dot notation)과 배열 인덱싱을 사용하여 워크플로우의 다양한 데이터 소스에 접근할 수 있게 합니다. 입력 데이터, 컴포넌트 출력, 작업 결과, 환경 변수 등을 참조할 수 있습니다. `${...}` 구문은 중첩된 객체 경로, 배열 접근, 그리고 구성 파일에서 사용되는 위치에 따라 달라지는 컨텍스트별 변수를 지원합니다.

### 12.2.1 단일 값 참조

```yaml
${input}                    # 전체 입력 객체
${input.field}              # 입력의 field 필드
${input.user.email}         # 중첩 경로
${response.data[0].id}      # 배열 인덱스
```

### 12.2.2 컴포넌트별 응답 변수 소스

**중요**: 컴포넌트 타입에 따라 응답 데이터를 참조하는 변수가 다릅니다.

| 컴포넌트 타입 | 변수 소스 | 스트리밍 변수 | 설명 |
|--------------|----------|--------------|------|
| `http-client` | `${response}` | `${response[]}` | HTTP 응답 데이터 |
| `http-server` | `${response}` | `${response[]}` | 관리형 HTTP 서버 응답 |
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

**사용 예제**:

```yaml
# HTTP 클라이언트 - response 사용
components:
  - id: openai-api
    type: http-client
    endpoint: https://api.openai.com/v1/chat/completions
    output: ${response.choices[0].message.content}

# 로컬 모델 - result 사용
components:
  - id: local-model
    type: model
    task: text-generation
    model: gpt2
    output: ${result}

# 벡터 스토어 - response 사용
components:
  - id: chroma-db
    type: vector-store
    driver: chroma
    action: search
    output: ${response}

# 셸 명령 - stdout/stderr 사용
components:
  - id: run-script
    type: shell
    command: echo "Hello"
    output: ${stdout}
```

**핵심 규칙**:
- HTTP 기반 컴포넌트 (`http-client`, `http-server`, `vector-store`, `mcp-client`) → `${response}`
- 로컬 실행 컴포넌트 (`model`, `datasets`, `text-splitter`, `image-processor`) → `${result}`
- 셸 명령 → `${stdout}` 또는 `${stderr}`
- 워크플로우 호출 → `${output}`

### 12.2.3 스트리밍 참조 (청크별)

```yaml
${result[]}                 # 모델 스트리밍 청크
${response[]}               # HTTP 스트리밍 청크
${result[0]}                # 특정 인덱스 청크
```

스트리밍을 지원하는 컴포넌트:
- `http-client` (stream_format 설정 시) → `${response[]}`
- `http-server` (stream_format 설정 시) → `${response[]}`
- `model` (streaming: true 설정 시) → `${result[]}`

### 12.2.4 작업 결과 참조

```yaml
${jobs.job-id.output}           # 특정 작업 출력
${jobs.job-id.output.field}     # 작업 출력의 특정 필드
```

### 12.2.5 환경 변수

```yaml
${env.OPENAI_API_KEY}       # 환경 변수
${env.PORT | 8080}          # 기본값 포함
```

---

## 12.3 타입 변환

타입 변환은 `as` 키워드를 사용하여 변수 값을 특정 데이터 타입으로 변환할 수 있게 합니다. 이를 통해 컴포넌트 간 데이터 호환성을 보장하고 다양한 사용 사례에 맞는 적절한 포맷을 제공합니다. 기본 타입(text, number, boolean) 간 변환, 객체 배열에서 특정 필드 추출, 포맷 지정이 가능한 미디어 타입 처리 등을 지원합니다.

### 12.3.1 기본 타입

| 타입 | 설명 | 예제 |
|------|------|------|
| `text` | 문자열로 변환 | `${input.message as text}` |
| `number` | 실수로 변환 | `${input.price as number}` |
| `integer` | 정수로 변환 | `${input.count as integer}` |
| `boolean` | 불리언으로 변환 | `${input.enabled as boolean}` |
| `json` | JSON 파싱 | `${input.data as json}` |

### 12.3.2 객체 배열 변환

```yaml
# 객체 배열에서 특정 필드만 추출
${response.users as object[]/id,name}
# 결과: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# 중첩 경로 지원
${response.data as object[]/user.id,user.email,status}
# 결과: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 12.3.3 미디어 타입

| 타입 | 서브타입 | 포맷 | 예제 |
|------|---------|------|------|
| `image` | `png`, `jpg`, `webp` | `base64`, `url`, `path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`, `wav`, `ogg` | `base64`, `url`, `path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`, `webm` | `base64`, `url`, `path` | `${result as video/mp4}` |
| `file` | 임의 | `base64`, `url`, `path` | `${input.document as file}` |

### 12.3.4 Base64 인코딩

```yaml
${output as base64}                      # 바이너리 데이터를 Base64로 인코딩
```

### 12.3.5 Base64 디코딩

```yaml
${output as audio/mp3;base64}           # Base64 문자열을 디코딩해서 오디오로 변환
${output as image/png;base64}           # Base64 문자열을 디코딩해서 이미지로 변환
```

---

## 12.4 변수 포맷

변수 포맷 지정자는 데이터가 클라이언트나 다운스트림 컴포넌트로 직렬화되고 전송되는 방식을 제어합니다. 타입 변환 뒤에 세미콜론(`;`) 구문을 사용하여 실시간 데이터 전달을 위한 SSE와 같은 스트리밍 프로토콜을 지정하거나, Web UI에 최적화된 데이터 표현을 제공할 수 있습니다.

### 12.4.1 SSE (Server-Sent Events) 스트리밍

```yaml
# 텍스트 스트림
output: ${output as text;sse-text}

# JSON 스트림
output: ${output as text;sse-json}
```

### 12.4.2 Web UI 특화

```yaml
# Web UI가 자동으로 UI 컴포넌트 선택
${input.photo as image}      # 이미지 업로드 위젯
${output as audio}           # 오디오 플레이어
${result as text}            # 텍스트박스
```

---

## 12.5 기본값

기본값은 변수가 누락되었거나, null일 때 대체 데이터를 제공합니다. 파이프(`|`) 연산자를 사용하여 리터럴 값을 지정하거나, 환경 변수를 참조할 수 있습니다. 환경 변수를 기본값으로 사용하는 경우, 해당 환경 변수에 대해서도 한 단계에 한해 리터럴 기본값을 추가로 지정할 수 있습니다.

### 12.5.1 리터럴 기본값

```yaml
${input.temperature | 0.7}             # 숫자
${input.model | "gpt-4o"}              # 문자열
${input.enabled | true}                # 불리언
```

### 12.5.2 환경 변수 기본값

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # 환경 변수를 기본값으로 사용
${input.api_key | ${env.API_KEY}}             # 환경 변수를 기본값으로 사용
```

### 12.5.3 중첩 기본값 (환경 변수 + 리터럴)

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 12.6 어노테이션

MCP 서버에서 파라미터 설명을 제공할 때 사용합니다.

### 12.6.1 기본 어노테이션

```yaml
${input.channel @(description Slack channel ID)}
${input.limit as integer | 10 @(description Maximum number of results)}
```

### 12.6.2 복합 예제

```yaml
input:
  prompt: ${input.prompt as text @(description The text prompt for generation)}
  temperature: ${input.temperature as number | 0.7 @(description Controls randomness (0-2))}
  max_tokens: ${input.max_tokens as integer | 100 @(description Maximum tokens to generate)}
```

---

## 12.7 UI 타입 힌트

Web UI에서 입력 위젯 타입을 지정합니다.

### 12.7.1 Select (드롭다운)

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 12.7.2 Slider

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# 형식: slider/min,max,step | default
```

### 12.7.3 Textarea

```yaml
${input.prompt as text}
# UI 힌트는 타입에 포함되지 않음 (Web UI가 자동 감지)
```

---

## 12.8 실전 예제

### 12.8.1 OpenAI API 호출

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

### 12.8.2 이미지 처리 파이프라인

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

### 12.8.3 스트리밍 응답

```yaml
workflow:
  output: ${output as text;sse-text}

component:
  type: http-client
  body:
    stream: true
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

### 12.8.4 벡터 검색 결과 포맷

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# 결과: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 12.8.5 조건부 기본값

```yaml
component:
  type: http-client
  headers:
    Authorization: Bearer ${input.api_key | ${env.OPENAI_API_KEY}}
  body:
    model: ${input.model | ${env.DEFAULT_MODEL | "gpt-4o"}}
```

---

## 다음 단계

실습해보세요:
- 다양한 타입 변환 표현식 작성
- 중첩된 기본값과 환경 변수 활용
- UI 타입 힌트로 Gradio 인터페이스 개선
- 스트리밍 출력 포맷 실험

---

**다음 장**: [13. 시스템 통합](./13-system-integration.md)
