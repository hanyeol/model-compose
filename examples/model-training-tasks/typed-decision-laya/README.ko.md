# typed-decision 모델 파인튜닝 · Laya 드라이버

라벨링된 `{state, schema, answers}` 데이터셋 위에서 [Laya](https://github.com/NandhaKishorM/laya) 인코더 + 질문별 head를 파인튜닝합니다.

Laya의 상류(upstream) 학습은 노트북/참조 스크립트 형태로만 제공됩니다. 이 예제는 그 레시피(RLCD + strictly-proper-scoring-rule 보상 + GRPO 스타일 policy gradient를 soft-target cross-entropy와 혼합, LBFGS 기반 온도 보정)를 [mindor-laya-trainer](https://github.com/hanyeol/mindor-laya-trainer) 패키지를 통해 돌립니다.

## 데이터셋 포맷

각 라인은 JSON 객체이며, 세 개의 필드를 가집니다. typed-decision 추론 입력과 동일한 형태에 정답 `answers` 맵이 추가됩니다:

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

응답 값은 전체 확률 딕셔너리(예: `{"true": 0.9, "false": 0.1}`)로도 줄 수 있습니다. soft target은 상류 노트북이 소비하는 것과 동일한 방식으로 CE 항목을 통해 전파됩니다.

3행짜리 토이 데이터셋이 [`train.jsonl`](./train.jsonl)에 포함되어 있습니다.

## 실행

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/laya",
  "num_epochs": 4
}'
```

출력 디렉토리는 `convaiinnovations/laya` 스냅샷의 drop-in 대체물입니다. 추론 측 `typed-decision` 컴포넌트가 이 경로를 가리키도록 하면 됩니다:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: laya
    model: ./output/laya
    preset: typed-decisions
```

## freeze_encoder

트레이너 컴포넌트에서 `freeze_encoder: true`를 설정하면 질문별 head만 학습합니다. 인코더의 옵티마이저 learning rate가 0으로 고정되므로(gradient checkpointing과 호환되게 `requires_grad`는 건드리지 않음), VRAM도 적게 들고 더 빠릅니다.

## Preset

`preset` 필드는 Laya 번들의 어느 서브폴더에서 warm-start 할지 결정합니다 (`english`, `multilingual`, `typed-decisions`). `typed-decisions` 체크포인트는 이미 typed-decision 태스크 패밀리에 파인튜닝되어 있어, 호환되는 데이터에서 가장 빨리 수렴합니다.
