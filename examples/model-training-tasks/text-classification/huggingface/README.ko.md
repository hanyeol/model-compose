# 텍스트 분류 + LoRA 모델 트레이너 예제

이 예제는 model-compose의 `model-trainer` 컴포넌트를 HuggingFace 드라이버의 `text-classification` 태스크로 사용해 시퀀스 분류기를 파인튜닝하는 방법을 보여줍니다. GLUE SST-2에서 BERT-base에 LoRA 어댑터를 붙여 이진 감성 분류(positive/negative)를 학습합니다.

## 개요

이 워크플로우는 다음과 같은 선언적 Classification+LoRA 학습 루프를 제공합니다:

1. **HuggingFace Trainer**: `transformers.Trainer`를 `TrainingArguments`, `AutoModelForSequenceClassification`과 함께 감쌉니다
2. **LoRA 어댑터**: BERT의 `query`/`value` 프로젝션에 rank-8 LoRA 어댑터를 붙입니다
3. **자동 모델 프로비저닝**: 첫 실행 시 `bert-base-uncased`를 다운로드합니다
4. **GLUE SST-2 데이터셋**: GLUE의 SST-2 감성 데이터셋을 로드하고 `sentence` 컬럼으로 학습합니다
5. **안전한 Split 선택**: 평가용으로 `validation` split을 자동 선택합니다 (SST-2의 `test` split은 라벨이 마스킹되어 있어 드라이버가 이를 거부하고 fallthrough)
6. **체크포인트 출력**: 학습된 어댑터를 `output_dir` 아래에 저장하고 학습 지표를 반환합니다

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `torch`, `transformers`, `datasets`, `peft`, `accelerate`가 있는 Python 환경 (컴포넌트의 `_get_setup_requirements`에서 자동 관리됨)
- **VRAM ≥ 4 GB**의 GPU 권장. 다만 이 예제는 작아서 3 에폭 학습이 **CPU에서 ~30분**이면 됩니다.
- BERT 가중치와 SST-2 데이터셋 캐시를 위한 **디스크 ~1 GB**

### 왜 Classification + LoRA인가

- **시퀀스 분류**는 감성/토픽/의도 라벨링의 표준 태스크입니다. `AutoModelForSequenceClassification`은 베이스 트랜스포머 위에 선형 분류 헤드를 추가합니다.
- **LoRA** rank 8은 BERT 파라미터의 ~0.3%만 학습 가능하게 하면서도 GLUE 규모의 태스크에서 대체로 full-fine-tune 정확도에 근접합니다.
- **SST-2**는 표준 이진 감성 벤치마크입니다 (67k 학습 예제). 배치 크기 32에서 1~3 에폭이면 수렴합니다.

### 환경 구성

이 예제 디렉토리로 이동합니다:
```bash
cd examples/model-training-tasks/text-classification/huggingface
```

별도의 환경 구성은 필요하지 않습니다.

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
         "num_epochs": 3,
         "batch_size": 32,
         "learning_rate": 5e-5
       }
     }'
   ```

   **웹 UI 사용:**
   - http://localhost:8081 열기
   - 원하는 대로 `num_epochs`, `batch_size`, `learning_rate` 조정
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"num_epochs": 3}'
   ```

3. **학습된 어댑터 확인:**
   ```bash
   ls ./output/classification
   # adapter_config.json  adapter_model.safetensors  tokenizer_config.json  ...
   ```

## 컴포넌트 상세

### Model-Trainer 컴포넌트 (기본)

- **Type**: `model-trainer`
- **Task**: `text-classification`
- **Driver**: `huggingface`
- **베이스 모델**: `bert-base-uncased`
- **LoRA 구성**:
  - rank: 8
  - alpha: 16
  - dropout: 0.05
  - target_modules: `query`, `value` (BERT self-attention 이름)
- **Label Names**: `[negative, positive]` (저장된 체크포인트에 `id2label` / `label2id`가 함께 저장됨)

### 모델 정보: bert-base-uncased

- **개발자**: Google Research
- **파라미터**: 1억 1천만 개
- **유형**: encoder-only 양방향 트랜스포머
- **라이선스**: Apache 2.0
- **LoRA 적용 후 학습 파라미터**: ~300K (~0.3%)

## 워크플로우 상세

### "Fine-tune BERT for SST-2 Sentiment Classification" 워크플로우 (기본)

**설명**: LoRA 어댑터로 BERT-base를 GLUE SST-2에서 이진 감성 분류로 파인튜닝한 뒤 체크포인트 디렉토리와 학습 지표를 반환합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|-----|--------|------|
| `dataset_path` | string | 아니오 | `stanfordnlp/sst2` | HuggingFace 데이터셋 repo id. 다중 config repo(예: `nyu-mll/glue`)에는 `dataset_name`도 함께 지정 |
| `dataset_name` | string | 아니오 | *(미설정)* | 다중 config repo용 config 이름 (예: `nyu-mll/glue` 하의 `sst2`, `mrpc`, `cola`) |
| `text_column` | string | 아니오 | `sentence` | 입력 텍스트가 있는 컬럼 |
| `label_column` | string | 아니오 | `label` | 정수 클래스 라벨이 있는 컬럼 |
| `label_names` | list | 아니오 | `["negative", "positive"]` | id 순서의 사람이 읽을 수 있는 클래스 이름. 데이터셋의 클래스 개수와 길이가 일치해야 함 |
| `num_epochs` | int | 아니오 | `3` | 학습 에폭 수 |
| `batch_size` | int | 아니오 | `32` | 디바이스당 학습 배치 크기 |
| `learning_rate` | float | 아니오 | `5e-5` | AdamW 초기 학습률 |
| `output_dir` | string | 아니오 | `./output/classification` | 학습된 어댑터가 저장되는 위치 |

#### 출력 형식

| 필드 | 타입 | 설명 |
|-----|------|------|
| `output_dir` | string | 저장된 LoRA 어댑터 + 토크나이저가 있는 디렉토리 |
| `train_loss` | float | 최종 학습 손실 |
| `metrics` | object | 전체 `Trainer.train()` 지표 (train_runtime, samples_per_second, ...) |

## 라벨 처리

드라이버는 라벨 리스트를 다음 우선순위로 결정합니다:

1. **action config의 명시적 `label_names`** (이 예제는 `[negative, positive]` 사용)
2. **데이터셋 라벨 feature의 `ClassLabel.names`** (SST-2도 이 정보를 가짐)
3. **split에서 서로 다른 값 스캔**

결정된 `num_labels`와 `id2label` / `label2id` 매핑이 `AutoModelForSequenceClassification.from_pretrained`에 전달되어 분류 헤드의 출력 크기가 올바르게 잡히고, 저장된 체크포인트가 예측을 사람이 읽을 수 있는 라벨로 디코딩할 수 있습니다.

데이터셋의 원본 라벨 값이 비연속적이면(예: `{0, 1}` 대신 `{1, 2}`), 드라이버가 자동으로 `label_remap`을 만들어 학습 전에 라벨을 다시 씁니다. 정수가 아닌 라벨(float, string, None)은 조용히 강제 변환되지 않고 학습 시작 시점에 명시적으로 거부됩니다.

## Split 처리

`_load_datasets`는 평가 split을 `validation` → `eval` → `test` 순으로 시도합니다. GLUE SST-2의 `test` split은 모든 라벨이 `-1`로 마스킹되어 있어 드라이버가 이를 감지하고 `validation`으로 fallthrough합니다. 즉:

- `path: nyu-mll/glue, name: sst2`로 설정하면 학습에는 `train`을, 평가에는 `validation`을 자동으로 씁니다.
- 어떤 후보에도 사용 가능한 라벨이 없으면 임의의 split으로 fallback하지 않고 평가를 건너뜁니다.

## 시스템 요구사항

### 최소 사양

- **CPU**: 현대적인 멀티코어 CPU 아무거나
- **RAM**: 4 GB
- **디스크**: 2 GB
- **학습 시간**: CPU에서 3 에폭 ~30분 (Apple Silicon: ~15분)

### 권장 사양

- **GPU**: VRAM ≥ 4 GB의 CUDA GPU 아무거나 (아주 가벼운 워크로드)
- **학습 시간**: RTX 3060에서 3 에폭 ~5분

## 커스터마이징

### 다른 분류 데이터셋 사용

모든 데이터셋 형태의 입력은 런타임에 override 가능합니다 — YAML 편집이 필요 없습니다.

CoLA (문법 수용 가능성, 2 클래스, `nyu-mll/glue` 다중 config repo 안에 존재):

```bash
model-compose run --input '{
  "dataset_path": "nyu-mll/glue",
  "dataset_name": "cola",
  "text_column": "sentence",
  "label_names": ["unacceptable", "acceptable"]
}'
```

AG News (4 클래스 뉴스 토픽, 단일 config repo):

```bash
model-compose run --input '{
  "dataset_path": "ag_news",
  "text_column": "text",
  "label_names": ["world", "sports", "business", "sci-tech"]
}'
```

### QLoRA 사용 (4비트 양자화 베이스)

`deberta-v3-large` 같은 더 큰 encoder의 경우:

```yaml
component:
  type: model-trainer
  task: text-classification
  driver: huggingface
  model: microsoft/deberta-v3-large
  lora:
    rank: 8
    alpha: 16
    target_modules: [query_proj, value_proj]
  quantization:
    type: nf4
    compute_dtype: bfloat16
  action:
    dataset: ${jobs.load-dataset.output}
    text_column: sentence
    label_names: [negative, positive]
```

참고: 양자화는 `lora` 설정을 요구합니다(드라이버가 그 외 조합을 거부).

### datasets 컴포넌트와 체이닝

한 job에서 데이터셋을 미리 로드하고 셔플한 뒤 트레이너에 전달합니다:

```yaml
components:
  - id: sst2
    type: datasets
    driver: huggingface
    action:
      method: load
      path: glue
      name: sst2
      shuffle: true

  - id: trainer
    type: model-trainer
    task: text-classification
    driver: huggingface
    model: bert-base-uncased
    lora:
      rank: 8
      target_modules: [query, value]
    action:
      dataset: ${jobs.load-data.output}
      text_column: sentence
      label_names: [negative, positive]
      output_dir: ./output/classification

workflow:
  jobs:
    - id: load-data
      component: sst2
    - id: train
      component: trainer
      depends_on: [load-data]
```

## 트러블슈팅

- **`num_labels` 불일치 오류**: 데이터셋의 서로 다른 라벨 수가 선언한 것과 다릅니다. `label_names`를 제거해 드라이버가 자동 감지하게 하거나 리스트를 고치세요.
- **정수가 아닌 라벨 거부**: 드라이버는 float/bool/string 라벨을 거부합니다 — `int(0.8)`은 조용히 0으로 뭉개지기 때문입니다. 학습 전에 라벨을 버킷화하거나 캐스팅하세요.
- **CPU에서 학습 느림**: 예상된 동작 — BERT의 CPU 추론은 괜찮지만 배치 32의 학습은 무겁습니다. `batch_size`를 줄이거나 GPU를 쓰세요.
- **`datasets` 버전 비호환**: 드라이버는 `datasets>=2.14,<4.0`으로 고정합니다. 전역에 더 최신 버전이 있어도 model-compose의 격리된 런타임이 고정 버전을 설치합니다.

## 학습된 분류기 사용

학습 후 `text-classification` 태스크의 `model` 컴포넌트로 어댑터를 로드합니다:

```yaml
component:
  type: model
  task: text-classification
  model: bert-base-uncased
  peft_adapters:
    - type: lora
      model: ./output/classification
  action:
    text: ${input.text}
```

어댑터 체크포인트에 `id2label`이 저장되어 있으므로 출력이 `0` / `1`이 아닌 `"positive"` / `"negative"`로 나옵니다.

## 관련 예제

- `examples/model-training-tasks/sft-lora/huggingface/` — Alpaca instruction 데이터셋에서의 TinyLlama SFT+LoRA
- `examples/model-tasks/text-classification/` — 사전학습된(또는 여러분이 파인튜닝한) 분류기를 추론에 사용
