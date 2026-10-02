# typed-decision 모델 파인튜닝 · Nimble 드라이버

[Bespoke Nimble](https://github.com/bespokelabsai/nimble)의 candidate-token cross-entropy를 통해 Qwen3.5-9B에 LoRA 어댑터를 붙여 라벨링된 `{state, schema, answers}` 데이터셋으로 파인튜닝합니다.

트레이너는 [mindor-nimble-trainer](https://github.com/hanyeol/mindor-nimble-trainer) 패키지를 통해 연결됩니다. 이 패키지는 `nimble.training.schema_train`의 primitives (`CandidateCollator`, `CandidateTrainer`, `prepare_prompts`, `choice_key`, `load_base`)를 재사용하면서 그 위에 model-compose 친화적인 데이터셋 형태를 얹습니다.

## 데이터셋 포맷

각 라인은 JSON 객체입니다:

```json
{
  "state": "User said: book me a flight to Tokyo tomorrow.",
  "schema": {
    "intent":   { "type": "choice", "options": ["buy", "ask", "complain"] },
    "urgent":   { "type": "noul" },
    "priority": { "type": "score", "options": ["low", "medium", "high"] }
  },
  "answers": {
    "intent":   "buy",
    "urgent":   true,
    "priority": "high"
  }
}
```

각 행은 응답이 있는 스키마 필드마다 하나의 학습 예제로 확장됩니다. Nimble은 모든 필드를 독립적인 candidate-classification 예제로 다룹니다. 트레이너는 필드를 상류 `prepare_prompts()`가 기대하는 형태(`choice`는 명시적 choices, `score`는 숫자 문자열 레벨, `noul`은 옵션 없음)로 재정규화합니다.

3행짜리 토이 데이터셋이 [`train.jsonl`](./train.jsonl)에 포함되어 있습니다.

## 실행

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/nimble",
  "num_epochs": 3
}'
```

출력 디렉토리는 `schema_config.json`과 함께 HuggingFace 스타일 LoRA 어댑터 디렉토리입니다. 상류 `nimble.training.schema_train`이 작성하는 결과물과 동일합니다. `typed-decision` 추론 컴포넌트에서 로드하면 됩니다:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: nimble
    model: ./output/nimble
    base_model: Qwen/Qwen3.5-9B
```

## 플랫폼

Nimble의 CUDA 스코어러는 `torch>=2.8`과 bf16 지원 GPU가 필요합니다. 트레이너도 동일한 핀을 상속합니다. Apple Silicon에서는 MLX / `mlx-lm` 위에서 돌고, Linux x86_64 또는 aarch64에서는 CUDA 위에서 돕니다. 그 외 플랫폼(Darwin x86_64, Windows)은 Nimble 상류가 지원하지 않으므로 셋업 단계에서 실패합니다.
