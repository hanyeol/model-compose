# 11. 스트리밍 모드

이 장에서는 model-compose의 스트리밍 기능을 사용하여 실시간 응답을 생성하고 처리하는 방법을 설명합니다.

---

## 11.1 스트리밍 개요

### 11.1.1 스트리밍이란?

스트리밍 모드는 모델이나 API가 전체 응답을 생성할 때까지 기다리지 않고, 생성되는 즉시 부분적인 결과를 전달하는 방식입니다.

**장점:**
- 사용자에게 즉각적인 피드백 제공
- 긴 응답의 첫 번째 토큰까지의 지연 시간(TTFT) 감소
- 실시간 스트리밍 애플리케이션 구축 가능
- 더 나은 사용자 경험 (타이핑 효과)

**사용 사례:**
- 챗봇 대화 (ChatGPT 스타일)
- 실시간 텍스트 생성
- 긴 문서 요약
- 번역 서비스
- 코드 생성

### 11.1.2 지원 컴포넌트

스트리밍을 지원하는 컴포넌트:

| 컴포넌트 타입 | 스트리밍 지원 | 설정 방법 |
|-------------|------------|---------|
| `model` (text-generation) | ✅ | `streaming: true` |
| `model` (chat-completion) | ✅ | `streaming: true` |
| `http-client` | ✅ | `stream_format: json/text` |
| `http-server` | ✅ | `stream_format: json/text` |

### 11.1.3 스트리밍 프로토콜

model-compose는 **SSE (Server-Sent Events)** 프로토콜을 사용합니다.

**SSE 형식:**
```
data: chunk1

data: chunk2

data: chunk3

```

각 청크는 `data:` 접두사와 함께 전송되며, 빈 줄로 구분됩니다.

---

## 11.2 컴포넌트별 스트리밍 설정

### 11.2.1 모델 컴포넌트

#### 기본 설정

```yaml
component:
  type: model
  task: text-generation
  model: facebook/bart-large-cnn
  text: ${input.text as text}
  streaming: true                  # 스트리밍 활성화
  params:
    max_output_length: 150
```

**중요 제약사항:**
- `batch_size`는 반드시 `1`이어야 합니다
- 단일 입력만 지원 (배치 처리 불가)
- 스트리밍 중에는 `num_beams: 1` 권장

#### Text Generation 스트리밍

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  text: ${input.prompt as text}
  streaming: true
  params:
    max_output_length: 200
    do_sample: false               # 결정적 생성 (빠름)
    num_beams: 1                   # 빔 서치 비활성화
```

**출력 참조:**
- 스트리밍: `${result[]}` (청크별)
- 비스트리밍: `${result}` (전체 완료 후)

#### Chat Completion 스트리밍

```yaml
component:
  type: model
  task: chat-completion
  model: microsoft/DialoGPT-medium
  messages:
    - role: user
      content: ${input.message as text}
  streaming: true
  params:
    max_output_length: 100
```

**특징:**
- 대화 템플릿 자동 적용
- Text generation과 동일한 스트리밍 메커니즘
- `${result[]}` 참조로 청크별 처리

### 11.2.2 HTTP 컴포넌트

#### HTTP Client 스트리밍

**OpenAI API 스트리밍:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    model: gpt-4o
    messages:
      - role: user
        content: ${input.prompt as text}
    stream: true                   # API 파라미터
  stream_format: json              # 청크를 JSON으로 파싱
  output: ${response[].choices[0].delta.content}
```

**stream_format 옵션:**

- `json`: 각 청크를 JSON으로 파싱
  ```yaml
  stream_format: json
  output: ${response[].choices[0].delta.content}
  ```

- `text`: 각 청크를 UTF-8 텍스트로 디코딩
  ```yaml
  stream_format: text
  output: ${response[]}
  ```

- 지정하지 않음: 바이트 그대로 전달

**출력 참조:**
- 스트리밍: `${response[]}` (청크별)
- 비스트리밍: `${response}` (전체 완료 후)

#### HTTP Server (관리형 서비스) 스트리밍

**vLLM 서버 스트리밍:**

```yaml
component:
  type: http-server
  start:
    - vllm
    - serve
    - Qwen/Qwen2-7B-Instruct
    - --port
    - "8000"
  port: 8000
  healthcheck:
    path: /health
  method: POST
  path: /v1/chat/completions
  body:
    model: qwen2-7b-instruct
    messages:
      - role: user
        content: ${input.prompt as text}
    stream: true
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

---

## 11.3 워크플로우에서 스트리밍 사용

### 11.3.1 기본 스트리밍 워크플로우

```yaml
controller:
  type: http-server
  port: 8080

workflow:
  title: Streaming Chat
  output: ${output as text;sse-text}    # SSE 텍스트 형식으로 출력

component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    model: gpt-4o
    messages:
      - role: user
        content: ${input.prompt as text}
    stream: true
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

**워크플로우 출력 형식:**

- `as text;sse-text`: SSE 텍스트 스트림
  ```yaml
  output: ${output as text;sse-text}
  ```

- `as text;sse-json`: SSE JSON 스트림
  ```yaml
  output: ${output as text;sse-json}
  ```

### 11.3.2 여러 단계 워크플로우 스트리밍

```yaml
workflows:
  - id: translate-and-summarize
    title: Translate and Summarize
    output: ${output as text;sse-text}
    jobs:
      - id: translate
        component: translator
        input:
          text: ${input.text}
          target_lang: en
        # 번역은 스트리밍 없이 전체 완료 후

      - id: summarize
        component: summarizer
        input:
          text: ${jobs.translate.output}
        # 요약은 스트리밍으로 출력
        depends_on: [translate]

components:
  - id: translator
    type: model
    task: translation
    model: Helsinki-NLP/opus-mt-ko-en
    text: ${input.text as text}
    streaming: false

  - id: summarizer
    type: model
    task: text-generation
    model: facebook/bart-large-cnn
    text: ${input.text as text}
    streaming: true                    # 마지막 작업만 스트리밍
    params:
      max_output_length: 150
```

**중요:**
- 워크플로우에서 **마지막 작업만** 스트리밍 가능
- 중간 작업은 완료될 때까지 대기 필요
- 최종 출력만 `${result[]}`로 스트리밍

### 11.3.3 조건부 스트리밍

```yaml
workflow:
  title: Conditional Streaming
  output: ${output as text;sse-text}

component:
  type: model
  task: text-generation
  model: gpt2
  text: ${input.prompt as text}
  streaming: ${input.stream | false}   # 입력에 따라 스트리밍 결정
  params:
    max_output_length: 100
```

**API 호출 예제:**

```bash
# 스트리밍 활성화
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Hello", "stream": true},
    "output_only": true,
    "wait_for_completion": true
  }'

# 스트리밍 비활성화
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Hello", "stream": false},
    "wait_for_completion": true
  }'
```

---

## 11.4 스트리밍 응답 처리

### 11.4.1 API 엔드포인트

**스트리밍 요청 요구사항:**

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Write a story"},
    "output_only": true,              # 필수: 출력만 반환
    "wait_for_completion": true       # 필수: 완료까지 대기
  }'
```

**응답 헤더:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
```

**응답 본문 (SSE):**
```
data: Once

data:  upon

data:  a

data:  time

```

### 11.4.2 클라이언트 구현 (JavaScript)

**EventSource API 사용:**

```javascript
const eventSource = new EventSource(
  'http://localhost:8080/api/workflows/runs',
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      input: { prompt: 'Hello' },
      output_only: true,
      wait_for_completion: true
    })
  }
);

eventSource.onmessage = (event) => {
  const chunk = event.data;
  console.log('Received:', chunk);
  // UI 업데이트
  document.getElementById('output').textContent += chunk;
};

eventSource.onerror = (error) => {
  console.error('Error:', error);
  eventSource.close();
};
```

**Fetch API 사용:**

```javascript
const response = await fetch('http://localhost:8080/api/workflows/runs', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    input: { prompt: 'Hello' },
    output_only: true,
    wait_for_completion: true
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const content = line.substring(6);
      console.log('Chunk:', content);
      // UI 업데이트
      document.getElementById('output').textContent += content;
    }
  }
}
```

### 11.4.3 클라이언트 구현 (Python)

**requests 라이브러리:**

```python
import requests
import json

url = 'http://localhost:8080/api/workflows/runs'
payload = {
    'input': {'prompt': 'Hello'},
    'output_only': True,
    'wait_for_completion': True
}

response = requests.post(url, json=payload, stream=True)

for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            chunk = line[6:]
            print(chunk, end='', flush=True)
```

**aiohttp 라이브러리 (비동기):**

```python
import aiohttp
import asyncio

async def stream_workflow():
    url = 'http://localhost:8080/api/workflows/runs'
    payload = {
        'input': {'prompt': 'Hello'},
        'output_only': True,
        'wait_for_completion': True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    chunk = line[6:]
                    print(chunk, end='', flush=True)

asyncio.run(stream_workflow())
```

### 11.4.4 Web UI 통합

**Gradio 자동 스트리밍:**

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Streaming Chat
  output: ${output as text;sse-text}

component:
  type: model
  task: chat-completion
  model: gpt2
  messages:
    - role: user
      content: ${input.prompt as text}
  streaming: true
```

Gradio Web UI는 자동으로:
- `sse-text` 형식 감지
- 실시간 텍스트 누적 표시
- 타이핑 애니메이션 효과

---

## 11.5 성능 및 최적화

### 11.5.1 모델 스트리밍 최적화

**빠른 토큰 생성을 위한 설정:**

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  text: ${input.prompt as text}
  streaming: true
  params:
    # 성능 최적화
    do_sample: false               # 결정적 생성 (빔 서치 없음)
    num_beams: 1                   # 단일 빔
    max_output_length: 100         # 적절한 길이 제한

    # 품질 vs 속도 균형
    # top_p: 0.9                   # 샘플링 시 사용
    # temperature: 0.8             # 샘플링 시 사용
```

**설정별 영향:**

| 파라미터 | 값 | 효과 |
|---------|---|------|
| `do_sample` | `false` | 가장 빠름, 결정적 |
| `do_sample` | `true` | 느림, 다양한 출력 |
| `num_beams` | `1` | 빠름 |
| `num_beams` | `>1` | 느림, 품질 향상 |
| `max_output_length` | 작음 | 빠른 완료 |
| `max_output_length` | 큼 | 긴 대기 시간 |

### 11.5.2 HTTP 스트리밍 최적화

**청크 크기 조정:**

기본 청크 크기는 65536 바이트입니다. aiohttp 설정으로 조정 가능:

```python
# 커스텀 HTTP 클라이언트 설정 (코드 레벨)
import aiohttp

async with aiohttp.ClientSession() as session:
    async with session.get(url, chunk_size=8192) as response:
        async for chunk in response.content.iter_chunked(8192):
            # 처리
```

**타임아웃 설정:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  timeout: 60                      # 60초 타임아웃
  path: /chat/completions
  body:
    stream: true
  stream_format: json
```

### 11.5.3 메모리 관리

**스트리밍 중 메모리 사용:**

- 모델 스트리밍: 스레드 기반, 큐 사용 (최소 메모리)
- HTTP 스트리밍: 청크 단위 처리 (전체 응답 버퍼링 안 함)
- 워크플로우: 청크별 렌더링 (누적 안 함)

**권장사항:**
- GPU 메모리: 모델 크기에 따라 결정
- CPU 메모리: 스트리밍 시 청크 크기만 필요
- 긴 응답도 메모리 효율적

### 11.5.4 네트워크 최적화

**지연 시간 최소화:**

1. **서버 위치**: 사용자와 가까운 지역
2. **HTTP/2 사용**: Keep-alive 연결
3. **CDN**: 정적 자산 캐싱
4. **압축**: gzip 압축 (SSE는 자동)

**대역폭 최적화:**

- 필요한 필드만 추출
  ```yaml
  output: ${response[].choices[0].delta.content}
  # 전체 response가 아닌 content만
  ```

- JSON 형식 최소화
  ```yaml
  stream_format: text              # JSON보다 가벼움
  ```

### 11.5.5 에러 처리

**재시도 로직:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  max_retries: 3                   # 최대 3회 재시도
  retry_delay: 1                   # 1초 대기
  path: /chat/completions
  body:
    stream: true
```

**타임아웃 처리:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  timeout: 30                      # 30초 타임아웃
  path: /chat/completions
  body:
    stream: true
```

**스트림 중단 처리:**

클라이언트 측에서:
```javascript
const controller = new AbortController();

// 5초 후 자동 중단
setTimeout(() => controller.abort(), 5000);

fetch(url, {
  signal: controller.signal,
  // ...
});
```

---

## 11.6 실전 예제

### 11.6.1 실시간 번역 스트리밍

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Real-time Translation
  output: ${output as text;sse-text}

component:
  type: model
  task: translation
  model: Helsinki-NLP/opus-mt-ko-en
  text: ${input.text as text}
  streaming: true
  params:
    max_output_length: 512
```

### 11.6.2 OpenAI + Claude 조합

```yaml
workflows:
  - id: multi-model-chat
    title: Multi-Model Chat
    output: ${output as text;sse-text}
    jobs:
      - id: openai-response
        component: openai-client
        input:
          prompt: ${input.prompt}
        condition: ${input.model == 'openai'}

      - id: claude-response
        component: claude-client
        input:
          prompt: ${input.prompt}
        condition: ${input.model == 'claude'}

components:
  - id: openai-client
    type: http-client
    base_url: https://api.openai.com/v1
    path: /chat/completions
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt as text}
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}

  - id: claude-client
    type: http-client
    base_url: https://api.anthropic.com/v1
    path: /messages
    headers:
      x-api-key: ${env.ANTHROPIC_API_KEY}
      anthropic-version: "2023-06-01"
    body:
      model: claude-3-5-sonnet-20241022
      messages:
        - role: user
          content: ${input.prompt as text}
      stream: true
    stream_format: json
    output: ${response[].delta.text}
```

### 11.6.3 로컬 모델 스트리밍 서버

```yaml
controller:
  type: http-server
  port: 8080

workflow:
  title: Local Model Streaming
  output: ${output as text;sse-text}

component:
  type: http-server
  start:
    - vllm
    - serve
    - meta-llama/Llama-2-7b-chat-hf
    - --port
    - "8000"
    - --gpu-memory-utilization
    - "0.9"
  port: 8000
  healthcheck:
    path: /health
    interval: 5s
  method: POST
  path: /v1/chat/completions
  body:
    model: llama-2-7b-chat
    messages:
      - role: user
        content: ${input.prompt as text}
    stream: true
    max_tokens: 256
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

---

## 11.7 스트리밍 모범 사례

### 스트리밍 사용 권장사항

**언제 스트리밍을 사용해야 하나요?**

✅ **사용 권장:**
- 긴 응답 (100+ 토큰)
- 실시간 사용자 경험 필요
- 챗봇 및 대화 시스템
- 점진적 결과 표시

❌ **사용 비권장:**
- 짧은 응답 (< 50 토큰)
- 배치 처리
- 백그라운드 작업
- 완전한 응답 필요 시 (분석, 저장 등)

### 성능 최적화 체크리스트

- [ ] `num_beams: 1` 설정 (모델 스트리밍)
- [ ] `do_sample: false` 설정 (빠른 생성)
- [ ] 적절한 `max_output_length` 설정
- [ ] 타임아웃 설정
- [ ] 에러 핸들링 구현
- [ ] 클라이언트 측 중단 로직
- [ ] GPU 사용 (가능한 경우)

### 보안 고려사항

- API 키를 환경 변수로 관리
- HTTPS 사용 (프로덕션)
- 속도 제한 설정
- 입력 검증
- 출력 필터링 (유해 콘텐츠)

---

## 다음 단계

실습해보세요:
- 로컬 모델 스트리밍 테스트
- 외부 API 스트리밍 통합
- Web UI에서 실시간 응답 확인
- 다양한 출력 형식 실험

---

**다음 장**: [12. 변수 바인딩](./12-variable-binding.md)
