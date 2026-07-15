# model-compose benchmarks

Head-to-head benchmarks that compare **model-compose** against other orchestration frameworks on tasks where streaming pipelines matter.

## Why these exist

Most public agent-framework benchmarks measure blocking, single-turn requests. They don't capture what happens in a multi-stage pipeline where every stage can stream: time to first output at the tail, memory footprint at each phase of the run, and how much of the wall time the framework spends actually overlapping work vs. serializing it.

model-compose is designed stream-native. These benchmarks exist to show — with reproducible numbers — where that design pays off, and where it doesn't.

## Layout

```
benchmarks/
├── README.md                       (this file)
├── requirements.txt                shared dependency list
├── common/                         shared harness
│   ├── metrics.py                  MetricsCollector, SystemSample
│   └── runner.py                   subprocess runner + resource sampler
└── <benchmark-name>/
    ├── README.md                   scenario summary + results table
    ├── scenario.md                 event contract every implementation honors
    ├── data/                       inputs (or a fetch script)
    ├── model-compose/
    │   ├── model-compose.yml
    │   └── pipeline.py             thin driver that emits the required events
    ├── langgraph/
    │   └── pipeline.py
    ├── langchain/
    │   └── pipeline.py
    ├── llamaindex/
    │   └── pipeline.py
    └── <other>/                    additional baselines as we add them
```

Each benchmark folder is self-contained. Adding a new baseline means adding a new sibling folder.

## Metrics

Every benchmark reports the same core metrics via `common/metrics.py`. Implementations emit three events (`runtime.ready`, `pipeline.first_output`, `pipeline.done`) and the harness derives the rest.

| Metric | What it measures |
|---|---|
| **TTFO** (Time To First Output) | `pipeline.first_output − runtime.ready` — how quickly the tail of the pipeline produces its first result once models are loaded. |
| **E2E latency** | `pipeline.done − runtime.ready` — total wall time from ready to last output. |
| **Ready RSS** | Process RSS snapshotted the instant `runtime.ready` arrives; captures framework + model baseline before any pipeline work starts. |
| **Peak / Mean / p95 RSS** | Sampled every 100 ms from `runtime.ready` onward. |
| **CPU% peak / mean / p95** | Same sampling. Rolled up across the driver process and its children. |
| **Threads peak / final** | Same sampling. |

The runner also supports fault-injection flags (see each benchmark's `scenario.md`):

- `--slow-consumer-ms N` — throttle tail-of-pipeline event reads to observe backpressure behavior.
- `--cancel-at-seconds T` — SIGTERM the driver mid-run and measure cleanup latency.

Raw 100 ms samples are written to `<impl>/results/system-*.csv`; aggregated numbers land in `summary-*.json`.

## Benchmarks

| Name | Status | Focus |
|---|---|---|
| [audio-streaming-pipeline](./audio-streaming-pipeline/) | ready | 3-stage: STT → text splitter → embedding. Compares model-compose vs. LangGraph / LangChain / LlamaIndex. |

## Ground rules

- Each baseline uses that framework's idiomatic shape. LangGraph = `StateGraph` with one node per stage. LangChain = LCEL `RunnableLambda | RunnableLambda | ...`. LlamaIndex = `IngestionPipeline` with `TransformComponent`s. model-compose = YAML workflow with per-component streaming. No hand-tuning one side while leaving the other naive.
- Same models, same input data, same hardware for a given result row.
- Every driver `pipeline.py` follows the same shape: framework-specific imports up top, then the same block of preload / warmup / `read_wav_pcm` helpers, then framework-specific graph/chain construction, then a `main` that:
  1. Preloads and warms all models.
  2. Builds the graph / chain / pipeline.
  3. Emits `runtime.ready`.
  4. Sleeps 1 s (lets the runner snapshot Ready RSS before inference-time memory starts growing).
  5. Runs the pipeline and emits `pipeline.first_output` / `pipeline.done`.
- Raw run outputs land in `<benchmark>/<impl>/results/` (gitignored). Aggregated results are checked into the benchmark README.
- Every result must be reproducible with the commands in the benchmark README.
