# 9. 모델 훈련

> **⚠️ 개발 상태**: 이 기능은 현재 개발 중입니다. 설정 스키마는 정의되어 있지만 훈련 실행 서비스는 아직 구현되지 않았습니다. 향후 릴리스에서 업데이트될 예정입니다.

이 장에서는 model-compose를 사용한 모델 훈련 설정 방법을 설명합니다.

---

## 9.1 훈련 개요

### 9.1.1 지원 훈련 태스크

model-compose는 다음 훈련 태스크를 위한 설정을 제공합니다:

- **SFT (Supervised Fine-Tuning)**: 지도 학습 기반 파인튜닝
- **Classification**: 분류 모델 훈련

### 9.1.2 훈련 컴포넌트 구조

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft                      # 또는 classification

    # LoRA 설정 (선택사항)
    peft_adapter: lora
    lora_r: 8
    lora_alpha: 16

    # 훈련 파라미터
    learning_rate: 5e-5
    num_epochs: 3
    output_dir: ./trained-model
```

---

## 9.2 데이터셋 준비

### 9.2.1 데이터셋 컴포넌트 개요

데이터셋 컴포넌트는 훈련용 데이터를 준비하는 도구를 제공합니다.

**지원 기능:**
- HuggingFace Hub에서 데이터셋 로드
- 로컬 파일에서 데이터셋 로드
- 데이터셋 병합 및 변환
- 행/열 선택 및 필터링

### 9.2.2 HuggingFace 데이터셋 로드

**기본 설정:**

```yaml
components:
  - id: dataset-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca          # HuggingFace Hub 경로
    split: train                    # train, test, validation 등
    fraction: 1.0                   # 전체 데이터의 비율 (0.0 ~ 1.0)
```

**고급 설정:**

```yaml
components:
  - id: dataset-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca
    name: default                   # 데이터셋 설정 이름
    split: train
    fraction: 0.1                   # 10%만 사용
    streaming: false                # 스트리밍 모드
    cache_dir: ./cache/datasets     # 캐시 디렉토리
    revision: main                  # Git 리비전
    trust_remote_code: false        # 원격 코드 실행 허용
    token: ${env.HF_TOKEN}          # HuggingFace 토큰
    shuffle: true                   # 데이터 셔플
```

**워크플로우 예제:**

```yaml
workflows:
  - id: load-training-data
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: ${input.dataset | tatsu-lab/alpaca}
          split: train
          fraction: 1.0
        output: ${output}
```

### 9.2.3 로컬 데이터셋 로드

**JSON 파일:**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: json                    # json, csv, parquet, text
    data_files: ./data/train.json   # 파일 경로
```

**CSV 파일:**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: csv
    data_files:
      - ./data/train.csv
      - ./data/validation.csv
```

**디렉토리:**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: json
    data_dir: ./data/training       # 디렉토리 내 모든 JSON 파일
```

### 9.2.4 데이터셋 조작

**데이터셋 병합:**

```yaml
workflows:
  - id: merge-datasets
    jobs:
      - id: load-first
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: load-second
        component: dataset-loader
        input:
          path: yahma/alpaca-cleaned
          split: train

      - id: concat
        component: dataset-ops
        method: concat
        input:
          datasets:
            - ${jobs.load-first.output}
            - ${jobs.load-second.output}
        depends_on: [ load-first, load-second ]
```

**열 선택:**

```yaml
workflows:
  - id: select-columns
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: select
        component: dataset-ops
        method: select
        input:
          dataset: ${jobs.load.output}
          axis: columns
          columns: [ instruction, input, output ]
        depends_on: [ load ]
```

**행 선택:**

```yaml
workflows:
  - id: select-rows
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: select
        component: dataset-ops
        method: select
        input:
          dataset: ${jobs.load.output}
          axis: rows
          indices: [ 0, 1, 2, 3, 4 ]    # 처음 5개 행
        depends_on: [ load ]
```

**데이터 필터링:**

```yaml
components:
  - id: dataset-ops
    type: datasets
    method: filter
    dataset: ${input.dataset}
    condition: ${input.condition}    # 필터 조건
```

**데이터 매핑:**

```yaml
components:
  - id: dataset-ops
    type: datasets
    method: map
    dataset: ${input.dataset}
    template: ${input.template}      # 데이터 변환 템플릿
```

### 9.2.5 데이터셋 형식

**SFT 훈련용 데이터 형식:**

1. **단일 텍스트 열:**
```json
{
  "text": "Complete training text here..."
}
```

2. **프롬프트-응답 형식:**
```json
{
  "prompt": "User question or instruction",
  "response": "Model's expected response"
}
```

3. **Instruction 형식 (Alpaca 스타일):**
```json
{
  "instruction": "Task instruction",
  "input": "Optional context",
  "output": "Expected output"
}
```

4. **대화 형식:**
```json
{
  "system": "You are a helpful assistant",
  "prompt": "User message",
  "response": "Assistant response"
}
```

---

## 9.3 훈련 설정

### 9.3.1 기본 훈련 설정

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 데이터셋
    dataset: ${input.dataset}

    # 학습률 및 배치 크기
    learning_rate: 5e-5
    per_device_train_batch_size: 8
    per_device_eval_batch_size: 8
    num_epochs: 3

    # 출력 디렉토리
    output_dir: ./output/model
```

### 9.3.2 옵티마이저 설정

**지원 옵티마이저:**

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    optimizer: adamw_torch          # 기본값
```

**옵티마이저 종류:**

**AdamW 변형:**
- `adamw_torch`: PyTorch 기본 AdamW
- `adamw_torch_fused`: Fused AdamW (더 빠름)
- `adamw_8bit`: 8-bit AdamW (메모리 절약)
- `adamw_bnb_8bit`: BitsAndBytes 8-bit AdamW

**메모리 효율적 옵티마이저:**
- `adafactor`: Adafactor (메모리 효율적)
- `lomo`: LOMO (Low-Memory Optimization)
- `galore_adamw`: GaLore AdamW
- `galore_adamw_8bit`: GaLore AdamW 8-bit

**고급 옵티마이저:**
- `grokadamw`: Grok AdamW
- `stableadamw`: Stable AdamW
- `schedule_free_radamw`: Schedule-Free RAdamW

**전통적 옵티마이저:**
- `sgd`: Stochastic Gradient Descent
- `adagrad`: Adagrad
- `rmsprop`: RMSprop

### 9.3.3 학습률 스케줄러

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    lr_scheduler_type: linear       # 기본값
    warmup_steps: 100
```

**스케줄러 종류:**

- `linear`: 선형 감소
- `cosine`: 코사인 감소
- `cosine_with_restarts`: 재시작이 있는 코사인
- `polynomial`: 다항식 감소
- `constant`: 고정 학습률
- `constant_with_warmup`: Warmup 후 고정
- `inverse_sqrt`: 역제곱근 감소
- `reduce_lr_on_plateau`: 성능 정체 시 감소
- `cosine_with_min_lr`: 최소 학습률이 있는 코사인
- `warmup_stable_decay`: Warmup-Stable-Decay

### 9.3.4 최적화 설정

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 가중치 감소 (정규화)
    weight_decay: 0.01

    # 그래디언트 클리핑
    max_grad_norm: 1.0

    # 그래디언트 누적
    gradient_accumulation_steps: 4
```

**그래디언트 누적:**
- 효과적인 배치 크기 = `per_device_train_batch_size × gradient_accumulation_steps × num_gpus`
- 메모리 부족 시 배치 크기를 줄이고 누적 스텝을 증가

### 9.3.5 평가 및 저장

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 평가
    eval_steps: 500                 # 500 스텝마다 평가
    eval_dataset: ${input.eval_dataset}

    # 체크포인트 저장
    save_steps: 500                 # 500 스텝마다 저장

    # 로깅
    logging_steps: 10               # 10 스텝마다 로그
```

### 9.3.6 메모리 최적화

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 그래디언트 체크포인팅
    gradient_checkpointing: true    # 메모리 절약, 속도 감소

    # 혼합 정밀도
    fp16: true                      # FP16 (V100, RTX 시리즈)
    # 또는
    bf16: true                      # BF16 (A100, H100 권장)
```

**메모리 최적화 옵션:**
- `gradient_checkpointing`: 메모리를 약 30-40% 절약, 속도 약 20% 감소
- `fp16`: FP16 혼합 정밀도, 메모리 절약 및 속도 향상
- `bf16`: BF16 혼합 정밀도, 수치 안정성 우수 (Ampere 이상 GPU)

### 9.3.7 재현성 설정

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    seed: 42                        # 랜덤 시드
```

---

## 9.4 파인튜닝

### 9.4.1 SFT (Supervised Fine-Tuning)

**기본 설정:**

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    # 데이터셋
    dataset: ${input.dataset}
    eval_dataset: ${input.eval_dataset}

    # 데이터 형식
    text_column: text               # 단일 텍스트 열
    max_seq_length: 512

    # 훈련 설정
    learning_rate: 5e-5
    num_epochs: 3
    per_device_train_batch_size: 4
    output_dir: ./output/sft-model
```

**프롬프트-응답 형식:**

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    dataset: ${input.dataset}

    # 대화 형식
    prompt_column: prompt
    response_column: response
    system_column: system           # 선택사항

    max_seq_length: 1024
```

**데이터 검증:**
- `text_column` 또는 `prompt_column` + `response_column` 중 하나 필수
- 둘 다 지정하면 오류 발생

### 9.4.2 시퀀스 패킹

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    dataset: ${input.dataset}
    text_column: text

    # 시퀀스 패킹
    packing: true                   # 짧은 샘플을 하나의 시퀀스로 결합
    max_seq_length: 512
```

**패킹 장점:**
- 짧은 샘플이 많을 때 훈련 효율 향상
- GPU 사용률 증가
- 훈련 시간 단축

**패킹 단점:**
- 샘플 경계가 명확하지 않을 수 있음
- 일부 태스크에서 성능 저하 가능

---

## 9.5 LoRA 훈련

### 9.5.1 LoRA 개요

LoRA (Low-Rank Adaptation)는 대규모 모델을 효율적으로 파인튜닝하는 기법입니다.

**장점:**
- 훈련 가능한 파라미터 수 대폭 감소 (1% 미만)
- 메모리 사용량 감소
- 훈련 속도 향상
- 여러 LoRA 어댑터를 하나의 베이스 모델에 적용 가능

### 9.5.2 기본 LoRA 설정

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft

    # LoRA 활성화
    peft_adapter: lora

    # LoRA 하이퍼파라미터
    lora_r: 8                       # LoRA rank (낮을수록 메모리 절약)
    lora_alpha: 16                  # LoRA scaling (일반적으로 r의 2배)
    lora_dropout: 0.05              # 드롭아웃 비율

    # 데이터셋 및 훈련 설정
    dataset: ${input.dataset}
    learning_rate: 1e-4             # LoRA는 일반적으로 높은 학습률
    num_epochs: 3
    output_dir: ./output/lora-adapter
```

### 9.5.3 타겟 모듈 설정

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft
    peft_adapter: lora

    # 타겟 모듈 지정
    lora_target_modules:
      - q_proj                      # Query projection
      - v_proj                      # Value projection
      - k_proj                      # Key projection
      - o_proj                      # Output projection

    lora_r: 16
    lora_alpha: 32
```

**일반적인 타겟 모듈:**
- **Transformer Attention**: `q_proj`, `k_proj`, `v_proj`, `o_proj`
- **MLP**: `gate_proj`, `up_proj`, `down_proj`
- **Embedding**: `embed_tokens`, `lm_head`

**타겟 모듈 선택 가이드:**
- 더 많은 모듈: 성능 향상, 메모리 증가
- Attention만: 메모리 효율적, 대부분의 경우 충분
- Attention + MLP: 더 나은 성능, 메모리 증가

### 9.5.4 LoRA Bias 설정

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft
    peft_adapter: lora

    lora_bias: none                 # none, all, lora_only
```

**Bias 옵션:**
- `none`: Bias 훈련 안 함 (기본값, 메모리 효율적)
- `all`: 모든 Bias 훈련
- `lora_only`: LoRA 레이어의 Bias만 훈련

### 9.5.5 QLoRA (Quantized LoRA)

QLoRA는 양자화된 베이스 모델에 LoRA를 적용하여 메모리를 더욱 절약합니다.

```yaml
components:
  - id: qlora-trainer
    type: model-trainer
    task: sft

    # LoRA 설정
    peft_adapter: lora
    lora_r: 64
    lora_alpha: 16

    # 4-bit 양자화
    quantization: nf4               # int4 또는 nf4
    bnb_4bit_compute_dtype: bfloat16
    bnb_4bit_use_double_quant: true

    # 데이터셋 및 훈련
    dataset: ${input.dataset}
    learning_rate: 2e-4
    num_epochs: 1
    per_device_train_batch_size: 4
    gradient_accumulation_steps: 4

    # 메모리 최적화
    gradient_checkpointing: true
    bf16: true
```

**양자화 옵션:**
- `nf4`: NormalFloat 4-bit (권장)
- `int4`: 4-bit 정수 양자화
- `int8`: 8-bit 정수 양자화

**QLoRA 권장 설정:**
- 더 높은 `lora_r` (64 이상)
- 더 높은 학습률 (2e-4)
- BF16 혼합 정밀도
- 그래디언트 체크포인팅

### 9.5.6 LoRA 하이퍼파라미터 가이드

| 파라미터 | 낮은 값 | 높은 값 | 권장 사용 |
|---------|---------|---------|-----------|
| `lora_r` | 4-8 | 64-128 | 일반: 8-16, QLoRA: 64 |
| `lora_alpha` | 8-16 | 32-64 | 일반적으로 r의 2배 |
| `lora_dropout` | 0.0 | 0.1 | 작은 데이터셋: 0.05-0.1 |
| `learning_rate` | 1e-5 | 5e-4 | Full FT: 5e-5, LoRA: 1e-4 |

---

## 9.6 훈련 모니터링

### 9.6.1 로깅 설정

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # 로깅
    logging_steps: 10               # 로그 출력 간격
    eval_steps: 100                 # 평가 간격
```

**예상 로그 출력:**
- Training loss
- Learning rate
- Gradient norm
- Training speed (samples/sec)

### 9.6.2 평가 메트릭

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    eval_dataset: ${input.eval_dataset}
    eval_steps: 500
```

**예상 평가 메트릭:**
- Evaluation loss
- Perplexity
- Task-specific metrics (classification accuracy 등)

### 9.6.3 TensorBoard 통합 (예정)

향후 릴리스에서 TensorBoard 통합이 추가될 예정입니다:

```bash
# 예상 사용법
tensorboard --logdir ./output/runs
```

---

## 9.7 체크포인트 관리

### 9.7.1 체크포인트 저장

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    output_dir: ./output/checkpoints
    save_steps: 500                 # 500 스텝마다 저장
```

**예상 디렉토리 구조:**
```
output/checkpoints/
  ├── checkpoint-500/
  │   ├── model.safetensors
  │   ├── config.json
  │   ├── training_args.bin
  │   └── optimizer.pt
  ├── checkpoint-1000/
  └── checkpoint-1500/
```

### 9.7.2 체크포인트에서 재개

향후 릴리스에서 지원 예정:

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    resume_from_checkpoint: ./output/checkpoints/checkpoint-1000
```

### 9.7.3 최종 모델 저장

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    output_dir: ./output/final-model
```

**예상 최종 모델 구조:**
```
output/final-model/
  ├── model.safetensors
  ├── config.json
  ├── tokenizer.json
  ├── tokenizer_config.json
  └── special_tokens_map.json
```

---

## 9.8 실전 예제

### 9.8.1 Alpaca 스타일 파인튜닝

```yaml
components:
  - id: alpaca-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca
    split: train

  - id: alpaca-trainer
    type: model-trainer
    task: sft

    # LoRA 설정
    peft_adapter: lora
    lora_r: 16
    lora_alpha: 32
    lora_dropout: 0.05
    lora_target_modules: [q_proj, v_proj]

    # 데이터 설정
    dataset: ${input.dataset}
    prompt_column: instruction
    response_column: output
    max_seq_length: 512

    # 훈련 설정
    learning_rate: 1e-4
    num_epochs: 3
    per_device_train_batch_size: 4
    gradient_accumulation_steps: 4

    # 최적화
    gradient_checkpointing: true
    fp16: true

    output_dir: ./output/alpaca-lora

workflows:
  - id: train-alpaca
    jobs:
      - id: load-data
        component: alpaca-loader

      - id: train
        component: alpaca-trainer
        input:
          dataset: ${jobs.load-data.output}
        depends_on: [load-data]
```

### 9.8.2 QLoRA로 대규모 모델 훈련

```yaml
components:
  - id: qlora-trainer
    type: model-trainer
    task: sft

    # QLoRA 설정
    peft_adapter: lora
    lora_r: 64
    lora_alpha: 16
    quantization: nf4
    bnb_4bit_compute_dtype: bfloat16

    # 데이터
    dataset: ${input.dataset}
    text_column: text
    max_seq_length: 2048
    packing: true

    # 훈련
    learning_rate: 2e-4
    num_epochs: 1
    per_device_train_batch_size: 1
    gradient_accumulation_steps: 16

    # 최적화
    optimizer: adamw_8bit
    gradient_checkpointing: true
    bf16: true

    output_dir: ./output/qlora-model
```

### 9.8.3 커스텀 데이터셋 준비 및 훈련

```yaml
components:
  - id: local-data
    type: datasets
    provider: local
    loader: json
    data_files: ./data/custom_train.json

  - id: data-processor
    type: datasets
    method: map

  - id: custom-trainer
    type: model-trainer
    task: sft

    peft_adapter: lora
    lora_r: 8
    lora_alpha: 16

    dataset: ${input.dataset}
    prompt_column: user_input
    response_column: assistant_response

    learning_rate: 5e-5
    num_epochs: 5
    per_device_train_batch_size: 8

    output_dir: ./output/custom-model

workflows:
  - id: train-custom
    jobs:
      - id: load
        component: local-data

      - id: process
        component: data-processor
        input:
          dataset: ${jobs.load.output}
          template: ${input.template}
        depends_on: [load]

      - id: train
        component: custom-trainer
        input:
          dataset: ${jobs.process.output}
        depends_on: [process]
```

---

## 다음 단계

데이터셋 준비 방법을 익혔다면:

- **10장**: 외부 서비스 통합 - API 서비스 활용
- **8장**: 로컬 AI 모델 사용 - LoRA 어댑터 로드 및 추론

현재 사용 가능한 기능:
- 데이터셋 로드 및 조작 (HuggingFace, 로컬 파일)
- 데이터셋 병합, 필터링, 선택
- LoRA 어댑터를 사용한 추론 (8장 참조)

향후 추가될 기능:
- 모델 훈련 실행
- 체크포인트 관리
- 훈련 모니터링 및 시각화

---

**다음 장**: [10. 외부 서비스 통합](./10-external-service-integration.md)
