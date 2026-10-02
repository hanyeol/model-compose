# typed-decision 모델 파인튜닝 · Kev 드라이버

[Kev](https://github.com/jaredpalmer/kev)의 LoRA 어댑터와 pointer head를 라벨링된 `{state, schema, answers}` 데이터셋에서 공동 학습합니다.

Kev의 상류 학습은 자체 suite / manifest 레이아웃에 묶인 1000+ 줄 CLI 스크립트입니다. 이 예제는 그 핵심 학습 루프(bf16 LoRA + pointer head, 질문별 `kev.train.question_loss`)를 [mindor-kev-trainer](https://github.com/hanyeol/mindor-kev-trainer) 패키지를 통해 돌립니다. 이 패키지는 루프를 평범한 `train(dataset, config)` 함수로 재구현했고, 설치된 `kev` 패키지의 `kev.model.DecisionModel`, `kev.model.encode`, `kev.train.question_loss`를 재사용합니다.

## 범위

**지원**: 단일 프로세스 LoRA + pointer-head 학습, bf16/fp16 autocast, linear warmup → linear decay LR 스케줄, 에폭별 체크포인트.

**지원하지 않음**: FSDP2 full fine-tune, Kev의 micro-batch planner, permutation KL 정규화, anchor-KL teacher distribution. 이 기능들은 `python -m kev.train`을 직접 쓰세요.

## 데이터셋 포맷

각 라인은 JSON 객체입니다:

```json
{
  "state": "User said: book me a flight to Tokyo tomorrow.",
  "schema": {
    "intent":   { "type": "choice", "options": ["buy", "ask", "complain"], "instructions": "..." },
    "urgent":   { "type": "noul",   "instructions": "..." },
    "priority": { "type": "score",  "options": ["low", "medium", "high"] }
  },
  "answers": {
    "intent":   "buy",
    "urgent":   true,
    "priority": "high"
  }
}
```

설정된 `max_state_length` / `max_branch_length` 예산을 초과하는 행은 스킵됩니다 (즉석에서 record를 만드는 상류 정책과 동일).

3행짜리 토이 데이터셋이 [`train.jsonl`](./train.jsonl)에 포함되어 있습니다.

## 실행

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/kev",
  "num_epochs": 3
}'
```

출력 디렉토리에는 LoRA 어댑터와 `pointer_head.pt`가 포함되어 있습니다. Kev의 표준 로더로 로드하면 됩니다:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: kev
    model: ./output/kev
```

## Loss

질문별 loss는 `kev.train.question_loss`를 그대로 사용합니다:

- `choice`: 옵션에 대한 cross-entropy (`question["target"]`을 통해 soft target 지원).
- `noul`: `(false, true)`에 대한 cross-entropy.
- `score`: cross-entropy에 ordinal ranked-probability-score 항을 더한 값 (트레이너의 `ord_weight`로 조정, 기본값 0.5).
