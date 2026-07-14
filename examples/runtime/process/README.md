# Process Runtime

Runs the model worker in a **separate OS process** (via `multiprocessing`).
IPC travels over `multiprocessing.Queue` — no sockets, no filesystem.

```yaml
component:
  runtime:
    type: process
    start_timeout: 120s
    env:
      TOKENIZERS_PARALLELISM: "false"
```

## Try it

```bash
model-compose up
model-compose run --input '{"text": "I love this project"}'
```

First run downloads the model (a few hundred MB). Subsequent runs are fast.

## What you get

- Model load and inference happen in the child process, not the controller.
- A native-lib crash (segfault, OOM) kills the worker but not the controller.
- `env:` values apply *only* to the child, so you can tune per-model knobs like
  `TOKENIZERS_PARALLELISM`, `CUDA_VISIBLE_DEVICES`, etc. without polluting the
  controller environment.

## Comparison

| Feature                    | `embedded` | `process` |
|----------------------------|:---------:|:---------:|
| Crash isolation            |     ❌    |     ✅    |
| Independent env vars       |     ❌    |     ✅    |
| Dependency isolation       |     ❌    |     ❌    |
| Startup cost               |     0     |  ~seconds |

For dependency isolation, see [`../virtualenv-python`](../virtualenv-python).
