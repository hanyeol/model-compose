# 7장: WebSocket 인터페이스

이 장에서는 model-compose의 WebSocket 인터페이스를 사용하여 실시간 태스크 모니터링, 워크플로우 실행 및 양방향 제어를 수행하는 방법을 설명합니다.

---

## 7.1 WebSocket 개요

### 7.1.1 WebSocket 인터페이스란?

WebSocket 인터페이스는 HTTP 서버 컨트롤러에 `/ws` 엔드포인트를 추가하여, 클라이언트와 서버 간 실시간 양방향 통신을 가능하게 합니다. `GET /tasks/{task_id}`를 반복적으로 폴링하는 대신, 태스크 진행에 따라 즉각적인 상태 업데이트를 받을 수 있습니다.

**장점:**
- 실시간 태스크 상태 업데이트 (폴링 불필요)
- 양방향 통신 (서버 푸시 + 클라이언트 명령)
- 상태 변경 및 인터럽트 처리의 낮은 지연 시간
- 단일 지속 연결로 효율적인 리소스 사용
- 하나의 연결로 여러 태스크 동시 모니터링

**사용 사례:**
- 워크플로우 실행을 모니터링하는 실시간 대시보드
- 인터럽트/재개 흐름이 있는 대화형 애플리케이션
- 즉각적인 피드백이 필요한 채팅 애플리케이션
- 단일 클라이언트에서 다중 태스크 모니터링

### 7.1.2 WebSocket vs REST API

두 인터페이스 모두 워크플로우 실행을 지원합니다. 필요에 따라 선택하세요:

| 상황 | 추천 방식 | 이유 |
|------|-----------|------|
| 간단한 배치 작업 | REST API | WebSocket 연결 불필요 |
| 실시간 UI (채팅, 생성 등) | WebSocket | 한 번의 연결로 모든 작업 |
| 외부 시스템 통합 | REST API + WebSocket | 표준 HTTP로 시작, WebSocket으로 모니터링 |
| 여러 태스크 동시 모니터링 | WebSocket | 하나의 연결로 여러 태스크 |
| curl/Postman 테스트 | REST API | 간단한 요청/응답 |

### 7.1.3 전달 보장 수준

WebSocket 인터페이스는 **최신 상태 전달(latest-state delivery)** 만 보장합니다 — 순서 보장된 이벤트 스트림이 아닙니다:

- 구독 시 태스크의 **현재(최신) 상태**를 즉시 수신합니다.
- 이후 상태가 변경될 때 업데이트를 수신하지만, 연결이 열려 있고 전송이 성공한 경우에 한합니다.
- 빠르게 여러 상태 전이가 일어나는 경우(예: 구독 전에 `PENDING → PROCESSING → COMPLETED` 완료), 중간 상태가 유실될 수 있습니다.
- 이는 현재 설계의 의도적인 한계입니다. 모든 상태 전이를 순서대로 캡처해야 하는 경우(이벤트 소싱, 감사 로그 등)는 `GET /tasks/{task_id}` 폴링을 사용하거나 향후 버전을 기다려 주세요.

### 7.1.4 동작 방식

```
클라이언트                        서버
  │                               │
  │──── WebSocket 연결 ──────────>│  ws://localhost:8080/ws
  │<─── 연결 수락 ───────────────│
  │                               │
  │──── run_workflow ────────────>│  워크플로우 실행
  │<─── workflow_started ─────────│  task_id 반환
  │                               │
  │<─── task_state (processing) ──│  실시간 업데이트
  │<─── task_state (interrupted) ─│  인터럽트 알림
  │                               │
  │──── resume_task ─────────────>│  워크플로우 재개
  │<─── task_resumed ─────────────│
  │<─── task_state (completed) ───│  최종 결과
  │                               │
  │──── close ───────────────────>│
```

---

## 7.2 설정

### 7.2.1 WebSocket 활성화

HTTP 서버 컨트롤러 사용 시 WebSocket은 기본적으로 활성화됩니다. 기본 사용에는 추가 설정이 필요 없습니다.

```yaml
controller:
  type: http-server
  port: 8080
```

WebSocket 엔드포인트: `ws://localhost:8080/ws`

### 7.2.2 WebSocket 설정 옵션

`websocket` 필드는 boolean 또는 설정 객체를 받습니다:

- `websocket: true` (기본값) — 기본 설정으로 활성화
- `websocket: false` — WebSocket 비활성화
- `websocket: { ... }` — 상세 설정으로 활성화

```yaml
controller:
  type: http-server
  port: 8080
  origins: "*"
  websocket:
    path: /ws
    max_connections: 100
```

**설정 필드:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `path` | string | `/ws` | WebSocket 엔드포인트 경로 |
| `max_connections` | integer | 무제한 | 최대 동시 WebSocket 연결 수 (best-effort: 연결 수 검사~accept 사이에 소수의 초과가 발생할 수 있음) |
| `ping_interval` | integer | `30` | 서버 측 ping 간격 (초, `0`이면 비활성화) |
| `ping_timeout` | integer | `10` | ping 타임아웃 (초) |

### 7.2.3 설정 예시

#### 개발 환경

```yaml
controller:
  type: http-server
  host: 0.0.0.0
  port: 8080
  origins: "*"
  # WebSocket은 기본 활성화, 추가 설정 불필요
```

#### 프로덕션 환경

```yaml
controller:
  type: http-server
  host: 127.0.0.1
  port: 8080
  origins: "https://app.example.com"
  websocket:
    path: /ws
    max_connections: 100
```

#### WebSocket 비활성화

```yaml
controller:
  type: http-server
  port: 8080
  websocket: false
```

---

## 7.3 WebSocket 연결

### 7.3.1 기본 연결

WebSocket 엔드포인트에 연결합니다:

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  console.log('연결됨');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('수신:', message);
};

ws.onclose = () => {
  console.log('연결 해제');
};
```

```python
import asyncio
import websockets
import json

async def connect():
    async with websockets.connect('ws://localhost:8080/ws') as ws:
        print('연결됨')
        async for message in ws:
            data = json.loads(message)
            print('수신:', data)

asyncio.run(connect())
```

### 7.3.2 세션 ID

쿼리 파라미터로 세션 ID를 지정하여 연결을 식별할 수 있습니다:

```javascript
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:8080/ws?session=${sessionId}`);
```

- 미지정 시 서버가 UUID를 자동 생성합니다.
- 하나의 세션 ID에는 하나의 활성 연결만 가능합니다. 동일 세션 ID로 중복 연결 시 거부됩니다 (close code `4409`).
- 세션 ID는 REST API 통합을 가능하게 합니다 ([7.5절](#75-rest-api-통합) 참조).

### 7.3.3 연결 시 자동 구독

`task` 쿼리 파라미터로 연결과 동시에 태스크를 구독할 수 있습니다:

```javascript
const ws = new WebSocket(`ws://localhost:8080/ws?task=${taskId}`);
```

이는 연결 후 `subscribe_task` 메시지를 보내는 것과 동일합니다.

---

## 7.4 WebSocket 메시지

### 7.4.1 메시지 형식

모든 메시지는 공통 JSON 봉투 구조를 사용합니다:

```json
{
  "type": "message_type",
  "id": "optional_message_id",
  "data": { }
}
```

- `type` (string, 필수): 메시지 타입 식별자
- `id` (string, 선택): 요청-응답 상관관계를 위한 고유 메시지 ID
- `data` (object, 메시지 타입에 따라 선택): 메시지별 페이로드. `ping` 등 페이로드가 불필요한 메시지에서는 생략 가능하며, 서버는 `data`가 없으면 빈 `{}`로 처리합니다.

### 7.4.2 클라이언트 → 서버 메시지

#### `run_workflow` — 워크플로우 실행

```json
{
  "type": "run_workflow",
  "id": "msg-001",
  "data": {
    "workflow_id": "chat-completion",
    "input": {
      "prompt": "안녕하세요!"
    },
    "subscribe_task": true
  }
}
```

**필드:**
- `workflow_id` (string, 선택): 실행할 워크플로우 (기본값: `__default__`)
- `input` (object, 선택): 워크플로우 입력 파라미터
- `subscribe_task` (boolean, 기본값: `true`): 태스크 상태 업데이트 자동 구독

**응답:** `workflow_started` 메시지. `subscribe_task`가 `true`이면 `task_state` 업데이트도 수신됩니다.

#### `subscribe_task` — 태스크 상태 구독

```json
{
  "type": "subscribe_task",
  "id": "msg-002",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**필드:**
- `task_id` (string, 필수): 모니터링할 태스크 ID (ULID 형식)

**응답:** 현재 상태를 포함한 `task_subscribed` 메시지 후, 상태 변경 시 `task_state` 업데이트.

#### `unsubscribe_task` — 태스크 구독 해제

```json
{
  "type": "unsubscribe_task",
  "id": "msg-003",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**응답:** `task_unsubscribed` 메시지.

#### `resume_task` — 중단된 태스크 재개

`POST /tasks/{task_id}/resume`의 WebSocket 버전입니다.

```json
{
  "type": "resume_task",
  "id": "msg-004",
  "data": {
    "task_id": "01HXYZ...",
    "job_id": "review-step",
    "answer": {
      "approved": true
    }
  }
}
```

**필드:**
- `task_id` (string, 필수): 재개할 태스크 ID
- `job_id` (string, 필수): 중단된 작업 ID (`interrupt.job_id`)
- `answer` (any, 선택): 워크플로우에 전달할 응답 값

**응답:** `task_resumed` 또는 `error` 메시지.

#### `get_task` — 태스크 상태 조회 (1회성)

```json
{
  "type": "get_task",
  "id": "msg-005",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**응답:** 현재 상태를 포함한 `task_state` 메시지. 구독을 생성하지 않습니다.

#### `ping` — 연결 헬스 체크

```json
{
  "type": "ping",
  "id": "msg-006"
}
```

**응답:** `pong` 메시지.

### 7.4.3 서버 → 클라이언트 메시지

#### `workflow_started` — 워크플로우 실행 시작

```json
{
  "type": "workflow_started",
  "id": "msg-001",
  "data": {
    "task_id": "01HXYZ...",
    "workflow_id": "chat-completion",
    "status": "pending"
  }
}
```

`run_workflow`에 대한 응답으로 전송됩니다.

#### `task_subscribed` — 구독 확인

```json
{
  "type": "task_subscribed",
  "id": "msg-002",
  "data": {
    "task_id": "01HXYZ...",
    "current_state": {
      "task_id": "01HXYZ...",
      "status": "processing",
      "output": null,
      "error": null,
      "interrupt": null
    }
  }
}
```

`subscribe_task`에 대한 응답으로, 구독 시점의 현재 태스크 상태를 포함합니다.

#### `task_unsubscribed` — 구독 해제 확인

```json
{
  "type": "task_unsubscribed",
  "id": "msg-003",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

#### `task_state` — 태스크 상태 업데이트

```json
{
  "type": "task_state",
  "data": {
    "task_id": "01HXYZ...",
    "status": "interrupted",
    "output": null,
    "error": null,
    "interrupt": {
      "job_id": "review-step",
      "phase": "before",
      "message": "승인이 필요합니다",
      "metadata": { "cost": 0.5 }
    },
    "timestamp": "2026-02-06T12:34:56.789Z"
  }
}
```

**필드:**
- `status`: `"pending"` | `"processing"` | `"interrupted"` | `"completed"` | `"failed"`
- `output`: 완료 시 결과 데이터 (JSON 직렬화 가능한 값만. 이미지 등 직렬화 불가한 출력은 `null`)
- `error`: 실패 시 에러 메시지
- `interrupt`: `"interrupted"` 상태일 때 인터럽트 상세 정보 (`job_id`, `phase`, `message`, `metadata`)
- `timestamp`: 상태 변경 시각 (ISO 8601)

#### `task_resumed` — 태스크 재개 확인

```json
{
  "type": "task_resumed",
  "id": "msg-004",
  "data": {
    "task_id": "01HXYZ...",
    "status": "processing"
  }
}
```

`resume_task` 성공 시 전송됩니다.

#### `error` — 오류 메시지

```json
{
  "type": "error",
  "id": "msg-001",
  "data": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "워크플로우 'invalid-workflow'를 찾을 수 없습니다",
    "details": {
      "workflow_id": "invalid-workflow"
    }
  }
}
```

**오류 코드:**

| 코드 | 설명 |
|------|------|
| `WORKFLOW_NOT_FOUND` | 지정된 워크플로우가 존재하지 않음 |
| `TASK_NOT_FOUND` | 지정된 태스크가 존재하지 않음 |
| `INVALID_REQUEST` | 잘못된 메시지 형식 또는 필수 필드 누락 |
| `TASK_NOT_INTERRUPTED` | 태스크가 interrupted 상태가 아님 |
| `JOB_ID_MISMATCH` | job_id가 현재 인터럽트 지점과 불일치 |
| `INTERNAL_ERROR` | 예기치 않은 서버 오류 |

#### `pong` — Ping 응답

```json
{
  "type": "pong",
  "id": "msg-006",
  "data": {
    "timestamp": "2026-02-06T12:34:56.789Z"
  }
}
```

---

## 7.5 REST API 통합

WebSocket과 REST API를 함께 사용할 수 있습니다. REST로 워크플로우를 시작하고 WebSocket으로 실시간 모니터링하고 싶을 때 유용합니다.

### 7.5.1 `subscribe_task` 파라미터

`POST /workflows/runs` 엔드포인트에서 `subscribe_task` 파라미터를 지원합니다:

```bash
curl -X POST "http://localhost:8080/workflows/runs?session_id=my-session-id" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat-completion",
    "input": { "prompt": "안녕하세요" },
    "wait_for_completion": false,
    "subscribe_task": true
  }'
```

**요구사항:**
- `subscribe_task: true` 시 `session_id` query parameter 필수
- 해당 세션 ID의 활성 WebSocket 연결이 존재해야 함
- `wait_for_completion`은 `false`여야 함 (둘 다 `true`는 400 에러 반환)

### 7.5.2 `wait_for_completion`과 `subscribe_task` 조합

| wait_for_completion | subscribe_task | 동작 |
|---------------------|----------------|------|
| `true` (기본) | `false` (기본) | HTTP 응답이 완료까지 대기. 구독 없음. (기존 동작) |
| `false` | `false` | 즉시 PENDING 상태 반환. 구독 없음. |
| `false` | `true` | 즉시 PENDING 반환 + WebSocket 자동 구독. **권장 패턴** |
| `true` | `true` | **비허용.** 400 Bad Request 반환. |

### 7.5.3 패턴: WebSocket 먼저 연결 + REST 실행

REST + WebSocket 통합의 권장 패턴:

```javascript
// 1. 세션 ID 생성 및 WebSocket 연결
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:8080/ws?session=${sessionId}`);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'task_state') {
    console.log('상태:', msg.data.status);
    if (msg.data.status === 'completed') {
      console.log('결과:', msg.data.output);
    }
  }
};

// 2. REST API로 워크플로우 실행 (같은 세션 ID 사용)
ws.onopen = async () => {
  const response = await fetch(`/workflows/runs?session_id=${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflow_id: 'chat-completion',
      input: { prompt: '안녕하세요' },
      wait_for_completion: false,
      subscribe_task: true
    })
  });

  const { task_id } = await response.json();
  console.log('워크플로우 시작:', task_id);
  // WebSocket으로 자동으로 업데이트가 수신됩니다
};
```

---

## 7.6 사용 패턴

### 7.6.1 패턴 1: WebSocket으로 실행 및 모니터링

가장 간단한 패턴 — 단일 WebSocket 연결로 워크플로우를 실행하고 업데이트를 수신합니다.

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'run_workflow',
    id: 'msg-001',
    data: {
      workflow_id: 'chat-completion',
      input: { prompt: '안녕하세요!' },
      subscribe_task: true
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'workflow_started':
      console.log('시작:', msg.data.task_id);
      break;

    case 'task_state':
      console.log('상태:', msg.data.status);
      if (msg.data.status === 'completed') {
        console.log('출력:', msg.data.output);
        ws.close();
      }
      break;

    case 'error':
      console.error('에러:', msg.data.message);
      break;
  }
};
```

```python
import asyncio
import websockets
import json

async def run_and_monitor():
    async with websockets.connect('ws://localhost:8080/ws') as ws:
        # 워크플로우 실행
        await ws.send(json.dumps({
            'type': 'run_workflow',
            'id': 'msg-001',
            'data': {
                'workflow_id': 'chat-completion',
                'input': {'prompt': '안녕하세요!'},
                'subscribe_task': True
            }
        }))

        # 업데이트 수신
        async for message in ws:
            msg = json.loads(message)

            if msg['type'] == 'workflow_started':
                print(f"시작: {msg['data']['task_id']}")

            elif msg['type'] == 'task_state':
                status = msg['data']['status']
                print(f"상태: {status}")
                if status == 'completed':
                    print(f"출력: {msg['data']['output']}")
                    break
                elif status == 'failed':
                    print(f"에러: {msg['data']['error']}")
                    break

asyncio.run(run_and_monitor())
```

### 7.6.2 패턴 2: 대화형 인터럽트/재개

사람이 개입하는 인터럽트 포인트가 있는 워크플로우를 처리합니다.

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'run_workflow',
    id: 'msg-001',
    data: {
      workflow_id: 'content-review',
      input: { text: 'AI에 관한 블로그 글을 작성해주세요' },
      subscribe_task: true
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'task_state' && msg.data.status === 'interrupted') {
    const interrupt = msg.data.interrupt;
    console.log(`작업 '${interrupt.job_id}'에서 인터럽트: ${interrupt.message}`);

    // 인터럽트에 응답
    ws.send(JSON.stringify({
      type: 'resume_task',
      id: 'msg-002',
      data: {
        task_id: msg.data.task_id,
        job_id: interrupt.job_id,
        answer: { approved: true }
      }
    }));
  }

  if (msg.type === 'task_state' && msg.data.status === 'completed') {
    console.log('최종 출력:', msg.data.output);
    ws.close();
  }
};
```

### 7.6.3 패턴 3: 기존 태스크 구독

REST API나 다른 클라이언트에서 시작된 태스크를 모니터링합니다.

```javascript
// 1. REST API로 워크플로우 실행
const response = await fetch('/workflows/runs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    workflow_id: 'batch-processing',
    input: { data: '...' },
    wait_for_completion: false
  })
});

const { task_id } = await response.json();

// 2. 나중에 WebSocket 연결하여 구독
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe_task',
    id: 'msg-001',
    data: { task_id }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'task_subscribed') {
    console.log('현재 상태:', msg.data.current_state.status);
  }
  if (msg.type === 'task_state') {
    console.log('업데이트:', msg.data.status);
  }
};
```

### 7.6.4 패턴 4: 다중 태스크 대시보드

단일 WebSocket 연결로 여러 태스크를 모니터링합니다.

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
const tasks = {};

ws.onopen = async () => {
  // 여러 워크플로우 시작
  for (const workflow of ['translate', 'summarize', 'classify']) {
    ws.send(JSON.stringify({
      type: 'run_workflow',
      id: `run-${workflow}`,
      data: {
        workflow_id: workflow,
        input: { text: '입력 텍스트' },
        subscribe_task: true
      }
    }));
  }
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'workflow_started') {
    tasks[msg.data.task_id] = { workflow: msg.data.workflow_id, status: 'pending' };
    console.log(`[${msg.data.workflow_id}] 시작: ${msg.data.task_id}`);
  }

  if (msg.type === 'task_state') {
    const task = tasks[msg.data.task_id];
    if (task) {
      task.status = msg.data.status;
      console.log(`[${task.workflow}] ${msg.data.status}`);

      if (msg.data.status === 'completed') {
        task.output = msg.data.output;
      }
    }

    // 모든 태스크 완료 확인
    const allDone = Object.values(tasks).every(
      t => t.status === 'completed' || t.status === 'failed'
    );
    if (allDone) {
      console.log('모든 태스크 완료:', tasks);
      ws.close();
    }
  }
};
```

---

## 7.7 연결 관리

### 7.7.1 세션과 재연결

- 각 WebSocket 연결은 세션 ID로 식별됩니다 (자동 생성 또는 `?session=`으로 지정).
- 연결이 끊기면 이전 연결이 완전히 종료된 후 같은 세션 ID로 재연결할 수 있습니다.
- 새 세션을 만들려면 `?session=` 파라미터를 생략하거나 새 UUID를 사용하세요.

### 7.7.2 연결 라이프사이클

WebSocket 연결이 종료되면:
- 해당 클라이언트의 모든 태스크 구독이 자동 해제됩니다.
- 실행 중인 워크플로우는 **영향을 받지 않습니다** — WebSocket은 모니터링/제어 채널이며, 워크플로우 실행과는 독립적입니다.
- 클라이언트는 재연결하여 다시 구독할 수 있습니다.

### 7.7.3 연결 제한

`max_connections`가 설정되어 있고 한도에 도달하면, 새 연결은 close code `4429` (Too Many Connections)로 거부됩니다.

```yaml
controller:
  type: http-server
  websocket:
    max_connections: 50  # 50개 초과 연결 거부
```

### 7.7.4 Ping을 통한 연결 유지

`ping` 메시지로 연결이 활성 상태인지 확인합니다:

```javascript
// 30초마다 ping 전송
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping', id: 'heartbeat' }));
  }
}, 30000);
```

---

## 7.8 보안 고려사항

### 7.8.1 세션 ID 보안

세션 ID (`?session=` 및 `?session_id=`)는 인증 메커니즘이 아닙니다:
- 세션 ID를 아는 누구나 해당 세션의 WebSocket에 REST 구독을 연결할 수 있습니다.
- 신뢰할 수 없는 네트워크 환경에서는 애플리케이션 수준의 토큰 기반 인증 추가를 고려하세요.

### 7.8.2 CORS와 Origins

컨트롤러 설정의 `origins` 설정은 브라우저에서의 WebSocket 연결에 적용됩니다:

```yaml
controller:
  type: http-server
  origins: "https://app.example.com"  # 브라우저 origins 제한
```

참고: 이는 브라우저에서 시작된 연결에만 적용됩니다. 서버 간 WebSocket 연결은 CORS 제한을 받지 않습니다.

### 7.8.3 프로덕션 권장사항

- 리버스 프록시를 통한 WSS (WebSocket over TLS) 사용
- 신뢰할 수 있는 도메인으로 origins 제한
- 리소스 고갈 방지를 위한 `max_connections` 설정
- 애플리케이션 수준 인증 추가 고려

**WebSocket용 Nginx 리버스 프록시:**

```nginx
server {
    listen 443 ssl;
    server_name app.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /ws {
        proxy_pass http://127.0.0.1:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;  # 연결 유지
    }
}
```

---

## 7.9 모범 사례

### 1. 실시간 모니터링에는 `subscribe_task: true` 사용

WebSocket으로 워크플로우를 실행할 때, 자동 업데이트를 받으려면 항상 `subscribe_task: true`를 설정하세요:

```json
{
  "type": "run_workflow",
  "data": {
    "workflow_id": "my-workflow",
    "subscribe_task": true
  }
}
```

### 2. 모든 메시지 타입 처리

항상 `error` 메시지와 예상치 못한 상태에 대한 핸들러를 포함하세요:

```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'workflow_started':
    case 'task_state':
    case 'task_subscribed':
    case 'task_resumed':
      // 정상 처리
      break;
    case 'error':
      console.error(`[${msg.data.code}] ${msg.data.message}`);
      break;
    default:
      console.warn('알 수 없는 메시지 타입:', msg.type);
  }
};
```

### 3. 재연결 로직 구현

WebSocket 연결은 끊어질 수 있습니다. 지수 백오프 재연결을 구현하세요:

```javascript
function connectWithRetry(url, maxRetries = 5) {
  let retries = 0;

  function connect() {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      retries = 0; // 성공 시 초기화
      // 필요시 태스크 재구독
    };

    ws.onclose = () => {
      if (retries < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retries), 30000);
        retries++;
        console.log(`${delay}ms 후 재연결...`);
        setTimeout(connect, delay);
      }
    };

    return ws;
  }

  return connect();
}
```

### 4. 메시지 ID로 상관관계 설정

요청 메시지에 `id`를 포함하여 응답과 매칭하세요:

```javascript
const msgId = `msg-${Date.now()}`;
ws.send(JSON.stringify({
  type: 'run_workflow',
  id: msgId,
  data: { workflow_id: 'my-workflow' }
}));

// 응답에 동일한 id가 포함됩니다
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id === msgId && msg.type === 'workflow_started') {
    // 우리의 특정 요청에 대한 응답
  }
};
```

### 5. 완료 시 구독 해제

완료된 태스크의 구독을 해제하여 연결을 깔끔하게 유지하세요:

```javascript
if (msg.data.status === 'completed' || msg.data.status === 'failed') {
  ws.send(JSON.stringify({
    type: 'unsubscribe_task',
    data: { task_id: msg.data.task_id }
  }));
}
```

---

## 다음 단계

다음을 시도해 보세요:
- WebSocket 엔드포인트에 연결하여 워크플로우 실행
- 실시간 모니터링 대시보드 구축
- 대화형 인터럽트/재개 흐름 처리
- REST API와 WebSocket을 결합한 하이브리드 아키텍처

---

**이전 장**: [6. 컨트롤러 구성](./06-controller-configuration.md) | **다음 장**: [8. Web UI 구성](./08-webui-configuration.md)
