# SGLang Chat Completion 스트리밍 예제

이 예제는 내장 **SGLang** 드라이버로 **토큰 단위 스트리밍** chat completion을 수행하는 방법을 보여줍니다. 토큰이 생성되는 대로 점진적으로 방출되므로 클라이언트는 전체 응답을 기다리지 않고 즉시 출력을 볼 수 있습니다.

## 개요

이 워크플로우는 스트리밍을 활성화하는 두 가지 변경을 제외하면 `../sglang/`과 동일합니다:

1. **action의 `streaming: true`** — 드라이버가 최종 문자열 대신 점진적 iterator를 반환합니다.
2. **job의 `output: ${output as stream/text}`** — 워크플로우가 청크들을 집계하지 않고 텍스트 스트림으로 전달합니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 `PATH`에서 사용 가능
- SGLang은 CUDA GPU가 필요 (Linux + NVIDIA)
- 스트리밍 응답을 소비할 수 있는 HTTP 클라이언트 (예: `curl -N`)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/chat-completion/sglang-stream
   ```

2. 첫 실행 시 컴포넌트가 `.venv/sglang`을 구성하고 SGLang을 설치한 뒤 Qwen 모델을 다운로드합니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행 (스트리밍):**

   **API 사용 (`curl -N`은 버퍼링을 비활성화):**
   ```bash
   curl -N -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "system_prompt": "You are a helpful AI assistant.",
         "user_prompt": "Explain quantum computing in simple terms."
       }
     }'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 토큰이 스트리밍되면서 출력 영역에 점진적으로 표시됩니다.

## 컴포넌트 상세

### Chat Completion 모델 컴포넌트 (SGLang, 스트리밍)
- **타입**: `model` 컴포넌트, `task: chat-completion`, `driver: sglang`
- **모델**: `Qwen/Qwen2.5-0.5B-Instruct`
- **런타임**: `.venv/sglang`의 `virtualenv`
- **Action 플래그**: `streaming: true` — 생성된 토큰이 점진적으로 방출됩니다.

### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `system_prompt` | text | 아니오 | 어시스턴트의 행동을 지정하는 system 메시지 |
| `user_prompt` | text | 예 | 어시스턴트가 응답할 user 턴 |

### 출력 형식

job 출력은 텍스트 스트림입니다 — HTTP 응답이 청크를 점진적으로 전달하고, `${output as stream/text}`는 model-compose에게 스트림을 그대로 클라이언트에게 전달하도록 지시합니다.

## 커스터마이징

### 더 큰 모델

```yaml
component:
  model: Qwen/Qwen2.5-7B-Instruct
  options:
    context_length: 8192
```

### 샘플링

```yaml
action:
  params:
    temperature: 0.9
    top_p: 0.95
    do_sample: true
```

## 문제 해결

- **터미널에 점진적 출력이 보이지 않음**: `curl`에 `-N`을 추가하거나 클라이언트의 버퍼링을 비활성화하세요. 그렇지 않으면 청크가 버퍼링되어 하나의 최종 응답처럼 보입니다.
- **CUDA 메모리 부족**: `mem_fraction_static` 또는 `context_length`를 낮추거나 더 작은 모델을 사용하세요.
- **스트림이 갑자기 멈춤**: 서버 로그를 확인하세요 — 엔진이 `max_output_length`나 stop sequence에 도달하면 스트리밍이 중단됩니다.

## 참고

- `../sglang/` — 전체 응답을 한 번에 반환하는 non-streaming 버전
- `../vllm-stream/` — vLLM 드라이버에서 동일한 스트리밍 워크플로우
