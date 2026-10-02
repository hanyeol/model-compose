# Fine-tuning typed-decision models · Clef driver

Fine-tune the [Cloudflare Clef](https://huggingface.co/Cloudflare/clef)
`joint_schema_model` on a labelled `{state, schema, answers}` dataset.

The trainer is wired through the [mindor-clef-trainer](https://github.com/hanyeol/mindor-clef-trainer)
package: `model-compose` provisions the base checkpoint, hands the dataset to
`clef_trainer.train(...)`, and copies the Clef runtime glue (processor configs,
`joint_schema_model.py`) into the resulting checkpoint directory.

## Dataset format

Each line is a JSON object with three fields, identical to the typed-decision
inference input plus a ground-truth `answers` map keyed by question id:

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

`noul` answers are native booleans; `choice` and `score` answers are option
labels (strings). The trainer coerces each answer to its gold logit index
before computing per-question loss.

A toy 3-row dataset is included at [`train.jsonl`](./train.jsonl).

## Run

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/clef",
  "num_epochs": 3
}'
```

The output directory becomes a drop-in replacement for the `Cloudflare/clef`
snapshot path — point an inference `typed-decision` component at it to serve
the fine-tuned model:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: clef
    model: ./output/clef
```

## Loss

Per-question losses are summed and averaged over the record:

| Question type | Loss                                      |
|---------------|-------------------------------------------|
| `choice`      | cross-entropy over `option_ids`           |
| `noul`        | cross-entropy over `(true, false)`        |
| `score`       | ordinal MSE on the chosen option index (ordered low→high); set `score_ordinal=False` on the trainer component for plain cross-entropy |

Per-type weights (`choice_loss_weight`, `noul_loss_weight`, `score_loss_weight`)
are tunable at the trainer component level.
