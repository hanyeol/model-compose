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
├── common/
│   └── metrics.py                  MetricsCollector, SystemSample (shared across benchmarks)
└── <benchmark-name>/
    ├── README.md                   scenario summary + results table
    ├── scenario.md                 event contract every implementation honors
    ├── common/
    │   └── benchmark.py            benchmark-specific harness: runs impls, measures, aggregates
    ├── data/                       inputs (or a fetch script)
    ├── model-compose/
    │   ├── model-compose.yml
    │   └── pipeline.py             thin driver that emits the required events
    ├── langgraph/
    │   └── pipeline.py
    ├── langchain/
    │   └── pipeline.py
    └── <other>/                    additional baselines as we add them
```

Each benchmark folder is self-contained. The runner is per-benchmark because input shape differs (audio chunks vs. text prompts vs. …); only the metrics computation is shared.

## Metrics

Every benchmark reports the same core metrics via [common/metrics.py](./common/metrics.py). Implementations emit three events (`runtime.ready`, `pipeline.first_output`, `pipeline.done`) and the harness derives the rest.

| Metric | What it measures |
|---|---|
| **TTFO** (Time To First Output) | `pipeline.first_output − runtime.ready` — how quickly the tail of the pipeline produces its first result once models are loaded. |
| **E2E latency** | `pipeline.done − runtime.ready` — total wall time from ready to last output. |
| **Ready RSS** | Process RSS snapshotted the instant `runtime.ready` arrives; captures framework + model baseline before any pipeline work starts. |
| **Peak / Mean / p95 RSS** | Sampled every 100 ms from `runtime.ready` onward. |
| **CPU% peak / mean / p95** | Same sampling. Rolled up across the driver process and its children. |
| **Threads peak / final** | Same sampling. |

Fault-injection flags are runner-specific — see each benchmark's `scenario.md` for what its runner supports. Common ones:

- `--slow-consumer-ms N` — throttle tail-of-pipeline event reads to observe backpressure behavior.
- `--cancel-at-seconds T` — SIGTERM the driver mid-run and measure cleanup latency.

Raw 100 ms samples are written to `<impl>/results/system-*.csv`; aggregated numbers land in `summary-*.json`.

## Benchmarks

| Name | Status | Focus |
|---|---|---|
| [stt-embed-streaming](./stt-embed-streaming/) | ready | 3-stage: STT → text splitter → embedding. Compares model-compose vs. LangGraph / LangChain / LlamaIndex. |
| [llm-tts-streaming](./llm-tts-streaming/) | ready | 3-stage: LLM (Qwen2.5-0.5B) → sentence splitter → Kokoro TTS. Compares model-compose vs. LangGraph / LangChain. |

## Ground rules

- Each baseline uses that framework's idiomatic shape. LangGraph = `StateGraph` with one node per stage. LangChain = LCEL `RunnableLambda | RunnableLambda | ...`. LlamaIndex = `IngestionPipeline` with `TransformComponent`s. model-compose = YAML workflow with per-component streaming. No hand-tuning one side while leaving the other naive.
- Same models, same input data, same hardware for a given result row.
- Every driver `pipeline.py` follows the same shape: framework-specific imports up top, then shared preload / warmup helpers, then framework-specific graph/chain construction, then a `main` that:
  1. Preloads and warms all models.
  2. Builds the graph / chain / pipeline.
  3. Emits `runtime.ready`.
  4. Sleeps 1 s (lets the runner snapshot Ready RSS before inference-time memory starts growing).
  5. Runs the pipeline and emits `pipeline.first_output` / `pipeline.done`.
- Raw run outputs land in `<benchmark>/<impl>/results/` (gitignored). Aggregated results are checked into the benchmark README.
- Every result must be reproducible with the commands in the benchmark README.
