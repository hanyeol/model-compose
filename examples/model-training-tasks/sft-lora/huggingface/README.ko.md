# SFT + LoRA 모델 트레이너 예제

이 예제는 model-compose의 `model-trainer` 컴포넌트를 HuggingFace 드라이버의 `sft` 태스크로 사용해 인과 언어 모델을 파인튜닝하는 방법을 보여줍니다. TinyLlama-1.1B에 LoRA 어댑터를 붙여 Alpaca instruction 데이터셋으로 지도 파인튜닝(SFT)을 실행합니다.

## 개요

이 워크플로우는 다음과 같은 선언적 SFT+LoRA 학습 루프를 제공합니다:

1. **HuggingFace Trainer**: `trl.SFTTrainer`를 `SFTConfig`(TRL 0.12+ API)와 함께 감쌉니다
2. **LoRA 어댑터**: `q_proj`/`k_proj`/`v_proj`/`o_proj`에 rank-16 LoRA 어댑터를 붙여 전체 파라미터의 ~1%만 학습되도록 합니다
3. **자동 모델 프로비저닝**: 첫 실행 시 TinyLlama를 다운로드해 `~/.cache/huggingface/` 밑에 캐시합니다
4. **Instruction 데이터셋**: `tatsu-lab/alpaca` 데이터셋을 로드하고 `text` 컬럼(사전에 평문화된 instruction/response 프롬프트)으로 학습합니다
5. **체크포인트 출력**: 학습된 LoRA 어댑터를 `output_dir` 아래에 저장하고 학습 지표를 반환합니다

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `torch`, `transformers`, `datasets`, `peft`, `trl`, `accelerate`가 있는 Python 환경 (컴포넌트의 `_get_setup_requirements`에서 자동 관리됨)
- **VRAM ≥ 8 GB**의 GPU 권장. CPU 전용 학습은 가능하지만 이 데이터셋 크기에서 에폭당 수 시간이 걸립니다
- TinyLlama 가중치와 데이터셋 캐시를 위한 **디스크 ~5 GB**

### 왜 SFT + LoRA인가

- **SFT**(지도 파인튜닝)는 짝지어진 prompt/response 텍스트로 베이스 LM에 instruction 추종이나 도메인 적응을 가르치는 표준 방법입니다.
- **LoRA**(Low-Rank Adaptation)는 전체 가중치 행렬 대신 어텐션 프로젝션별로 작은 행렬 쌍만 학습합니다. TinyLlama-1.1B를 rank 16으로 학습하면 학습 가능한 파라미터가 1.1B에서 ~4M으로 줄어들면서 파인튜닝 효과 대부분을 유지합니다.

### 환경 구성

이 예제 디렉토리로 이동합니다:
```bash
cd examples/model-training-tasks/sft-lora/huggingface
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
   ls ./output/sft-lora
   # adapter_config.json  adapter_model.safetensors  tokenizer.json  ...
   ```

## 컴포넌트 상세

### Model-Trainer 컴포넌트 (기본)

- **Type**: `model-trainer`
- **Task**: `sft`
- **Driver**: `huggingface`
- **베이스 모델**: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
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

### "Fine-tune TinyLlama with SFT + LoRA" 워크플로우 (기본)

**설명**: LoRA 어댑터를 사용해 TinyLlama-1.1B를 Alpaca instruction 데이터셋으로 지도 파인튜닝한 뒤 체크포인트 디렉토리와 학습 지표를 반환합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|-----|--------|------|
| `dataset` | string | 아니오 | `tatsu-lab/alpaca` | HuggingFace 데이터셋 이름 또는 로컬 경로 |
| `num_epochs` | int | 아니오 | `1` | 학습 에폭 수 |
| `batch_size` | int | 아니오 | `4` | 디바이스당 학습 배치 크기 |
| `learning_rate` | float | 아니오 | `2e-4` | AdamW 초기 학습률 |
| `output_dir` | string | 아니오 | `./output/sft-lora` | 학습된 어댑터가 저장되는 위치 |

#### 출력 형식

| 필드 | 타입 | 설명 |
|-----|------|------|
| `output_dir` | string | 저장된 LoRA 어댑터 + 토크나이저가 있는 디렉토리 |
| `train_loss` | float | 최종 학습 손실 |
| `metrics` | object | 전체 `Trainer.train()` 지표 (train_runtime, samples_per_second, ...) |

## 시스템 요구사항

### 권장 사양

- **GPU**: VRAM ≥ 8 GB의 NVIDIA GPU (RTX 3060 12GB, T4, A10 이상)
- **RAM**: 16 GB
- **디스크**: 모델 + 데이터셋 캐시 + 체크포인트용 10 GB
- **CUDA**: 11.8+ 와 호환되는 PyTorch

### CPU 전용

동작은 하지만 실용적이지 않을 정도로 느립니다(이 데이터셋에서 에폭당 수 시간). 파이프라인 스모크 테스트 용도로 `num_epochs: 1` + 작은 데이터셋 슬라이스로만 사용하세요.

## 커스터마이징

### QLoRA 사용 (4비트 양자화 베이스)

VRAM이 제한적일 때 더 큰 모델을 다루려면 컴포넌트에 `quantization`을 추가합니다. 양자화는 `lora` 설정을 요구합니다(드라이버가 그 외 조합을 거부).

```yaml
component:
  type: model-trainer
  task: sft
  driver: huggingface
  model: mistralai/Mistral-7B-Instruct-v0.3
  lora:
    rank: 8
    alpha: 16
  quantization:
    type: nf4
    compute_dtype: bfloat16
    double_quant: true
  action:
    dataset: HuggingFaceH4/ultrachat_200k
    text_column: messages       # UltraChat는 대화형 데이터를 제공
    output_dir: ./output/qlora
```

참고: `messages` 경로는 토크나이저에 `chat_template`이 있어야 합니다. Instruct 튜닝된 체크포인트(`*-Instruct-*`, `*-chat`, `*-it`)는 이를 포함하지만, 순수 베이스 체크포인트는 없어서 드라이버가 학습 시작 시 `ValueError`로 거부합니다.

### prompt/response 컬럼 사용

데이터셋이 사전 평문화된 텍스트 필드 대신 prompt/response로 별도 컬럼이 있는 경우:

```yaml
action:
  dataset: my-org/my-dataset
  prompt_column: instruction
  response_column: output
  system_column: system         # 선택
  output_dir: ./output/sft-lora
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
    driver: huggingface
    model: TinyLlama/TinyLlama-1.1B-Chat-v1.0
    lora:
      rank: 16
    action:
      dataset: ${jobs.load-data.output}
      text_column: text
      output_dir: ./output/sft-lora

workflow:
  jobs:
    - id: load-data
      component: alpaca
    - id: train
      component: trainer
      depends_on: [load-data]
```

## 트러블슈팅

- **메모리 부족 (CUDA OOM)**: `batch_size`를 줄이거나(예: `1`), `gradient_checkpointing: true`를 켜거나(이미 켜져 있음), QLoRA(`quantization.type: nf4`)로 전환하세요.
- **`chat_template is None` 오류**: instruct 튜닝된 모델로 바꾸거나 `text_column`을 사전 평문화된 텍스트 필드로 지정하세요.
- **첫 실행이 느림**: TinyLlama(~2 GB)와 Alpaca(~50 MB)는 첫 실행 시 다운로드됩니다. 이후 실행은 캐시를 재사용합니다.
- **`datasets` 버전 비호환**: 드라이버는 `datasets>=2.14,<4.0`으로 고정합니다 — TRL 0.13의 대화형 자동 감지가 datasets 4.0에서 깨지기 때문입니다. 전역에 더 최신 버전이 있어도 model-compose의 격리된 런타임이 고정 버전을 설치합니다.

## 관련 예제

- `examples/model-training-tasks/text-classification/huggingface/` — 텍스트 분류를 위한 GLUE SST-2에서의 BERT + LoRA
- `examples/model-training-tasks/sft-lora/unsloth/` — 동일 워크플로우를 Unsloth의 fused CUDA 커널로 실행 (~2× 처리량, ~30-70% VRAM 절감)
- `examples/model-tasks/chat-completion/huggingface/` — 사전학습된(또는 여러분이 파인튜닝한) chat 모델을 추론에 사용
