# 6장: 컨트롤러 구성

이 장에서는 model-compose의 컨트롤러를 구성하는 방법을 다룹니다. HTTP 서버, MCP 서버 설정과 동시 실행 제어, 포트 및 경로 관리를 학습합니다.

---

## 6.1 HTTP 서버

HTTP 서버 컨트롤러는 워크플로우를 REST API로 노출합니다.

### 기본 구조

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
```

### 예제: 간단한 챗봇 API

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api

workflow:
  title: Chat with AI
  description: Generate text responses using AI
  input: ${input}
  output: ${output}

component:
  type: http-client
  base_url: https://api.openai.com/v1
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
    message: ${response.choices[0].message.content}
```

### API 엔드포인트

HTTP 서버 컨트롤러는 다음 엔드포인트를 자동으로 생성합니다:

#### 워크플로우 목록 조회
```
GET /api/workflows
GET /api/workflows?include_schema=true
```

워크플로우 목록을 조회합니다. `include_schema=true` 파라미터를 추가하면 각 워크플로우의 입출력 스키마도 함께 반환됩니다.

요청 예시:
```bash
curl http://localhost:8080/api/workflows
```

응답 예시:
```json
[
  {
    "workflow_id": "chat",
    "title": "Chat with AI",
    "default": true
  }
]
```

스키마 포함 요청 예시:
```bash
curl http://localhost:8080/api/workflows?include_schema=true
```

응답 예시:
```json
[
  {
    "workflow_id": "chat",
    "title": "Chat with AI",
    "description": "Generate text responses using AI",
    "input": [
      {
        "name": "prompt",
        "type": "string"
      }
    ],
    "output": [
      {
        "name": "message",
        "type": "string"
      }
    ],
    "default": true
  }
]
```

#### 워크플로우 스키마 조회
```
GET /api/workflows/{workflow_id}/schema
```

특정 워크플로우의 입출력 스키마를 조회합니다.

요청 예시:
```bash
curl http://localhost:8080/api/workflows/chat/schema
```

응답 예시:
```json
{
  "workflow_id": "chat",
  "title": "Chat with AI",
  "description": "Generate text responses using AI",
  "input": [
    {
      "name": "prompt",
      "type": "string"
    }
  ],
  "output": [
    {
      "name": "message",
      "type": "string"
    }
  ],
  "default": true
}
```

#### 워크플로우 실행
```
POST /api/workflows/runs
```

워크플로우를 실행합니다. `wait_for_completion` 파라미터로 동기/비동기 실행을 제어할 수 있습니다.

요청 본문 파라미터:
- `workflow_id` (string, optional): 실행할 워크플로우 ID. 생략하면 default 워크플로우 실행
- `input` (object, optional): 워크플로우 입력 데이터
- `wait_for_completion` (boolean, default: true): true면 완료될 때까지 대기, false면 즉시 task_id 반환
- `output_only` (boolean, default: false): true면 출력 데이터만 반환 (wait_for_completion=true 필요)

##### 동기 실행 (기본)

완료될 때까지 대기하고 결과를 반환합니다.

요청 예시:
```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat",
    "input": {
      "prompt": "Hello, AI!"
    },
    "wait_for_completion": true
  }'
```

응답 예시:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "completed",
  "output": {
    "message": "Hello! How can I help you today?"
  }
}
```

##### output_only 모드

`output_only: true`를 설정하면 task 메타데이터 없이 출력 데이터만 반환합니다.

요청 예시:
```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat",
    "input": {
      "prompt": "Hello, AI!"
    },
    "wait_for_completion": true,
    "output_only": true
  }'
```

응답 예시:
```json
{
  "message": "Hello! How can I help you today?"
}
```

##### 비동기 실행

`wait_for_completion: false`로 설정하면 즉시 task_id를 반환하고 백그라운드에서 실행됩니다.

요청 예시:
```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat",
    "input": {
      "prompt": "Hello, AI!"
    },
    "wait_for_completion": false
  }'
```

응답 예시:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "pending"
}
```

#### Task 상태 조회
```
GET /api/tasks/{task_id}
GET /api/tasks/{task_id}?output_only=true
```

비동기로 실행한 워크플로우의 상태와 결과를 조회합니다.

Task 상태:
- `pending`: 대기 중 (아직 실행되지 않음)
- `processing`: 실행 중
- `completed`: 성공적으로 완료됨
- `failed`: 실행 중 오류 발생

요청 예시:
```bash
curl http://localhost:8080/api/tasks/01JBQR5KSXM8HNXF7N9VYW3K2T
```

실행 중인 경우 응답:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "processing"
}
```

완료된 경우 응답:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "completed",
  "output": {
    "message": "Hello! How can I help you today?"
  }
}
```

실패한 경우 응답:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "failed",
  "error": "Connection timeout"
}
```

output_only 모드:
```bash
curl http://localhost:8080/api/tasks/01JBQR5KSXM8HNXF7N9VYW3K2T?output_only=true
```

완료되지 않은 경우 HTTP 202 반환:
```
HTTP/1.1 202 Accepted
{"detail": "Task is still in progress."}
```

완료된 경우 출력만 반환:
```json
{
  "message": "Hello! How can I help you today?"
}
```

실패한 경우 HTTP 500 반환:
```
HTTP/1.1 500 Internal Server Error
{"detail": "Connection timeout"}
```

#### Health Check
```
GET /api/health
```

서버 상태를 확인합니다.

응답 예시:
```json
{
  "status": "ok"
}
```

### 비동기 실행과 Task 큐

#### Task 생성과 추적

워크플로우를 실행하면 내부적으로 Task가 생성됩니다:

1. **Task 생성**: 워크플로우 실행 시 ULID 기반의 고유한 `task_id`가 생성됩니다
2. **Task 상태 추적**: Task는 4가지 상태(`pending`, `processing`, `completed`, `failed`)를 가집니다
3. **Task 캐싱**: 완료된 Task는 1시간 동안 메모리에 캐시되어 `/api/tasks/{task_id}` 엔드포인트로 조회 가능합니다

#### 동기 vs 비동기 실행

**동기 실행** (`wait_for_completion: true`, 기본값):
- 워크플로우가 완료될 때까지 HTTP 요청이 대기합니다
- 완료 즉시 결과를 반환합니다
- 간단한 워크플로우나 즉시 결과가 필요한 경우 사용

**비동기 실행** (`wait_for_completion: false`):
- 즉시 `task_id`를 반환하고 연결을 종료합니다
- 백그라운드에서 워크플로우가 실행됩니다
- 이후 `/api/tasks/{task_id}` 엔드포인트로 상태와 결과를 조회합니다
- 긴 실행 시간이 예상되는 워크플로우에 적합합니다

### CORS 설정

HTTP 서버의 CORS는 `origins` 필드로 제어합니다.

```yaml
controller:
  type: http-server
  origins: "https://example.com,https://app.example.com"  # 특정 도메인만 허용
  # origins: "*"  # 모든 도메인 허용 (기본값, 개발 환경용)
```

---

## 6.2 MCP 서버

MCP (Model Context Protocol) 서버 컨트롤러는 Streamable HTTP 방식으로 Claude Desktop 및 다른 MCP 클라이언트와 통합할 수 있습니다.

### 기본 구조

```yaml
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp  # Streamable HTTP 엔드포인트 경로
```

### 예제: 콘텐츠 모더레이션 도구

```yaml
controller:
  type: mcp-server
  base_path: /mcp
  port: 8080

workflows:
  - id: moderate-text
    title: Moderate Text Content
    description: Check if text content violates content policies
    action: text-moderation
    input:
      text: ${input.text}
    output: ${output}

  - id: moderate-image
    title: Moderate Image Content
    description: Check if image content is safe and appropriate
    action: image-moderation
    input:
      image_url: ${input.image_url}
    output: ${output}

components:
  - id: openai-moderation
    type: http-client
    base_url: https://api.openai.com/v1
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    actions:
      - id: text-moderation
        path: /moderations
        method: POST
        body:
          input: ${input.text}
        output:
          flagged: ${response.results[0].flagged}
          categories: ${response.results[0].categories}
          scores: ${response.results[0].category_scores}

      - id: image-moderation
        path: /moderations
        method: POST
        body:
          input: ${input.image_url}
          model: omni-moderation-latest
        output:
          flagged: ${response.results[0].flagged}
          categories: ${response.results[0].categories}
```

### MCP 워크플로우 특징

MCP 서버에서 워크플로우는 다음과 같은 특징이 있습니다:

- **title**: MCP 클라이언트에 표시되는 도구 이름
- **description**: 도구 설명 (MCP 클라이언트에서 표시)
- **action**: 연결할 컴포넌트 액션 ID
- **input**: 도구의 입력 파라미터 정의

### MCP 클라이언트 연동

model-compose의 MCP 서버는 **Streamable HTTP** 프로토콜(MCP 사양 2025-03-26)을 사용합니다.

**Streamable HTTP의 특징**:
- **단일 엔드포인트**: 하나의 HTTP 엔드포인트로 모든 MCP 통신 처리
- **양방향 통신**: 서버가 클라이언트에게 알림과 요청을 보낼 수 있음
- **SSE 지원**: 선택적으로 Server-Sent Events를 사용하여 스트리밍 응답 가능
- **세션 관리**: `Mcp-Session-Id` 헤더를 통한 세션 추적

> **참고**: Streamable HTTP는 이전의 HTTP+SSE 방식(2024-11-05 사양)을 대체합니다. 단일 엔드포인트와 향상된 양방향 통신을 제공합니다.

#### 서버 시작

```bash
model-compose up -f model-compose.yml
```

서버가 시작되면 다음 URL로 MCP 서버에 접근할 수 있습니다:
```
http://localhost:8080/mcp
```

#### 클라이언트 연결

Streamable HTTP를 지원하는 MCP 클라이언트에서 위 URL로 연결할 수 있습니다.

**연결 정보**:
- URL: `http://localhost:8080/mcp` (또는 설정한 host:port와 base_path)
- Transport: Streamable HTTP
- Protocol Version: 2025-03-26

**프로덕션 환경**:

프로덕션 환경에서 MCP 서버를 외부에 노출할 때는 HTTPS를 사용하는 것이 권장됩니다. Nginx나 Caddy 같은 리버스 프록시를 통해 SSL/TLS를 적용할 수 있습니다.

```yaml
# model-compose는 로컬에서 HTTP로 실행
controller:
  type: mcp-server
  host: 127.0.0.1
  port: 8080
  base_path: /mcp
```

Nginx 리버스 프록시 설정 예시:
```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp {
        proxy_pass http://127.0.0.1:8080/mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 스트리밍 지원
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

MCP 클라이언트는 다음 URL로 연결합니다:
```
https://mcp.example.com/mcp
```

---

## 6.3 동시 실행 제어

`max_concurrent_count` 설정은 HTTP 서버와 MCP 서버 모두에서 사용 가능하며, 컨트롤러 레벨에서 동시에 실행할 수 있는 워크플로우 수를 제한합니다.

### 기본 설정

```yaml
controller:
  type: http-server  # 또는 mcp-server
  max_concurrent_count: 5  # 최대 5개 동시 실행으로 제한
```

### 동작 방식

- `max_concurrent_count: 0` (기본값): 무제한 동시 실행, Task 큐 비활성화
- `max_concurrent_count: 1`: 한 번에 하나의 워크플로우만 실행 (순차 실행)
- `max_concurrent_count: N` (N > 1): 최대 N개까지 동시 실행, 초과 시 큐에서 대기

Task 큐가 활성화되면 (`max_concurrent_count > 0`):
1. 새 워크플로우 실행 요청이 큐에 추가됩니다
2. 최대 `max_concurrent_count`개의 Worker가 큐에서 Task를 가져와 실행합니다
3. `wait_for_completion: true`인 경우에도 큐에서 대기하다가 실행됩니다

### 사용 사례

```yaml
# 기본 설정: 무제한
controller:
  type: http-server
  max_concurrent_count: 0

# GPU 리소스 제한이 필요한 경우
controller:
  type: http-server
  max_concurrent_count: 3  # 전체 워크플로우 실행을 3개로 제한
```

### 컨트롤러 vs 컴포넌트 레벨 제어

동시 실행 제어는 두 가지 레벨에서 가능합니다:

**컨트롤러 레벨** (`controller.max_concurrent_count`):
- 전체 워크플로우 실행 수를 제한합니다
- 모든 워크플로우에 공통으로 적용됩니다
- 전체 시스템 리소스(CPU, 메모리)를 보호할 때 사용합니다

**컴포넌트 레벨** (`component.max_concurrent_count`):
- 특정 컴포넌트의 동시 호출 수를 제한합니다
- 컴포넌트별로 독립적으로 설정 가능합니다
- GPU, 외부 API rate limit 등 특정 리소스를 보호할 때 사용합니다

예시:
```yaml
controller:
  type: http-server
  max_concurrent_count: 0  # 워크플로우 실행은 무제한

components:
  - id: image-model
    type: model
    max_concurrent_count: 2  # GPU 메모리 제한으로 2개만 동시 실행
    model: stabilityai/stable-diffusion-2-1
    task: text-to-image

  - id: openai-api
    type: http-client
    max_concurrent_count: 10  # API rate limit 고려하여 10개로 제한
    base_url: https://api.openai.com/v1
```

**권장 사항**:
- 일반적으로 컴포넌트 레벨에서만 제어하는 것이 더 세밀한 리소스 관리가 가능합니다
- 컨트롤러 레벨 제어는 전체 시스템 과부하를 방지해야 할 때만 사용합니다
- 두 레벨 모두 설정된 경우, 양쪽 제한이 모두 적용됩니다

---

## 6.4 포트 및 호스트 설정

### 호스트 (host)

컨트롤러가 바인딩할 네트워크 인터페이스를 지정합니다.

#### 로컬호스트에서만 접근 허용 (기본값)

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # 기본값
  port: 8080       # 기본값
```

- 같은 머신에서만 접근 가능
- 리버스 프록시 뒤에서 실행하거나 보안이 중요한 경우 사용

#### 모든 인터페이스에서 접근 허용

```yaml
controller:
  type: http-server
  host: 0.0.0.0
  port: 8080
```

- 외부에서 접근 가능
- 개발 환경 또는 네트워크에 노출할 때 사용

### 포트 (port)

컨트롤러 API 서버가 사용할 포트를 지정합니다.

```yaml
controller:
  type: http-server
  port: 8080
```

### 기본 경로 (base_path)

모든 API 엔드포인트의 접두사를 설정합니다.

#### 기본 경로 없음 (기본값)

```yaml
controller:
  type: http-server
  port: 8080
  # base_path 없음
```

엔드포인트:
- `POST /workflows/runs`
- `GET /workflows`
- `GET /tasks/{task_id}`

#### 기본 경로 지정

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
```

엔드포인트:
- `POST /api/workflows/runs`
- `GET /api/workflows`
- `GET /api/tasks/{task_id}`

### 리버스 프록시 설정

Nginx나 Caddy 같은 리버스 프록시 뒤에서 실행하는 경우입니다.

#### model-compose 설정

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # 프록시에서만 접근
  port: 8080
  base_path: /ai   # 프록시 경로와 일치
```

#### Nginx 설정 예시

```nginx
server {
    listen 80;
    server_name example.com;

    location /ai/ {
        proxy_pass http://127.0.0.1:8080/ai/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

이제 외부에서 `http://example.com/ai/workflows/runs`로 접속하면, Nginx가 이를 내부의 `http://127.0.0.1:8080/ai/workflows/runs`로 전달합니다.

---

## 6.5 컨트롤러 모범 사례

### 1. 환경별 포트 설정

개발, 스테이징, 프로덕션 환경에 따라 다른 포트 사용:

```yaml
controller:
  type: http-server
  port: ${env.PORT | 8080}  # 환경 변수 또는 기본값 8080
  base_path: /api
```

### 2. CORS 적절히 설정

프로덕션에서는 특정 도메인만 허용:

```yaml
# 개발 환경
controller:
  type: http-server
  origins: "*"

# 프로덕션 환경
controller:
  type: http-server
  origins: "https://app.example.com,https://admin.example.com"
```

### 3. 동시 실행 제한 설정

리소스 사용량에 맞게 적절한 `max_concurrent_count` 설정:

```yaml
# GPU 사용 워크플로우 - 제한적 동시 실행
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 2  # GPU 메모리 제한 고려

# 가벼운 API 호출 워크플로우 - 많은 동시 실행
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 20
```

### 4. 비동기 실행 활용

긴 실행 시간이 예상되는 워크플로우는 비동기로 실행:

```javascript
// 클라이언트 코드 예시
async function runLongWorkflow(input) {
  // 1. 비동기로 워크플로우 시작
  const response = await fetch('/api/workflows/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflow_id: 'long-task',
      input: input,
      wait_for_completion: false
    })
  });

  const { task_id } = await response.json();

  // 2. 폴링으로 상태 확인
  while (true) {
    const taskResponse = await fetch(`/api/tasks/${task_id}`);
    const task = await taskResponse.json();

    if (task.status === 'completed') {
      return task.output;
    } else if (task.status === 'failed') {
      throw new Error(task.error);
    }

    await new Promise(resolve => setTimeout(resolve, 2000)); // 2초 대기
  }
}
```

### 5. 적절한 base_path 사용

리버스 프록시 뒤에서 실행할 때 base_path를 일관되게 설정:

```yaml
controller:
  type: http-server
  host: 127.0.0.1
  port: 8080
  base_path: /ai-service  # 프록시 경로와 정확히 일치
```

### 6. output_only 활용

API 응답 크기를 줄이고 싶을 때 `output_only` 사용:

```yaml
# 클라이언트에서 task_id가 불필요한 경우
POST /api/workflows/runs
{
  "workflow_id": "simple-chat",
  "input": { "prompt": "Hello" },
  "wait_for_completion": true,
  "output_only": true
}

# 응답: task_id, status 없이 출력만 반환
{ "message": "Hello! How can I help?" }
```

---

## 다음 단계

실습해보세요:
- HTTP 서버로 REST API 구축
- MCP 서버로 Streamable HTTP 서버 구축
- 비동기 실행과 Task 상태 조회 활용
- 리버스 프록시 뒤에서 실행

---

**다음 장**: [7. Web UI 구성](./07-webui-configuration.md)
