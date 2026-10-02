# Fine-tuning typed-decision models · Nimble driver

LoRA fine-tune Qwen3.5-9B through [Bespoke Nimble](https://github.com/bespokelabsai/nimble)'s
candidate-token cross-entropy on a labelled `{state, schema, answers}` dataset.

The trainer is wired through the [mindor-nimble-trainer](https://github.com/hanyeol/mindor-nimble-trainer)
package, which reuses `nimble.training.schema_train`'s primitives
(`CandidateCollator`, `CandidateTrainer`, `prepare_prompts`, `choice_key`,
`load_base`) with a model-compose-friendly dataset shape layered on top.

## Dataset format

Each line is a JSON object:

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

Each row is expanded into one training example per answered schema field —
Nimble treats every field as an independent candidate-classification example.
The trainer re-normalizes fields into the shape upstream `prepare_prompts()`
expects (`choice` with explicit choices, `score` with numeric string levels,
`noul` without options).

A toy 3-row dataset is included at [`train.jsonl`](./train.jsonl).

## Run

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/nimble",
  "num_epochs": 3
}'
```

The output directory is a HuggingFace-style LoRA adapter directory plus
`schema_config.json` — identical to what upstream `nimble.training.schema_train`
writes. Load it in a `typed-decision` inference component:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: nimble
    model: ./output/nimble
    base_model: Qwen/Qwen3.5-9B
```

## Platform

Nimble's CUDA scorer requires `torch>=2.8` and a bf16-capable GPU; the trainer
inherits the same pins. On Apple Silicon the trainer runs under
MLX / `mlx-lm`; on Linux x86_64 or aarch64 it runs on CUDA. Other platforms
(Darwin x86_64, Windows) are not supported by Nimble upstream and will fail at
setup time.
