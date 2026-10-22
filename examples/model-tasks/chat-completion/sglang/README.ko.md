# SGLang Chat Completion 예제

이 예제는 내장 **SGLang** 드라이버로 `chat-completion` 태스크를 실행하는 방법을 보여줍니다. 작은 instruction-tuned 모델을 전용 가상 환경에 로드하여 chat 응답을 생성합니다.

## 개요

이 워크플로우는 non-streaming chat completion을 수행합니다:

1. **SGLang 엔진**: 모델이 격리된 `virtualenv` 런타임 내부의 SGLang으로 로드되어 SGLang 의존성이 메인 환경과 분리됩니다.
2. **소형 Instruction 모델**: `Qwen/Qwen2.5-0.5B-Instruct` (~1GB)로 스모크 테스트 비용이 저렴합니다.
3. **표준 Chat 형식**: `system` 프롬프트와 `user` 프롬프트를 입력받아 전체 응답을 한 번에 반환합니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 `PATH`에서 사용 가능
- SGLang은 CUDA GPU가 필요 (Linux + NVIDIA). macOS/CPU 전용 환경에서는 실행 불가.
- Python 3.10+ (가상 환경 구성용)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/chat-completion/sglang
   ```

2. 첫 실행 시 컴포넌트가 `.venv/sglang`을 구성하고 SGLang을 설치한 뒤 Qwen 모델을 다운로드합니다.

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
         "system_prompt": "You are a helpful AI assistant.",
         "user_prompt": "Explain quantum computing in simple terms."
       }
     }'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - system prompt와 user prompt 입력
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{
     "system_prompt": "You are a helpful AI assistant.",
     "user_prompt": "Explain quantum computing in simple terms."
   }'
   ```

## 컴포넌트 상세

### Chat Completion 모델 컴포넌트 (SGLang)
- **타입**: `model` 컴포넌트, `task: chat-completion`, `driver: sglang`
- **모델**: `Qwen/Qwen2.5-0.5B-Instruct`
- **런타임**: `.venv/sglang`의 `virtualenv`
- **엔진 옵션**:
  - `context_length: 2048` — context window 상한
  - `mem_fraction_static: 0.85` — 모델과 KV 캐시용으로 예약되는 GPU 메모리 비율

### 왜 SGLang인가
- **구조화된 생성**: SGLang은 구조화된 출력, 제약 디코딩, 다중 턴 프로그램에 강합니다.
- **RadixAttention**: 요청 간 prefix 캐싱은 공유 system 프롬프트가 많은 워크로드에 유리합니다.

### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `system_prompt` | text | 아니오 | 어시스턴트의 행동을 지정하는 system 메시지 |
| `user_prompt` | text | 예 | 어시스턴트가 응답할 user 턴 |

### 출력 형식

| 필드 | 타입 | 설명 |
|------|------|------|
| `generated` | text | 어시스턴트 응답 전체(단일 문자열) |

## 커스터마이징

### 다른 모델 사용

```yaml
component:
  model: Qwen/Qwen2.5-1.5B-Instruct  # 또는 Qwen/Qwen2.5-7B-Instruct 등
```

### 더 큰 Context Window

```yaml
component:
  options:
    context_length: 8192
```

### 샘플링 파라미터

```yaml
action:
  params:
    temperature: 0.9
    top_p: 0.95
    do_sample: true
```

## 문제 해결

- **CUDA 오류 / 메모리 부족**: `mem_fraction_static`(예: `0.7`) 또는 `context_length`를 낮추거나 더 작은 모델을 사용하세요.
- **첫 실행이 느림**: SGLang 설치와 모델 다운로드가 첫 부팅 시 수행됩니다. 이후 실행은 캐시를 재사용합니다.
- **SGLang 설치 실패**: SGLang 릴리스 노트에서 CUDA + PyTorch 버전 조합을 확인하세요.

## 참고

- `../huggingface/` — HuggingFace 드라이버에서 동일 태스크 (SGLang 의존성 없음)
- `../vllm/` — vLLM 드라이버에서 동일 태스크
- `../sglang-stream/` — 이 예제의 streaming 버전
