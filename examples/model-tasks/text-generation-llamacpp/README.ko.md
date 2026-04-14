# 텍스트 생성 (llama.cpp) 예제

이 예제는 model-compose의 내장 `llamacpp` 드라이버를 사용하여 GGUF 포맷 모델로 llama.cpp 기반 텍스트 생성을 로컬에서 실행하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 텍스트 생성을 제공합니다:

1. **llama.cpp 백엔드**: 최소한의 메모리로 GGUF 양자화 모델 실행
2. **CPU 친화적**: GPU 없이도 CPU에서 원활하게 동작
3. **GGUF 포맷**: 메모리 절약을 위한 양자화 모델(Q4, Q5, Q8 등) 지원
4. **외부 API 불필요**: API 의존성 없이 완전한 오프라인 추론

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `llama-cpp-python` 설치 (아래 설치 방법 참조)
- `./models/llama-3.2-1b-instruct-q4_k_m.gguf` 경로에 GGUF 모델 파일 배치

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
curl -L -o models/llama-3.2-1b-instruct-q4_k_m.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/text-generation-llamacpp
   ```

2. GGUF 모델 파일을 `./models/` 아래에 배치합니다.

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
         "prompt": "인공지능의 역사는"
       }
     }'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 프롬프트 입력
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"prompt": "인공지능의 역사는"}'
   ```

## 컴포넌트 세부사항

### Text Generation Model 컴포넌트
- **유형**: text-generation task를 가진 Model 컴포넌트
- **드라이버**: `llamacpp`
- **모델**: GGUF 양자화 모델 (기본: Q4_K_M)
- **기능**:
  - llama.cpp를 이용한 CPU 최적화 추론
  - `n_gpu_layers`를 통한 GPU 오프로딩 (`-1`로 설정 시 전체 레이어 오프로딩)
  - 컨텍스트 윈도우 설정 (`context_length`)
  - 스트리밍 지원

## 워크플로우 세부사항

### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `prompt` | text | 예 | - | 생성의 시작점이 될 입력 텍스트 |

### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `generated` | text | 생성된 텍스트 |

## 사용자 정의

### GPU 오프로딩

GPU에 레이어를 오프로딩하려면 `device`와 `n_gpu_layers`를 설정합니다:

```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: ./models/llama-3.2-1b-instruct-q4_k_m.gguf
    format: gguf
  device: cuda        # macOS는 "metal"
  n_gpu_layers: -1    # -1 = 전체 레이어 오프로딩
  context_length: 4096
  action:
    text: ${input.prompt as text}
    params:
      max_output_length: 1024
```

### 다른 모델 사용

```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: ./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
    format: gguf
  context_length: 8192
  action:
    text: ${input.prompt as text}
```

### 스트리밍 출력

```yaml
component:
  action:
    text: ${input.prompt as text}
    streaming: true
    params:
      max_output_length: 2048
```

## 시스템 요구사항

### 최소 요구사항 (CPU)
- **RAM**: 2GB+ (모델 크기 및 양자화에 따라 다름)
- **디스크 공간**: 모델 파일 크기 (1B Q4_K_M ≈ 0.8GB)
- **CPU**: 최신 x86_64 또는 ARM64 프로세서

### 권장 사양 (GPU)
- **VRAM**: 1B 모델 2GB+, 7B 모델 6GB+
- **GPU**: NVIDIA (CUDA) 또는 Apple Silicon (Metal)

## GGUF 양자화 가이드

| 양자화 | 메모리 | 품질 | 추천 용도 |
|-------|--------|------|---------|
| Q2_K | 최소 | 최저 | RAM이 매우 제한적일 때 |
| Q4_K_M | 낮음 | 양호 | 일반 사용 (기본값) |
| Q5_K_M | 중간 | 더 좋음 | 더 높은 품질 |
| Q8_0 | 높음 | 최고 | 최대 품질 |
| F16 | 최고 | 무손실 | 대용량 VRAM GPU |

## 문제 해결

1. **`llama_cpp` 없음**: `pip install llama-cpp-python`으로 설치
2. **메모리 부족**: 더 낮은 양자화(Q4 또는 Q2)나 더 작은 모델 사용
3. **느린 추론**: `n_gpu_layers: -1`로 GPU 오프로딩 활성화
4. **모델 파일 없음**: YAML의 `path`가 실제 파일 위치와 일치하는지 확인
