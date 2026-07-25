# Scenario: llm-tts-streaming

Every implementation in this benchmark must satisfy this contract. If it doesn't, its numbers don't compare.

## Input

- A single text prompt at a path given on the command line: `pipeline.py --input path/to/prompt.txt`.
- The runner also exports the prompt text via `BENCH_PROMPT` env var for convenience; implementations may read either.
- One fixed prompt is checked in at [`data/prompt.txt`](./data/prompt.txt). Running with a different prompt is allowed but the results row must state which prompt was used.

## Pipeline stages

1. **LLM** — take the prompt, produce assistant text via **Qwen2.5-0.5B-Instruct** on transformers, with token-level streaming. Greedy decoding (`do_sample=False`), `max_new_tokens=512`. Same generation config across all implementations, so the same model produces byte-identical output text; the normalization metric (audio seconds) further neutralizes any residual output-length differences.
2. **Sentence splitter** — group streamed tokens into complete sentences. Emits one sentence at a time so downstream TTS can begin as soon as the first sentence is available.
3. **TTS** — **Kokoro** (`kokoro` package, voice `af_heart`, 24 kHz mono), synthesizes one audio segment per sentence.

There is no playback stage. Audio bytes are consumed (counted) by the pipeline driver, but not written to disk or played. The point is to measure how each orchestrator moves data through the three stages, not to time an audio sink.

## Device policy

To keep the comparison fair across implementations on Apple Silicon:

- **LLM**: `mps` (Qwen2.5-0.5B fits comfortably)
- **TTS (Kokoro)**: `cpu` (Kokoro's MPS support is partial; CPU is the stable common denominator)

All implementations must use the same device split. Deviating from this invalidates the row.

## Startup contract: preload models before timing starts

Model load time is not what this benchmark measures. Every implementation MUST:

1. Load the LLM and TTS model — plus initialize the splitter — **before** any pipeline work begins.
2. Warm each model with a dummy forward pass so the first real call doesn't include lazy-compile time.
3. Emit a single `runtime.ready` event once everything is resident and warm.
4. Only after `ready`, invoke the pipeline.

```json
{"t": 1720000000.000, "stage": "runtime", "event": "ready"}
```

The runner starts its clock (`input_start`) when it observes `runtime.ready`. All downstream timing is measured from that point, so cold-load time is excluded.

If `ready` never arrives the runner times out and the run is marked invalid.

## Required events

Three events, produced from the tail of the pipeline (the TTS stage):

```json
{"t": 1720000000.000, "stage": "runtime",  "event": "ready"}
{"t": 1720000000.789, "stage": "pipeline", "event": "first_output", "detail": {"sample_rate": 24000}}
{"t": 1720000012.345, "stage": "pipeline", "event": "done",         "detail": {"count": 7, "audio_seconds": 42.5}}
```

- `pipeline.first_output` — first audio chunk emerges from the tail of the pipeline. This is what captures pipelining. An implementation that waits for the full LLM output before starting TTS shows up as a large gap between `ready` and `first_output`.
- `pipeline.done` — pipeline drained, no more output. `detail` MUST include:
  - `audio_seconds` (float) — total playback seconds of generated audio (`sum(len(samples) / sample_rate)` across all TTS calls, or equivalently `total_pcm_bytes / (sample_rate * channels * bytes_per_sample)`)
  - `count` (int, optional) — number of audio segments produced

Audio seconds is the normalization anchor: it's what the pipeline was "meant to produce," it's independent of tokenizer / LLM output-length variance, and it aligns with the standard TTS-benchmark real-time factor (RTF).

Nothing else is required. Per-stage `first_token` / `first_sentence` events are not tracked — they double-count what `pipeline.first_output` already reveals.

Implementations MAY emit additional debug events, but the harness ignores them.

## Metrics reported

- **`pipeline.first_output` (TTFO)** — time to first audio chunk, from `input_start`. Reported raw (not normalized) — TTFO is a single-shot latency, not a long-running scale.
- **`pipeline.done` (E2E)** — total pipeline duration, from `input_start`. Reported raw.
- **`rtf`** — `E2E / audio_seconds`. Real-time factor; the primary throughput comparator across implementations. `rtf < 1` means the pipeline synthesizes faster than real-time playback. Because RTF divides by generated audio length rather than by LLM output length, it stays meaningful even if two runs produce different amounts of text.
- **`system` samples** — RSS / CPU% / thread count sampled every 100 ms via `psutil`, written to `system-*.csv`.

Note: with a fixed prompt + greedy decoding + fixed `max_new_tokens`, all implementations produce the same text and therefore the same `audio_seconds`. RTF differences reflect orchestration overhead only, not different workloads.

## Fault-injection modes

- `--slow-consumer-ms N` — the runner reads pipeline events with an `N`-ms artificial delay after `first_output`. Measures memory growth under a stuck consumer.
- `--cancel-at-seconds T` — the runner sends `SIGTERM` at `t=T` and measures time until the process exits cleanly.

## Out of scope

- LLM output quality. We compare orchestration behavior, not model choice.
- TTS voice quality or naturalness. Fixed voice, fixed model.
- Speaker adaptation, voice cloning, streaming synthesis within a sentence.
- GPU throughput. Small models on CPU/MPS are fine; the point is pipelining.
- Networked services. All models load locally.
