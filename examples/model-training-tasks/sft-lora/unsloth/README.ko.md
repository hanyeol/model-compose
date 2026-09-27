# SFT + LoRA 모델 트레이너 예제 (Unsloth)

이 예제는 model-compose의 `model-trainer` 컴포넌트를 **Unsloth** 드라이버의 `sft` 태스크로 사용해 인과 언어 모델을 파인튜닝하는 방법을 보여줍니다. TinyLlama-1.1B에 LoRA 어댑터를 붙여 Alpaca instruction 데이터셋으로 지도 파인튜닝(SFT)을 실행하되, Unsloth의 fused CUDA 커널을 활용해 기본 HuggingFace 백엔드 대비 ~2배의 처리량과 ~30-70%의 VRAM 절감을 얻습니다.

## 개요

이 워크플로우는 다음과 같은 선언적 SFT+LoRA 학습 루프를 제공합니다:

1. **Unsloth Fast 커널**: `FastLanguageModel.from_pretrained`로 베이스 모델을 로드하며, 이 함수가 어텐션과 MLP 레이어를 손수 튜닝된 Triton 커널로 패치합니다
2. **`FastLanguageModel.get_peft_model`을 통한 LoRA 어댑터**: PEFT 래핑은 Unsloth 전용입니다 — 표준 `peft.get_peft_model`은 fast 커널을 우회합니다
3. **자동 모델 프로비저닝**: 첫 실행 시 TinyLlama를 다운로드해 `~/.cache/huggingface/` 밑에 캐시합니다
4. **Instruction 데이터셋**: `tatsu-lab/alpaca` 데이터셋을 로드하고 `text` 컬럼(사전에 평문화된 instruction/response 프롬프트)으로 학습합니다
5. **체크포인트 출력**: 학습된 LoRA 어댑터를 `output_dir` 아래에 저장하고 학습 지표를 반환합니다

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- **CUDA 지원 NVIDIA GPU** — Unsloth는 CUDA 전용 커널(Triton + bitsandbytes + xformers)만 제공합니다. MPS와 CPU는 지원되지 않습니다.
- Compute Capability ≥ 7.0 (Turing / RTX 20xx 이상) 권장. bfloat16 mixed precision을 쓰려면 Ampere+ (RTX 30xx, A100, H100)가 필요합니다.
- `torch`, `unsloth`, `trl`, `huggingface_hub`가 있는 Python 환경 (컴포넌트의 `_get_setup_requirements`에서 자동 관리됨)
- rank 16의 TinyLlama에는 **VRAM ≥ 6 GB**의 GPU 권장. Unsloth의 메모리 효율성 덕분에 4-6 GB 카드에도 이 워크로드가 들어갑니다.
- TinyLlama 가중치와 데이터셋 캐시를 위한 **디스크 ~5 GB**

### 왜 Unsloth인가

Unsloth는 decoder-only 언어 모델의 LoRA/QLoRA 파인튜닝을 위한 drop-in 가속 레이어입니다. 기본 HuggingFace 경로와 비교하면:

- Ampere+ GPU에서 fused 어텐션/MLP 커널로 **~2× 처리량**
- 스마트 activation checkpointing과 4비트 가중치 압축으로 **~30-70% VRAM 절감**
- 트레이너는 **동일한 TRL API** — `SFTTrainer` + `SFTConfig`가 그대로 쓰이며, 가속은 학습 루프가 아니라 모델 래핑에 존재합니다

절충 사항:

- **CUDA 전용**. MPS, CPU, ROCm 미지원 (upstream에서 ROCm 지원을 추가 중이지만 아직 안정 단계는 아닙니다).
- **LoRA/QLoRA 필수**. Full 파인튜닝은 Unsloth 백엔드가 지원하지 않으며, 컴포넌트 config가 로드 시점에 거부합니다.
- **Rope 스케일링이 로드 시점에 고정**됩니다 — component-level의 `max_seq_length`가 결정합니다. Action-level `max_seq_length`는 여전히 per-batch truncation을 제어하지만 component 값을 초과할 수 없습니다.
- **모델 계열 지원**은 decoder-only 아키텍처(Llama, Mistral, Gemma, Qwen, Phi)에 한정됩니다. Encoder 모델(BERT, DeBERTa)은 `FastModel` API를 통한 분류에 지원되지만 이 SFT 드라이버로는 지원되지 않습니다.

### 환경 구성

이 예제 디렉토리로 이동합니다:
```bash
cd examples/model-training-tasks/sft-lora/unsloth
```

별도의 환경 구성은 필요하지 않습니다. 모델과 데이터셋은 워크플로우 첫 실행 시 자동으로 다운로드됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **학습 실행 트리거:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "num_epochs": 1,
         "batch_size": 4,
         "learning_rate": 2e-4
       }
     }'
   ```

   **웹 UI 사용:**
   - http://localhost:8081 열기
   - 원하는 대로 `num_epochs`, `batch_size`, `learning_rate` 조정
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"num_epochs": 1}'
   ```

3. **학습된 어댑터 확인:**
   ```bash
   ls ./output/sft-lora-unsloth
   # adapter_config.json  adapter_model.safetensors  tokenizer.json  ...
   ```

## 컴포넌트 상세

### Model-Trainer 컴포넌트 (기본)

- **Type**: `model-trainer`
- **Task**: `sft`
- **Driver**: `unsloth`
- **베이스 모델**: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- **max_seq_length** (component-level): `2048` — 로드 시점에 rope 스케일링으로 모델에 고정됨
- **LoRA 구성**:
  - rank: 16
  - alpha: 32
  - dropout: 0.05
  - target_modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`

### 모델 정보: TinyLlama-1.1B-Chat-v1.0

- **개발자**: TinyLlama 프로젝트
- **파라미터**: 11억 개
- **유형**: 인과 LM, chat 튜닝
- **라이선스**: Apache 2.0
- **LoRA 적용 후 학습 파라미터**: ~4M (~0.4%)

## 워크플로우 상세

### "Fine-tune TinyLlama with SFT + LoRA (Unsloth)" 워크플로우 (기본)

**설명**: Unsloth의 fast 커널과 LoRA 어댑터로 TinyLlama-1.1B를 Alpaca instruction 데이터셋으로 지도 파인튜닝한 뒤 체크포인트 디렉토리와 학습 지표를 반환합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|-----|--------|------|
| `dataset_path` | string | 아니오 | `tatsu-lab/alpaca` | HuggingFace 데이터셋 repo id 또는 로컬 경로 |
| `dataset_split` | string | 아니오 | `train` | 로드할 데이터셋 split |
| `num_epochs` | int | 아니오 | `1` | 학습 에폭 수 |
| `batch_size` | int | 아니오 | `4` | 디바이스당 학습 배치 크기 |
| `learning_rate` | float | 아니오 | `2e-4` | AdamW 초기 학습률 |
| `output_dir` | string | 아니오 | `./output/sft-lora-unsloth` | 학습된 어댑터가 저장되는 위치 |

#### 출력 형식

| 필드 | 타입 | 설명 |
|-----|------|------|
| `output_dir` | string | 저장된 LoRA 어댑터 + 토크나이저가 있는 디렉토리 |
| `train_loss` | float | 최종 학습 손실 |
| `metrics` | object | 전체 `Trainer.train()` 지표 (train_runtime, samples_per_second, ...) |

## `max_seq_length` 의미론

Unsloth의 `FastLanguageModel.from_pretrained`는 로드 시점에 rope 스케일링을 적용하고 최대 position embedding 크기를 패치된 모델에 고정합니다. 이는 truncation이 per-batch tokenizer 설정인 기본 HuggingFace 드라이버와 다릅니다.

- **`trainer.max_seq_length` (component-level)**: 로드된 모델의 positional 용량을 결정합니다. 하위 액션이 다룰 가장 긴 시퀀스를 감당할 수 있도록 한 번만 설정하세요.
- **`action.max_seq_length`**: SFT config 수준의 per-example truncation은 계속 제어합니다. 미설정 시 토크나이저의 `model_max_length`가 사용됩니다. 이 값은 component-level 값을 초과할 수 없습니다.

대부분의 instruction 튜닝 워크로드에는 component-level 값 `2048`이나 `4096`이 안전한 기본값입니다.

## 시스템 요구사항

### 권장 사양

- **GPU**: VRAM ≥ 6 GB의 NVIDIA GPU (RTX 3060 / T4 / A10 이상). Ampere+ (RTX 30xx, A100, H100)면 bfloat16을 활성화하고 완전한 가속을 얻습니다.
- **RAM**: 16 GB
- **디스크**: 모델 + 데이터셋 캐시 + 체크포인트용 10 GB
- **CUDA**: 11.8+ 와 호환되는 PyTorch

### 최소 사양

- **GPU**: VRAM 4 GB의 Turing (RTX 20xx / T4). 제한된 하드웨어에서 더 큰 모델을 다루려면 `quantization: nf4`와 `batch_size: 1`을 사용하세요.

## 커스터마이징

### QLoRA 사용 (4비트 양자화 베이스)

Unsloth의 가장 큰 이점은 QLoRA를 쓰는 7B+ 모델에서 나타납니다. 컴포넌트에 `quantization`을 추가합니다:

```yaml
component:
  type: model-trainer
  task: sft
  driver: unsloth
  model: mistralai/Mistral-7B-Instruct-v0.3
  max_seq_length: 2048
  lora:
    rank: 8
    alpha: 16
  quantization:
    type: nf4
    compute_dtype: bfloat16
  action:
    dataset: HuggingFaceH4/ultrachat_200k
    text_column: messages       # UltraChat는 대화형 데이터를 제공
    output_dir: ./output/qlora
```

Unsloth 하에서는 `quantization.type: int8`이 `load_in_8bit=True`로 매핑되고, `nf4`/`int4`/`fp4`가 모두 `load_in_4bit=True`로 매핑됩니다. Compute dtype은 `precision`과 GPU의 bfloat16 지원 여부에서 추론됩니다.

참고: `messages` 경로는 토크나이저에 `chat_template`이 있어야 합니다. Instruct 튜닝된 체크포인트(`*-Instruct-*`, `*-chat`, `*-it`)는 이를 포함하지만, 순수 베이스 체크포인트는 없어서 드라이버가 학습 시작 시 `ValueError`로 거부합니다.

### prompt/response 컬럼 사용

데이터셋이 사전 평문화된 텍스트 필드 대신 prompt/response로 별도 컬럼이 있는 경우:

```yaml
action:
  dataset: my-org/my-dataset
  prompt_column: instruction
  response_column: output
  system_column: system         # 선택
  output_dir: ./output/sft-lora-unsloth
```

드라이버는 `dataset.map`으로 정규화된 `messages` 컬럼을 만든 뒤 토크나이저의 chat template로 라우팅합니다. 이 경로에서도 chat template이 필요합니다.

### datasets 컴포넌트와 체이닝

한 job에서 데이터셋을 미리 로드하고 트레이너에 전달합니다:

```yaml
components:
  - id: alpaca
    type: datasets
    driver: huggingface
    action:
      method: load
      path: tatsu-lab/alpaca
      split: train

  - id: trainer
    type: model-trainer
    task: sft
    driver: unsloth
    model: TinyLlama/TinyLlama-1.1B-Chat-v1.0
    max_seq_length: 2048
    lora:
      rank: 16
    action:
      dataset: ${jobs.load-data.output}
      text_column: text
      output_dir: ./output/sft-lora-unsloth

workflow:
  jobs:
    - id: load-data
      component: alpaca
    - id: train
      component: trainer
      depends_on: [load-data]
```

## 트러블슈팅

- **`Unsloth trainer requires 'lora' to be set`**: 이 백엔드는 full 파인튜닝을 지원하지 않습니다. `lora` 블록을 추가하거나 `driver: huggingface`로 전환하세요.
- **`Unsloth trainer requires a CUDA device`**: `device`는 `cuda`, `cuda:N`, 또는 `auto`여야 합니다. MPS와 CPU는 지원되지 않습니다.
- **메모리 부족 (CUDA OOM)**: `batch_size`를 줄이거나(예: `1`), component-level `max_seq_length`를 줄이거나, `quantization: {type: nf4, compute_dtype: bfloat16}`을 추가하세요.
- **첫 실행 시 Triton 컴파일 오류**: Unsloth는 GPU에 맞춰 Triton 커널을 JIT 컴파일합니다. 컴파일 출력은 `~/.triton` 아래 캐시되며 첫 시작이 30-60초 지연될 수 있습니다.
- **첫 실행이 느림**: TinyLlama(~2 GB)와 Alpaca(~50 MB)는 첫 실행 시 다운로드됩니다. 이후 실행은 캐시를 재사용합니다.
- **`chat_template is None` 오류**: instruct 튜닝된 모델로 바꾸거나 `text_column`을 사전 평문화된 텍스트 필드로 지정하세요.

## 관련 예제

- `examples/model-training-tasks/sft-lora/huggingface/` — 동일한 워크플로우의 기본 HuggingFace 백엔드 버전. CUDA가 아닌 하드웨어에서의 비교용
- `examples/model-training-tasks/text-classification/huggingface/` — 텍스트 분류를 위한 GLUE SST-2에서의 BERT + LoRA
- `examples/model-tasks/chat-completion/huggingface/` — 사전학습된(또는 여러분이 파인튜닝한) chat 모델을 추론에 사용
