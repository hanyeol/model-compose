# 12. 변수 바인딩

이 장에서는 model-compose의 변수 바인딩 문법을 상세히 설명합니다. 변수 바인딩은 `${...}` 구문을 사용하여 데이터를 참조하고 변환하는 핵심 기능입니다.

---

## 12.1 기본 문법

변수 바인딩은 `${...}` 구문을 사용하여 데이터를 참조하고 변환합니다.

**기본 구조**:
```
${key.path as type/subtype;format | default @(annotation)}
```

---

## 12.2 키 참조

### 12.2.1 단일 값 참조

```yaml
${input}                    # 전체 입력 객체
${input.field}              # 입력의 field 필드
${input.user.email}         # 중첩 경로
${response.data[0].id}      # 배열 인덱스
```

### 12.2.2 스트리밍 참조 (청크별)

```yaml
${result[]}                 # 모델 스트리밍 청크
${response[]}               # HTTP 스트리밍 청크
${result[0]}                # 특정 인덱스 청크
```

### 12.2.3 작업 결과 참조

```yaml
${jobs.job-id.output}           # 특정 작업 출력
${jobs.job-id.output.field}     # 작업 출력의 특정 필드
```

### 12.2.4 환경 변수

```yaml
${env.OPENAI_API_KEY}       # 환경 변수
${env.PORT | 8080}          # 기본값 포함
```

---

## 12.3 타입 변환

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

## 12.4 출력 포맷

### 12.4.1 SSE (Server-Sent Events) 스트리밍

```yaml
# 텍스트 스트림
output: ${output as text;sse-text}

# JSON 스트림
output: ${output as text;sse-json}
```

### 12.4.2 Gradio UI 특화

```yaml
# Gradio가 자동으로 UI 컴포넌트 선택
${input.photo as image}      # 이미지 업로드 위젯
${output as audio}           # 오디오 플레이어
${result as text}            # 텍스트박스
```

---

## 12.5 기본값

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

Gradio Web UI에서 입력 위젯 타입을 지정합니다.

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
# UI 힌트는 타입에 포함되지 않음 (Gradio가 자동 감지)
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
