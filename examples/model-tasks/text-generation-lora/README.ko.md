# 다중 LoRA 어댑터를 사용한 텍스트 생성

이 예제는 기본 언어 모델과 함께 여러 LoRA (Low-Rank Adaptation) 어댑터를 사용하여 다양한 도메인과 작업에 걸쳐 텍스트 생성 능력을 향상시키는 방법을 보여줍니다.

## 개요

이 워크플로우는 기본 Llama 2 7B 모델과 여러 특화된 LoRA 어댑터를 결합합니다:

- **Alpaca 어댑터** (`tloen/alpaca-lora-7b`): 지시 수행 능력
- **Guanaco 어댑터** (`plncmm/guanaco-lora-7b`): 대화형 및 어시스턴트 같은 응답

각 어댑터는 독립적으로 가중치를 조정할 수 있어 모델의 동작을 세밀하게 제어할 수 있습니다.

## 기능

- **다중 어댑터 지원**: 여러 LoRA 어댑터를 동시에 로드
- **가중치 제어**: 각 어댑터의 영향력 조정 (0.0에서 2.0+)
- **장치 할당**: 각 어댑터에 대해 다른 장치 지정
- **정밀도 제어**: 어댑터별로 개별 정밀도 (float16, bfloat16) 설정

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- 충분한 VRAM을 가진 CUDA 호환 GPU (권장: 16GB+)
- transformers, torch, peft가 포함된 Python 환경 (자동 관리)
- 제한된 모델(예: Llama 2) 접근을 위한 HuggingFace 토큰

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/text-generation-lora
   ```

2. 제한된 모델을 위한 HuggingFace 인증 설정:
   ```bash
   export HUGGINGFACE_TOKEN=your_huggingface_token
   ```

   또는 CLI를 통해 로그인:
   ```bash
   huggingface-cli login
   ```

3. 추가 구성 불필요 - 모델과 LoRA 어댑터는 자동으로 다운로드됩니다.

## 구성

### 기본 모델
```yaml
model: meta-llama/Llama-2-7b-hf
```

### LoRA 어댑터
```yaml
peft_adapters:
  - type: lora
    name: alpaca
    model: tloen/alpaca-lora-7b
    weight: 0.7

  - type: lora
    name: assistant
    model: plncmm/guanaco-lora-7b
    weight: 0.8
```

### 매개변수
- `weight`: 어댑터 영향력을 위한 스케일링 인수 (기본값: 1.0)
  - `< 1.0`: 어댑터 효과 감소
  - `1.0`: 전체 어댑터 효과
  - `> 1.0`: 어댑터 효과 증폭
- `precision`: 모델 정밀도 (예: `float16`, `bfloat16`)

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
         "prompt": "Explain quantum computing in simple terms."
       }
     }'
   ```

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 프롬프트 입력
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"prompt": "Explain quantum computing in simple terms."}'
   ```

### 예제 프롬프트

**지시 수행 (Alpaca):**
```
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Write a Python function to calculate fibonacci numbers.

### Response:
```

**대화형 (Guanaco):**
```
Human: What are the benefits of using LoRA for fine-tuning?
Assistant:
```

## 작동 원리

### LoRA 아키텍처

LoRA는 가중치 업데이트를 저차원 행렬로 분해합니다:
```
W = W₀ + ΔW
ΔW = B × A × scaling
```

여기서:
- `W₀`: 고정된 사전 학습 가중치
- `A`: 저차원 다운 프로젝션 (rank × input_dim)
- `B`: 저차원 업 프로젝션 (output_dim × rank)
- `scaling`: lora_alpha / rank

### 다중 어댑터 블렌딩

여러 어댑터가 로드되면 순차적으로 적용됩니다:
```
output = base_model(input)
for adapter in adapters:
    output += adapter.forward(input) × weight
```

`weight` 매개변수는 각 어댑터의 기여도를 제어합니다.

## 맞춤화

### 자체 LoRA 추가

HuggingFace Hub 또는 로컬 경로에서 사용자 정의 LoRA 어댑터를 추가할 수 있습니다:

```yaml
peft_adapters:
  # HuggingFace Hub
  - type: lora
    name: my_adapter
    model: username/my-lora-adapter
    weight: 1.0

  # 로컬 경로
  - type: lora
    name: local_adapter
    model:
      provider: local
      path: ./path/to/lora
    weight: 0.5
```

### 어댑터 가중치 조정

어댑터 간 균형 미세 조정:

```yaml
peft_adapters:
  - type: lora
    name: alpaca
    weight: 0.3  # 지시 수행 감소

  - type: lora
    name: assistant
    weight: 1.2  # 대화형 증가
```

## 시스템 요구사항

### 최소 요구사항
- **GPU VRAM**: 16GB+ (Llama-2-7b + 어댑터에 필요)
- **RAM**: 16GB 시스템 RAM (권장 32GB+)
- **디스크 공간**: 모델 및 어댑터 저장을 위한 20GB+
- **CUDA**: CUDA 11.8+ 호환 GPU (NVIDIA)
- **인터넷**: 초기 모델 및 어댑터 다운로드에 필요

### 성능 참고사항
- 첫 실행 시 기본 모델(~13GB) 및 어댑터(각 ~100MB) 다운로드 필요
- 모델 로딩은 하드웨어에 따라 2-5분 소요
- 실용적인 추론 속도를 위해 GPU 가속 필요
- 여러 어댑터는 메모리 사용량과 로딩 시간 증가

## 참고 자료

- [PEFT 문서](https://huggingface.co/docs/peft)
- [LoRA 논문](https://arxiv.org/abs/2106.09685)
- [Alpaca 모델](https://github.com/tloen/alpaca-lora)
- [Guanaco 데이터셋](https://huggingface.co/datasets/timdettmers/openassistant-guanaco)
