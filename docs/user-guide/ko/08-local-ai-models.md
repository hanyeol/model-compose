# 8장: 로컬 AI 모델 사용

이 장에서는 로컬 AI 모델 사용 방법을 다룹니다.

---

## 8.1 로컬 모델 개요

### 로컬 모델이란?

로컬 모델은 외부 API 없이 시스템에서 직접 실행되는 AI 모델입니다. model-compose는 다양한 드라이버와 모델 포맷을 지원하여 유연한 모델 실행 환경을 제공합니다.

### 지원 모델 드라이버

model-compose는 다음 모델 드라이버를 지원합니다:

| 드라이버 | 설명 | 주요 사용 사례 |
|---------|------|---------------|
| `huggingface` | HuggingFace transformers | 범용 모델 추론, 가장 광범위한 모델 지원 |
| `unsloth` | Unsloth 최적화 모델 | 빠른 파인튜닝, 메모리 효율적 학습 |
| `vllm` | vLLM 추론 엔진 | 고성능 LLM 서빙, 프로덕션 배포 |
| `llamacpp` | llama.cpp 엔진 | CPU 추론, GGUF 포맷, 저사양 환경 |
| `custom` | 커스텀 구현 | 특수 모델, 사용자 정의 로직 |

### 지원 모델 포맷

다양한 모델 포맷을 지원합니다:

| 포맷 | 설명 | 호환 드라이버 |
|------|------|--------------|
| `pytorch` | PyTorch 기본 포맷 (.bin, .pt) | huggingface, unsloth |
| `safetensors` | 안전한 텐서 저장 포맷 | huggingface, unsloth |
| `onnx` | 최적화된 크로스 플랫폼 포맷 | custom |
| `gguf` | llama.cpp 양자화 포맷 | llamacpp |
| `tensorrt` | NVIDIA TensorRT 최적화 | custom |

### 로컬 모델의 장단점

**장점:**
- **비용 절감**: API 호출 비용 없음
- **프라이버시**: 데이터가 외부로 전송되지 않음
- **오프라인 실행**: 인터넷 연결 불필요
- **커스터마이징**: 파인튜닝, LoRA 어댑터 적용 가능
- **낮은 레이턴시**: 네트워크 지연 없음 (로컬 하드웨어 성능에 따라)

**단점:**
- **하드웨어 요구사항**: GPU 메모리, 연산 성능 필요
- **모델 크기**: 대용량 모델 파일 다운로드 및 저장 필요
- **설정 복잡도**: 환경 설정, 의존성 관리 필요
- **성능 제약**: 대형 모델은 고사양 GPU 필요

### 기본 사용법

**간단한 모델 로드 (HuggingFace)**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # 기본 드라이버는 huggingface
```

**드라이버 명시**
```yaml
component:
  type: model
  task: text-generation
  driver: unsloth  # Unsloth 드라이버 사용
  model: unsloth/llama-2-7b-bnb-4bit
```

**로컬 파일 로드**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch
```

**GGUF 포맷**
```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: /models/llama-2-7b-chat.Q4_K_M.gguf
    format: gguf
```

---

## 8.2 모델 설치 및 준비

### 모델 소스 지정 방법

model-compose는 두 가지 provider를 통해 모델을 로드할 수 있습니다:

#### 1. HuggingFace Hub (provider: huggingface)

**간단한 방법 (문자열)**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # 자동으로 HuggingFace Hub에서 로드
```

**상세 설정**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: main                  # 브랜치 또는 커밋 해시
    filename: pytorch_model.bin     # 특정 파일 지정
    cache_dir: /custom/cache        # 캐시 디렉토리
    local_files_only: false         # 로컬 캐시만 사용 여부
    token: ${env.HUGGINGFACE_TOKEN} # 프라이빗 모델 토큰
```

**HuggingFace 설정 필드:**
- `repository`: HuggingFace 모델 리포지토리 (필수)
- `revision`: 모델 버전 또는 브랜치 (기본값: `main`)
- `filename`: 리포지토리 내 특정 파일 지정 (선택)
- `cache_dir`: 모델 파일 캐시 디렉토리 (기본값: `~/.cache/huggingface/`)
- `local_files_only`: 로컬 캐시만 사용 (기본값: `false`)
- `token`: 프라이빗 모델 접근 토큰 (선택)

#### 2. 로컬 파일 (provider: local)

**간단한 방법 (경로 문자열)**
```yaml
component:
  type: model
  task: text-generation
  model: /path/to/model
  # 로컬 경로로 자동 인식
```

**상세 설정**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch  # pytorch, safetensors, onnx, gguf, tensorrt
```

**Local 설정 필드:**
- `path`: 모델 파일 또는 디렉토리 경로 (필수)
- `format`: 모델 파일 포맷 (기본값: `pytorch`)

**로컬 경로 인식 규칙:**

다음 패턴으로 시작하는 문자열은 자동으로 로컬 경로로 인식됩니다:
- 절대 경로: `/path/to/model`
- 상대 경로: `./model`, `../model`
- 홈 디렉토리: `~/models/model`
- Windows 드라이브: `C:\models\model`

그 외는 HuggingFace Hub 리포지토리로 인식됩니다:
- `meta-llama/Llama-2-7b-hf`
- `gpt2`
- `username/custom-model`

### HuggingFace 모델 다운로드

모델은 처음 실행 시 자동으로 다운로드됩니다:

```yaml
component:
  type: model
  task: chat-completion
  model: meta-llama/Llama-2-7b-chat-hf
  # 첫 실행 시 자동으로 ~/.cache/huggingface/ 에 다운로드됨
```

수동 다운로드:
```bash
# HuggingFace CLI로 사전 다운로드
pip install huggingface-hub
huggingface-cli download meta-llama/Llama-2-7b-chat-hf
```

### 프라이빗 모델 접근

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
```

환경 변수 설정:
```bash
export HUGGINGFACE_TOKEN=hf_your_token_here
model-compose up
```

### 특정 모델 버전 사용

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: v1.0  # 특정 태그
    # 또는 커밋 해시: revision: a1b2c3d4
```

### 오프라인 모드

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: gpt2
    local_files_only: true  # 로컬 캐시에서만 로드
```

---

## 8.3 지원 태스크 유형

model-compose는 다음 태스크 타입을 지원합니다:

| 태스크 | 설명 | 주요 사용 사례 |
|--------|------|---------------|
| `text-generation` | 텍스트 생성 | 스토리 작성, 코드 생성 |
| `chat-completion` | 대화형 완성 | 챗봇, 어시스턴트 |
| `text-classification` | 텍스트 분류 | 감정 분석, 주제 분류 |
| `text-embedding` | 텍스트 임베딩 | 시맨틱 검색, RAG |
| `image-to-text` | 이미지 캡셔닝 | 이미지 설명 생성, VQA |
| `image-generation` | 이미지 생성 | 텍스트→이미지 변환 |
| `image-upscale` | 이미지 업스케일 | 해상도 향상 |
| `face-embedding` | 얼굴 임베딩 | 얼굴 인식, 비교 |

### 8.3.1 text-generation

프롬프트를 기반으로 텍스트를 생성합니다.

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  text: ${input.prompt as text}
  params:
    max_output_length: 32768
    temperature: 0.7
    top_p: 0.9
```

**주요 파라미터:**
- `max_output_length`: 최대 생성 토큰 수
- `temperature`: 생성 랜덤성 (0.0~2.0, 낮을수록 결정적)
- `top_p`: Nucleus sampling threshold
- `top_k`: Top-K sampling
- `repetition_penalty`: 반복 방지 (1.0~2.0)

### 8.3.2 chat-completion

대화 형식의 메시지를 처리합니다.

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  messages:
    - role: system
      content: ${input.system_prompt}
    - role: user
      content: ${input.user_prompt}
  params:
    max_output_length: 2048
    temperature: 0.7
```

**메시지 형식:**
- `role`: `system`, `user`, `assistant`
- `content`: 메시지 내용

### 8.3.3 text-classification

텍스트를 카테고리로 분류합니다.

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased-finetuned-sst-2-english
  text: ${input.text as text}
  output:
    label: ${result.label}
    score: ${result.score}
```

### 8.3.4 text-embedding

텍스트를 고차원 벡터로 변환합니다.

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  text: ${input.text as text}
  output:
    embedding: ${result.embedding}
```

사용 예제 (RAG 시스템):
```yaml
workflow:
  title: Document Search
  jobs:
    - id: embed-query
      component: embedder
      input:
        text: ${input.query}
      output:
        query_vector: ${result.embedding}

    - id: search
      component: vector-store
      action: search
      input:
        vector: ${jobs.embed-query.output.query_vector}
        top_k: 5
```

### 8.3.5 image-to-text

이미지를 분석하여 텍스트를 생성합니다.

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-large
  architecture: blip
  image: ${input.image as image}
  prompt: ${input.prompt as text}
```

**지원 아키텍처:**
- `blip`: 이미지 캡셔닝
- `git`: Generative Image-to-Text
- `vit-gpt2`: Vision Transformer + GPT-2

### 8.3.6 image-generation

텍스트 프롬프트에서 이미지를 생성합니다.

```yaml
component:
  type: model
  task: image-generation
  architecture: flux
  model: black-forest-labs/FLUX.1-dev
  prompt: ${input.prompt as text}
  params:
    width: 1024
    height: 1024
    num_inference_steps: 50
```

**지원 아키텍처:**
- `flux`: FLUX 모델
- `sdxl`: Stable Diffusion XL
- `hunyuan`: HunyuanDiT

### 8.3.7 image-upscale

이미지 해상도를 향상시킵니다.

```yaml
component:
  type: model
  task: image-upscale
  architecture: real-esrgan
  model: RealESRGAN_x4plus
  image: ${input.image as image}
  params:
    scale: 4
```

**지원 아키텍처:**
- `real-esrgan`: Real-ESRGAN
- `esrgan`: ESRGAN
- `swinir`: SwinIR
- `ldsr`: Latent Diffusion Super Resolution

### 8.3.8 face-embedding

얼굴 이미지에서 특징 벡터를 추출합니다.

```yaml
component:
  type: model
  task: face-embedding
  model: buffalo_l
  image: ${input.image as image}
```

---

## 8.4 모델 설정 (디바이스, 정밀도, 배치 크기)

### 디바이스 설정

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  device: cuda         # 'cuda', 'cpu', 'mps' (Apple Silicon)
  device_mode: single  # 'single', 'auto' (multi-GPU)
```

**디바이스 옵션:**
- `cuda`: NVIDIA GPU
- `cpu`: CPU만 사용
- `mps`: Apple Silicon GPU (M1/M2/M3)

**디바이스 모드:**
- `single`: 단일 GPU 사용
- `auto`: 여러 GPU에 자동 분산

다중 GPU 예제:
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # 자동으로 여러 GPU에 모델 분산
```

### 정밀도 설정

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  precision: float16  # 'auto', 'float32', 'float16', 'bfloat16'
```

**정밀도 옵션:**
- `auto`: 자동 선택 (GPU는 float16, CPU는 float32)
- `float32`: 최고 정확도, 가장 많은 메모리 사용
- `float16`: 절반 메모리, 빠른 추론 (CUDA)
- `bfloat16`: float16 대안, 더 안정적 (최신 GPU)

정밀도 비교:

| 정밀도 | 메모리 | 속도 | 정확도 | 권장 사용 |
|--------|--------|------|--------|-----------|
| float32 | 100% | 기준 | 최고 | CPU, 높은 정확도 필요 시 |
| float16 | 50% | 2배 빠름 | 약간 감소 | CUDA GPU |
| bfloat16 | 50% | 2배 빠름 | float16보다 안정 | 최신 GPU (A100, H100) |

### 양자화

메모리를 더 줄이고 속도를 높이기 위한 양자화:

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  quantization: int8  # 'none', 'int8', 'int4', 'nf4'
```

**양자화 옵션:**
- `none`: 양자화 없음 (기본값)
- `int8`: 8비트 정수 (bitsandbytes 필요)
- `int4`: 4비트 정수 (bitsandbytes 필요)
- `nf4`: 4비트 NormalFloat (QLoRA용)

### 배치 크기

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased
  batch_size: 32  # 한 번에 처리할 입력 수
```

배치 크기 선택 가이드:
- **작은 배치 (1-8)**: 낮은 레이턴시, 실시간 추론
- **중간 배치 (16-32)**: 균형잡힌 처리량/레이턴시
- **큰 배치 (64+)**: 최대 처리량, 배치 처리

### 저메모리 로딩

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  low_cpu_mem_usage: true  # CPU RAM 사용 최소화
  device: cuda
```

---

## 8.5 LoRA/PEFT 어댑터 사용

LoRA (Low-Rank Adaptation)는 전체 모델을 파인튜닝하지 않고 작은 어댑터 모듈을 추가하여 모델을 특정 태스크에 맞게 조정하는 기법입니다.

### LoRA 어댑터 적용

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 1.0
  text: ${input.prompt as text}
```

### 다중 LoRA 어댑터

여러 LoRA 어댑터를 동시에 적용할 수 있습니다:

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 0.7
    - type: lora
      name: assistant
      model: plncmm/guanaco-lora-7b
      weight: 0.8
  text: ${input.prompt as text}
```

### 어댑터 가중치

`weight` 파라미터로 어댑터의 영향력을 조절합니다:

```yaml
peft_adapters:
  - type: lora
    name: style-adapter
    model: user/style-lora
    weight: 0.5  # 50% 영향력
```

- `weight: 0.0`: 어댑터 비활성화
- `weight: 0.5`: 50% 적용
- `weight: 1.0`: 100% 적용 (기본값)

### 로컬 LoRA 어댑터

로컬 파일 시스템의 어댑터 사용:

```yaml
peft_adapters:
  - type: lora
    name: custom-lora
    model:
      provider: local
      path: /path/to/lora/adapter
    weight: 1.0
```

### LoRA 사용 사례

**1. 도메인 적응**
```yaml
# 의료 도메인에 특화된 모델
peft_adapters:
  - type: lora
    name: medical
    model: medalpaca/medalpaca-lora-7b
    weight: 1.0
```

**2. 스타일 제어**
```yaml
# 여러 작문 스타일 조합
peft_adapters:
  - type: lora
    name: formal
    model: user/formal-writing-lora
    weight: 0.6
  - type: lora
    name: technical
    model: user/technical-lora
    weight: 0.4
```

**3. 다국어 지원**
```yaml
# 한국어 지원 강화
peft_adapters:
  - type: lora
    name: korean
    model: beomi/llama-2-ko-7b-lora
    weight: 1.0
```

---

## 8.6 모델 서빙 프레임워크

대규모 프로덕션 환경이나 고성능 추론이 필요한 경우, 전용 모델 서빙 프레임워크를 사용할 수 있습니다.

> **중요:** vLLM, Ollama 등의 모델 서빙 프레임워크는 로컬 모델을 사용하지만, `model` 컴포넌트가 아닌 `http-server`나 `http-client` 컴포넌트를 통해 HTTP API로 접근합니다. 이는 별도의 서버 프로세스가 모델을 로드하고 서빙하기 때문입니다.

### vLLM

vLLM은 대규모 언어 모델을 위한 고성능 추론 엔진입니다.

#### vLLM 특징

- **PagedAttention**: 메모리 효율적인 어텐션 메커니즘
- **연속 배칭**: 높은 처리량
- **빠른 추론**: 최적화된 CUDA 커널
- **OpenAI 호환 API**: 기존 코드와 쉽게 통합

#### vLLM 설정 예제

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        (pyenv activate vllm 2>/dev/null || pyenv virtualenv $(python --version | cut -d' ' -f2) vllm) &&
        pyenv activate vllm &&
        pip install vllm
    start:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        pyenv activate vllm &&
        python -m vllm.entrypoints.openai.api_server
          --model Qwen/Qwen2-7B-Instruct
          --port 8000
          --served-model-name qwen2-7b-instruct
          --max-model-len 2048
  port: 8000
  method: POST
  path: /v1/chat/completions
  headers:
    Content-Type: application/json
  body:
    model: qwen2-7b-instruct
    messages:
      - role: user
        content: ${input.prompt as text}
    max_tokens: 512
    temperature: ${input.temperature as number | 0.7}
    streaming: true
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

#### vLLM 파라미터

**서버 파라미터:**
- `--model`: 모델 이름 또는 경로
- `--port`: 서버 포트
- `--host`: 바인드 호스트
- `--served-model-name`: API에서 사용할 모델 이름
- `--max-model-len`: 최대 시퀀스 길이
- `--tensor-parallel-size`: Tensor parallelism (다중 GPU)
- `--dtype`: 데이터 타입 (auto, float16, bfloat16)

**추론 파라미터:**
- `max_tokens`: 최대 생성 토큰 수
- `temperature`: 생성 랜덤성
- `top_p`: Nucleus sampling
- `streaming`: 스트리밍 응답 여부

### Ollama

Ollama는 로컬에서 대형 언어 모델을 실행하기 위한 간단한 도구입니다.

#### Ollama 특징

- **간편한 설치**: 원클릭 설치
- **모델 라이브러리**: 사전 최적화된 모델 제공
- **낮은 진입장벽**: 복잡한 설정 불필요
- **REST API**: 간단한 HTTP 인터페이스

#### Ollama 자동 관리 (http-server 컴포넌트)

model-compose가 Ollama를 자동으로 설치하고 실행하는 경우:

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        # macOS/Linux
        curl -fsSL https://ollama.ai/install.sh | sh
        # 모델 다운로드
        ollama pull llama2
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  headers:
    Content-Type: application/json
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: false
  output:
    response: ${response.response}
```

**스트리밍 예제:**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: true
  stream_format: json
  output: ${response[].response}
```

**채팅 API:**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/chat
  body:
    model: llama2
    messages: ${input.messages}
  output:
    message: ${response.message.content}
```

#### 기존 Ollama 서버 사용 (http-client)

이미 실행 중인 Ollama 서버가 있는 경우:

```yaml
component:
  type: http-client
  endpoint: http://localhost:11434/api/generate
  method: POST
  body:
    model: llama2
    prompt: ${input.prompt as text}
  output:
    response: ${response.response}
```

### TGI (Text Generation Inference)

HuggingFace의 프로덕션 레벨 추론 서버입니다.

```yaml
component:
  type: http-client
  endpoint: http://localhost:8080/generate
  method: POST
  headers:
    Content-Type: application/json
  body:
    inputs: ${input.prompt as text}
    parameters:
      max_new_tokens: 512
      temperature: 0.7
      top_p: 0.9
  output:
    generated_text: ${response.generated_text}
```

### 프레임워크 비교

| 프레임워크 | 장점 | 단점 | 권장 사용 |
|-----------|------|------|-----------|
| **vLLM** | 최고 성능, 높은 처리량 | 설정 복잡도, CUDA 전용 | 프로덕션, 대규모 서비스 |
| **Ollama** | 간편한 설치, 낮은 진입장벽 | 제한적인 모델, 제한적인 제어 | 개발, 프로토타입, 개인 사용 |
| **TGI** | HuggingFace 통합, 안정성 | vLLM보다 느림 | HuggingFace 생태계 사용 시 |
| **transformers** | 최대 호환성, 커스터마이징 | 낮은 성능 | 연구, 실험, 커스텀 모델 |

---

## 8.7 성능 최적화 팁

### 1. 적절한 정밀도 선택

```yaml
# GPU가 있는 경우
component:
  type: model
  model: large-model
  precision: float16  # 또는 bfloat16 (최신 GPU)
  device: cuda

# CPU만 있는 경우
component:
  type: model
  model: small-model
  precision: float32  # CPU는 float32가 더 안정적
  device: cpu
```

### 2. 양자화 활용

```yaml
# 메모리가 제한적인 경우
component:
  type: model
  model: meta-llama/Llama-2-13b-hf
  quantization: int8  # 메모리 사용량 약 50% 감소
  device: cuda
```

### 3. 적절한 배치 크기

```yaml
# 처리량 최적화
component:
  type: model
  task: text-classification
  model: bert-base
  batch_size: 32  # GPU 메모리에 맞게 조정
```

### 4. 모델 캐싱

```yaml
# 모델 재사용을 위한 캐싱
component:
  type: model
  model:
    provider: huggingface
    repository: gpt2
    cache_dir: /data/model-cache  # 고속 SSD 사용
```

### 5. 다중 GPU 활용

```yaml
# 모델 병렬화
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # 자동으로 여러 GPU에 분산
```

### 일반적인 성능 문제와 해결책

| 문제 | 원인 | 해결책 |
|------|------|--------|
| 느린 첫 실행 | 모델 다운로드, 컴파일 | 모델 사전 다운로드, 워밍업 |
| OOM (Out of Memory) | 모델이 GPU 메모리보다 큼 | 양자화, 정밀도 낮추기, 작은 배치 |
| 낮은 처리량 | 작은 배치 크기 | 배치 크기 증가 |
| 높은 레이턴시 | 큰 배치 크기 | 배치 크기 감소, 실시간 처리 |
| 불안정한 출력 | float16 정밀도 문제 | bfloat16 또는 float32 사용 |

---

## 다음 단계

실습해보세요:
- HuggingFace Hub에서 다양한 모델 테스트
- 양자화 및 정밀도 설정 실험
- LoRA 어댑터 로드 및 병합
- 배치 처리로 처리량 최적화

---

**다음 장**: [9. 모델 훈련](./09-model-training.md)
