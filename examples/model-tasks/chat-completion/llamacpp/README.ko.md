# Chat Completion (llama.cpp) 예제

이 예제는 model-compose의 내장 `llamacpp` 드라이버를 사용하여 GGUF 포맷 모델로 llama.cpp 기반 chat completion을 로컬에서 실행하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 chat completion을 제공합니다:

1. **llama.cpp 백엔드**: 최소한의 메모리로 GGUF 양자화 모델 실행
2. **OpenAI 호환 Chat 포맷**: system/user/assistant 메시지 역할 지원
3. **Tool Use (Function Calling)**: 함수 호출 워크플로우를 위한 툴 정의 지원
4. **외부 API 불필요**: API 의존성 없이 완전한 오프라인 추론

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `llama-cpp-python` 설치 (아래 설치 방법 참조)
- `./.models/llama-3.2-1b-instruct-q4_k_m.gguf` 경로에 GGUF instruct 모델 파일 배치

### llama-cpp-python 설치

```bash
# CPU 전용
pip install llama-cpp-python

# macOS Metal 가속 (Apple Silicon / AMD GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### GGUF 모델 다운로드

```bash
mkdir -p models

# HuggingFace에서 Llama-3.2-1B-Instruct Q4_K_M 다운로드
curl -L -o .models/llama-3.2-1b-instruct-q4_k_m.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/chat-completion-llamacpp
   ```

2. GGUF instruct 모델 파일을 `./.models/` 아래에 배치합니다.

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
         "system_prompt": "당신은 친절한 AI 어시스턴트입니다.",
         "user_prompt": "GGUF 파일이 무엇인지 쉽게 설명해주세요."
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
     "system_prompt": "당신은 친절한 AI 어시스턴트입니다.",
     "user_prompt": "GGUF 파일이 무엇인지 쉽게 설명해주세요."
   }'
   ```

## 컴포넌트 세부사항

### Chat Completion Model 컴포넌트
- **유형**: chat-completion task를 가진 Model 컴포넌트
- **드라이버**: `llamacpp`
- **모델**: GGUF 양자화 instruct 모델 (기본: Q4_K_M)
- **기능**:
  - llama.cpp를 이용한 CPU 최적화 추론
  - System 및 user 메시지 역할 지원
  - Tool use (function calling) 지원
  - `n_gpu_layers`를 통한 GPU 오프로딩
  - 스트리밍 지원

## 워크플로우 세부사항

### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `system_prompt` | text | 아니오 | - | 어시스턴트의 역할을 정의하는 system 메시지 |
| `user_prompt` | text | 예 | - | 어시스턴트가 응답해야 하는 user 메시지 |

### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `generated` | text | 어시스턴트의 응답 |

## 사용자 정의

### GPU 오프로딩

```yaml
component:
  type: model
  task: chat-completion
  driver: llamacpp
  model:
    provider: local
    path: ./.models/llama-3.2-1b-instruct-q4_k_m.gguf
    format: gguf
  device: cuda        # macOS는 "metal"
  n_gpu_layers: -1    # -1 = 전체 레이어 오프로딩
  context_length: 4096
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_prompt}
```

### 스트리밍 출력

```yaml
component:
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_prompt}
    streaming: true
```

### Tool Use (Function Calling)

```yaml
component:
  action:
    messages:
      - role: user
        content: ${input.user_prompt}
    tools:
      - name: get_weather
        description: 특정 위치의 현재 날씨를 가져옵니다
        parameters:
          type: object
          properties:
            location:
              type: string
              description: 도시 이름
          required:
            - location
```

## 시스템 요구사항

### 최소 요구사항 (CPU)
- **RAM**: 2GB+ (모델 크기 및 양자화에 따라 다름)
- **디스크 공간**: 모델 파일 크기 (1B Q4_K_M ≈ 0.8GB)
- **CPU**: 최신 x86_64 또는 ARM64 프로세서

### 권장 사양 (GPU)
- **VRAM**: 1B 모델 2GB+, 7B 모델 6GB+
- **GPU**: NVIDIA (CUDA) 또는 Apple Silicon (Metal)

## 문제 해결

1. **`llama_cpp` 없음**: `pip install llama-cpp-python`으로 설치
2. **낮은 응답 품질**: base 모델이 아닌 instruct/chat 튜닝된 GGUF 모델 사용
3. **메모리 부족**: 더 낮은 양자화(Q4 또는 Q2)나 더 작은 모델 사용
4. **느린 추론**: `n_gpu_layers: -1`로 GPU 오프로딩 활성화
