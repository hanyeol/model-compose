# 텍스트 임베딩 (llama.cpp) 예제

이 예제는 model-compose의 내장 `llamacpp` 드라이버를 사용하여 GGUF 포맷 임베딩 모델로 llama.cpp 기반 텍스트 임베딩을 로컬에서 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 텍스트 임베딩을 제공합니다:

1. **llama.cpp 백엔드**: GGUF 양자화 임베딩 모델을 효율적으로 실행
2. **CPU 친화적**: GPU 없이도 CPU에서 원활하게 동작
3. **L2 정규화**: 코사인 유사도 사용을 위한 선택적 임베딩 정규화
4. **외부 API 불필요**: API 의존성 없이 완전한 오프라인 임베딩

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `llama-cpp-python` 설치 (아래 설치 방법 참조)
- `./models/nomic-embed-text-v1.5.Q4_K_M.gguf` 경로에 GGUF 임베딩 모델 파일 배치

### llama-cpp-python 설치

```bash
# CPU 전용
pip install llama-cpp-python

# macOS Metal 가속 (Apple Silicon / AMD GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### GGUF 임베딩 모델 다운로드

```bash
mkdir -p models

# HuggingFace에서 nomic-embed-text-v1.5 Q4_K_M 다운로드
curl -L -o models/nomic-embed-text-v1.5.Q4_K_M.gguf \
  https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q4_K_M.gguf
```

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/text-embedding-llamacpp
   ```

2. GGUF 임베딩 모델 파일을 `./models/` 아래에 배치합니다.

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
         "text": "빠른 갈색 여우가 게으른 개를 뛰어넘습니다."
       }
     }'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 텍스트 입력
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"text": "빠른 갈색 여우가 게으른 개를 뛰어넘습니다."}'
   ```

## 컴포넌트 세부사항

### Text Embedding Model 컴포넌트
- **유형**: text-embedding task를 가진 Model 컴포넌트
- **드라이버**: `llamacpp`
- **모델**: GGUF 양자화 임베딩 모델 (기본: nomic-embed-text-v1.5 Q4_K_M)
- **기능**:
  - llama.cpp를 이용한 CPU 최적화 추론
  - 자동 `embedding=True` 모드 활성화
  - 코사인 유사도 사용을 위한 L2 정규화
  - 배치 처리 지원
  - `n_gpu_layers`를 통한 GPU 오프로딩

## 워크플로우 세부사항

### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `text` | text | 예 | - | 임베딩할 입력 텍스트 |

### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `embedding` | JSON 배열 | 부동소수점 임베딩 벡터 |

## 사용자 정의

### GPU 오프로딩

```yaml
component:
  type: model
  task: text-embedding
  driver: llamacpp
  model:
    provider: local
    path: ./models/nomic-embed-text-v1.5.Q4_K_M.gguf
    format: gguf
  device: cuda        # macOS는 "metal"
  n_gpu_layers: -1    # -1 = 전체 레이어 오프로딩
  context_length: 2048
  action:
    text: ${input.text}
    params:
      normalize: true
```

### 배치 임베딩

```yaml
component:
  action:
    text: ${input.texts}   # 문자열 리스트 전달
    batch_size: 16
    params:
      normalize: true
```

### 정규화 없이 사용

```yaml
component:
  action:
    text: ${input.text}
    params:
      normalize: false    # 원시 임베딩 반환
```

## 시스템 요구사항

### 최소 요구사항 (CPU)
- **RAM**: 1GB+ (모델 크기 및 양자화에 따라 다름)
- **디스크 공간**: 모델 파일 크기 (nomic-embed Q4_K_M ≈ 80MB)
- **CPU**: 최신 x86_64 또는 ARM64 프로세서

### 권장 사양 (GPU)
- **VRAM**: 대부분의 임베딩 모델에 1GB+
- **GPU**: NVIDIA (CUDA) 또는 Apple Silicon (Metal)

## 추천 GGUF 임베딩 모델

| 모델 | 차원수 | 크기 (Q4) | 용도 |
|-----|--------|---------|------|
| `nomic-ai/nomic-embed-text-v1.5-GGUF` | 768 | ~80MB | 범용 |
| `CompendiumLabs/bge-large-en-v1.5-gguf` | 1024 | ~300MB | 고품질 영어 |
| `CompendiumLabs/bge-m3-gguf` | 1024 | ~600MB | 다국어 |

## 문제 해결

1. **`llama_cpp` 없음**: `pip install llama-cpp-python`으로 설치
2. **잘못된 모델 유형**: 생성 모델이 아닌 전용 임베딩 모델 사용
3. **메모리 부족**: 더 낮은 양자화나 더 작은 임베딩 모델 사용
4. **느린 임베딩**: `n_gpu_layers: -1`로 GPU 오프로딩 활성화
5. **모두 0인 임베딩**: 임베딩 모드를 지원하는 모델인지 확인 (전용 임베딩 GGUF 사용)
