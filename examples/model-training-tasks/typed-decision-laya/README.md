# Fine-tuning typed-decision models · Laya driver

Fine-tune a [Laya](https://github.com/NandhaKishorM/laya) encoder + per-question
heads on a labelled `{state, schema, answers}` dataset.

Laya's upstream training ships only as a notebook / reference script; this
example drives the recipe (RLCD + strictly-proper-scoring-rule reward +
GRPO-style policy gradient mixed with soft-target cross-entropy; LBFGS
temperature calibration) via the [mindor-laya-trainer](https://github.com/hanyeol/mindor-laya-trainer)
package.

## Dataset format

Each line is a JSON object with three fields — the typed-decision inference
input plus a ground-truth `answers` map:

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

Answer values may also be a full probability dict (e.g. `{"true": 0.9,
"false": 0.1}`) — soft targets propagate through the CE term the same way the
upstream notebook consumes them.

A toy 3-row dataset is included at [`train.jsonl`](./train.jsonl).

## Run

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/laya",
  "num_epochs": 4
}'
```

The output directory is a drop-in replacement for a `convaiinnovations/laya`
snapshot — point an inference `typed-decision` component at it:

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

Set `freeze_encoder: true` on the trainer component to train only the
per-question heads. The encoder's optimizer learning rate is zeroed (not
`requires_grad`) so gradient checkpointing keeps working.

## Preset

The `preset` field is optional and selects which Laya bundle subfolder to
warm-start from (`english`, `multilingual`, or `typed-decisions`). The
`typed-decisions` checkpoint is already fine-tuned for the typed-decision
task family, so it converges fastest on compatible data.

Leave `preset` unset when `model` points at a standalone checkpoint — the
driver then warm-starts from the checkpoint root. Omitting both `model` and
`preset` falls back to the bundle repo + `preset: multilingual`.
