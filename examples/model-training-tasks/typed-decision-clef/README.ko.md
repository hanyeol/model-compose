# typed-decision 모델 파인튜닝 · Clef 드라이버

[Cloudflare Clef](https://huggingface.co/Cloudflare/clef)의 `joint_schema_model`을 라벨링된 `{state, schema, answers}` 데이터셋으로 파인튜닝합니다.

트레이너는 [mindor-clef-trainer](https://github.com/hanyeol/mindor-clef-trainer) 패키지를 통해 연결됩니다. `model-compose`가 베이스 체크포인트를 프로비저닝하고, 데이터셋을 `clef_trainer.train(...)`에 전달한 뒤, Clef 런타임 글루(프로세서 설정, `joint_schema_model.py`)를 결과 체크포인트 디렉토리에 복사합니다.

## 데이터셋 포맷

각 라인은 JSON 객체이며, 세 개의 필드로 구성됩니다. typed-decision 추론 입력과 동일한 형태에 질문 id로 키가 매핑된 정답 `answers` 맵이 추가됩니다:

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

`noul` 응답은 네이티브 불리언이고, `choice`와 `score` 응답은 옵션 레이블(문자열)입니다. 트레이너는 각 응답을 질문별 loss를 계산하기 전에 정답 logit 인덱스로 변환합니다.

3행짜리 토이 데이터셋이 [`train.jsonl`](./train.jsonl)에 포함되어 있습니다.

## 실행

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/clef",
  "num_epochs": 3
}'
```

출력 디렉토리는 `Cloudflare/clef` 스냅샷 경로를 그대로 대체할 수 있습니다. 추론 측 `typed-decision` 컴포넌트가 이 경로를 가리키도록 하면 파인튜닝된 모델이 서빙됩니다:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: clef
    model: ./output/clef
```

## Loss

질문별 loss는 레코드 단위로 합산 후 평균됩니다:

| 질문 타입      | Loss                                                           |
|---------------|----------------------------------------------------------------|
| `choice`      | `option_ids`에 대한 cross-entropy                              |
| `noul`        | `(true, false)`에 대한 cross-entropy                           |
| `score`       | 선택된 옵션 인덱스에 대한 ordinal MSE (낮음→높음 순). 트레이너 컴포넌트의 `score_ordinal=False`로 전환하면 일반 cross-entropy |

질문 타입별 가중치(`choice_loss_weight`, `noul_loss_weight`, `score_loss_weight`)는 트레이너 컴포넌트 레벨에서 조정할 수 있습니다.
