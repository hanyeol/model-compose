# OpenAI Chat Completions 스트림 예제

이 예제는 실시간 스트리밍 응답과 함께 OpenAI의 GPT-4o 모델을 Chat Completions API를 통해 사용하여 스트리밍 채팅 인터페이스를 만드는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 스트리밍 채팅 인터페이스를 제공합니다:

1. **스트리밍 Chat Completion**: 사용자 프롬프트를 받아 OpenAI의 GPT-4o 모델을 사용하여 실시간 스트리밍 응답 생성
2. **Server-Sent Events**: 실시간 사용자 경험을 위한 SSE (Server-Sent Events)로 응답 전달
3. **Temperature 제어**: temperature 매개변수를 통한 응답 창의성 사용자 정의 가능

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/openai-chat-completions-stream
   ```

2. 샘플 환경 파일 복사:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일을 편집하여 OpenAI API 키 추가:
   ```env
   OPENAI_API_KEY=your-actual-openai-api-key
   ```

## 실행 방법

1. **서비스 시작:**
  ```bash
  model-compose up
  ```

2. **워크플로우 실행:**

  **API 사용:**
  ```bash
  curl -X POST http://localhost:8080/api/workflows/runs \
    -H "Content-Type: application/json" \
    -d '{
      "input": {
        "prompt": "Explain machine learning in simple terms",
        "temperature": 0.7
      }
    }'
  ```

  **웹 UI 사용:**
  - 웹 UI 열기: http://localhost:8081
  - 프롬프트 및 설정 입력
  - "Run Workflow" 버튼 클릭

  **CLI 사용:**
  ```bash
  model-compose run --input '{
    "prompt": "Explain machine learning in simple terms",
    "temperature": 0.7
  }'
  ```

## 컴포넌트 세부사항

### OpenAI HTTP Client 컴포넌트 (기본)
- **유형**: HTTP client 컴포넌트
- **목적**: 스트리밍 chat completion을 통한 AI 기반 텍스트 생성
- **API**: OpenAI GPT-4o Chat Completions
- **엔드포인트**: `https://api.openai.com/v1/chat/completions`
- **기능**:
  - `stream: true`를 사용한 실시간 스트리밍 응답
  - 응답 창의성을 위한 구성 가능한 temperature
  - 웹 애플리케이션을 위한 Server-Sent Events 출력 형식
  - 델타 콘텐츠 추출을 위한 JSON 스트림 파싱

## 워크플로우 세부사항

### "Chat with OpenAI GPT-4o" 워크플로우 (기본)

**설명**: OpenAI의 GPT-4o를 사용하여 스트리밍 텍스트 응답 생성

#### 작업 흐름

이 예제는 명시적인 작업 없이 단순화된 단일 컴포넌트 구성을 사용합니다.

```mermaid
graph TD
    %% Default job (implicit)
    J1((Default<br/>작업))

    %% Component
    C1[OpenAI GPT-4o<br/>컴포넌트]

    %% Job to component connections (solid: invokes, dotted: returns)
    J1 --> C1
    C1 -.-> |streaming response| J1

    %% Input/Output
    Input((입력)) --> J1
    J1 --> Output((스트리밍<br/>출력))
```

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `prompt` | text | 예 | - | AI에 전송할 사용자 메시지 |
| `temperature` | number | 아니오 | 0.7 | 응답의 무작위성 제어 (0.0-1.0)<br/>• 낮은 값 (예: 0.2): 더 집중적이고 결정적<br/>• 높은 값 (예: 0.8): 더 창의적이고 다양함 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| - | text (sse-text) | Server-Sent Events 스트림으로 전달되는 AI가 생성한 응답 텍스트 |

## 스트리밍 기능

이 예제는 다음을 제공하여 표준 chat completions와 다릅니다:

- **실시간 스트리밍**: 응답이 생성되는 대로 점진적으로 전달됨
- **SSE 형식**: 웹 브라우저 호환성을 위해 Server-Sent Events로 형식화된 출력
- **델타 처리**: `${response[].choices[0].delta.content}`를 사용하여 스트리밍 JSON 청크에서 콘텐츠 추출
- **향상된 UX**: 사용자가 실시간으로 문자별로 나타나는 응답 확인

## 맞춤화

- **모델**: `gpt-4o`를 `gpt-3.5-turbo`, `gpt-4` 등의 다른 사용 가능한 모델로 변경
- **스트림 형식**: 다양한 응답 처리를 위해 `stream_format` 및 출력 추출 로직 수정
- **System Prompt**: AI의 동작 및 성격을 정의하기 위한 system 메시지 추가
- **추가 매개변수**: `max_tokens`, `presence_penalty` 등의 다른 OpenAI 매개변수 포함
- **출력 형식**: 구조화된 스트리밍 데이터를 위해 `sse-text`에서 `sse-json`으로 변경

## 고급 구성

스트리밍과 함께 시스템 프롬프트와 대화 기록을 추가하려면:

```yaml
body:
  model: gpt-4o
  messages:
    - role: system
      content: "You are a helpful assistant specialized in technical explanations."
    - role: user
      content: ${input.prompt as text}
  temperature: ${input.temperature as number | 0.7}
  max_tokens: ${input.max_tokens as number | 1000}
  streaming: true
stream_format: json
output: ${response[].choices[0].delta.content}
```

## 표준 Chat Completions와 비교

| 기능 | 표준 | 스트림 |
|-----|------|--------|
| 응답 전달 | 한 번에 완전한 응답 | 실시간 증분 |
| 사용자 경험 | 전체 응답 대기 | 생성되는 응답 확인 |
| 출력 형식 | 단일 메시지 객체 | Server-Sent Events 스트림 |
| 웹 통합 | 간단한 JSON 처리 | SSE 클라이언트 지원 필요 |
| 지연 시간 | 체감 지연 시간 높음 | 체감 지연 시간 낮음 |
