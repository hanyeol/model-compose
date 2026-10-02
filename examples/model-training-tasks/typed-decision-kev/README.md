# Fine-tuning typed-decision models · Kev driver

Jointly train [Kev](https://github.com/jaredpalmer/kev)'s LoRA adapter and
pointer head on a labelled `{state, schema, answers}` dataset.

Kev's upstream training is a 1000+ line CLI script tied to its suite /
manifest layout. This example drives the core training loop (bf16 LoRA on the
language backbone + the pointer head, `kev.train.question_loss` per question)
through the [mindor-kev-trainer](https://github.com/hanyeol/mindor-kev-trainer)
package, which reimplements the loop as a plain `train(dataset, config)`
function and reuses `kev.model.DecisionModel`, `kev.model.encode`, and
`kev.train.question_loss` from the installed `kev` package.

## Scope

In scope: single-process LoRA + pointer-head training, bf16/fp16 autocast,
linear warmup → linear decay LR schedule, per-epoch checkpointing.

Out of scope: FSDP2 full fine-tune, Kev's micro-batch planner, permutation KL
regularizer, and anchor-KL teacher distributions. Use `python -m kev.train`
directly for those features.

## Dataset format

Each line is a JSON object:

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

Rows that overflow the configured `max_state_length` / `max_branch_length`
budgets are skipped (same policy upstream applies when encoding builds a
record on the fly).

A toy 3-row dataset is included at [`train.jsonl`](./train.jsonl).

## Run

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/kev",
  "num_epochs": 3
}'
```

The output directory contains the LoRA adapter plus `pointer_head.pt` — load
with Kev's standard loader:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: kev
    model: ./output/kev
```

## Loss

Per-question loss comes straight from `kev.train.question_loss`:

- `choice`: cross-entropy over options (soft target supported via
  `question["target"]`).
- `noul`: cross-entropy over `(false, true)`.
- `score`: cross-entropy plus an ordinal ranked-probability-score term
  (controlled by `ord_weight` on the trainer; defaults to 0.5).
