# Scenario spec: audio-streaming-pipeline

Every implementation in this benchmark must satisfy this contract. If it doesn't, its numbers don't compare.

## Input

- A single 16 kHz mono int16 WAV file at a path given on the command line: `pipeline.py --input path/to/sample.wav`.
- 30–60 seconds long.
- The runner still opens a stdin pipe to the process for historical reasons, but implementations are free to ignore stdin and read the file directly. All current implementations do so.

## Pipeline stages

1. **STT** — read the WAV, produce a transcript. Uses `faster-whisper` `base`, greedy decoding, VAD off.
2. **Text splitting** — split the transcript into chunks. Uses `langchain_text_splitters.RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)`.
3. **Embedding** — produce one 384-dim vector per chunk. Uses `sentence-transformers/all-MiniLM-L6-v2`.

There is no storage stage. Vectors are consumed (counted) by the pipeline driver, but not persisted. The point is to measure how each orchestrator moves data through the three stages, not to time a vector store.

## Startup contract: preload models before timing starts

Model load time is not what this benchmark measures. Every implementation MUST:

1. Load all models (STT, embedder) — plus initialize the splitter — **before** any pipeline work begins.
2. Emit a single `runtime.ready` event once everything is resident and warm.
3. Only after `ready`, invoke the pipeline.

```json
{"t": 1720000000.000, "stage": "runtime", "event": "ready"}
```

The runner starts its clock (`input_start`) when it observes `runtime.ready`. All downstream timing is measured from that point, so cold-load time is excluded.

If `ready` never arrives the runner times out and the run is marked invalid.

## Required events

Two events, produced by the last stage of the pipeline (the embedding stage):

```json
{"t": 1720000000.000, "stage": "runtime", "event": "ready"}
{"t": 1720000000.789, "stage": "pipeline", "event": "first_output", "detail": {"dim": 384}}
{"t": 1720000001.234, "stage": "pipeline", "event": "done",         "detail": {"count": 42}}
```

- `pipeline.first_output` — first embedding vector emerges from the tail of the pipeline. This is what actually captures pipelining. An implementation that buffers the whole transcript before starting to embed shows up as a large gap between `ready` and `first_output`.
- `pipeline.done` — pipeline drained, no more output.

Nothing else is required. Per-stage `first_partial` / `first_token` / `first_vector` events are not tracked — they're either fragile to define fairly across frameworks (model-compose hooks fire on job start, not on real data movement) or they double-count what `pipeline.first_output` already reveals.

Implementations MAY emit additional debug events, but the harness ignores them.

## Metrics reported

- **`pipeline.first_output` (TTFO)** — time to first emitted vector, from `input_start`.
- **`pipeline.done` (E2E)** — total pipeline duration, from `input_start`.
- **`system` samples** — RSS / CPU% / thread count sampled every 100 ms via `psutil`, written to `system-*.csv`.

## Fault-injection modes

- `--slow-consumer-ms N` — the runner reads pipeline events with an `N`-ms artificial delay after `first_output`. Measures memory growth under a stuck consumer.
- `--cancel-at-seconds T` — the runner sends `SIGTERM` at `t=T` and measures time until the process exits cleanly.

## Out of scope

- Transcription accuracy. We compare orchestration behavior, not model quality.
- Vector storage. That's the next benchmark's problem.
- GPU throughput. Small models on CPU/MPS are fine; the point is pipelining.
- Networked services. All models load locally.
