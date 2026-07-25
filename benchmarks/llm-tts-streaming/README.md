# llm-tts-streaming

Three-stage pipeline where each stage can, in principle, produce partial output before the previous stage finishes. This is the shape where stream-native orchestration should win.

```
prompt ─► Qwen2.5-0.5B-Instruct ─► sentence-splitter ─► Kokoro TTS
          (tokens)                  (sentences)          (audio chunks)
```

## Why this scenario

- Every stage naturally streams: the LLM emits tokens as it decodes, the splitter groups tokens into sentences and emits one at a time, Kokoro synthesizes one audio segment per sentence.
- A stream-native orchestrator should overlap them — TTS on sentence #1 while the LLM is still decoding sentence #2 — and drive the time-to-first-audio down to *(first sentence tokens + Kokoro on that sentence)* rather than *(all 512 tokens + Kokoro on everything)*.
- Fixed prompt + greedy + fixed `max_new_tokens` means all implementations produce the same text and same TTS workload. Any difference in TTFO / E2E is orchestration overhead only.
- Fully local, fully reproducible: no network, no API cost.

## Stack

| Stage | Component | Model / config |
|---|---|---|
| LLM | `transformers` (HuggingFace) | `Qwen/Qwen2.5-0.5B-Instruct`, greedy, `max_new_tokens=512`, `mps` |
| Split | sentence-tokenizer | one sentence at a time, streaming |
| TTS | `kokoro` | voice `af_heart`, 24 kHz mono, `cpu` |

The device split (`LLM=mps, TTS=cpu`) is enforced across all implementations — see [scenario.md](./scenario.md).

## Scenario

See [scenario.md](./scenario.md) for the events every implementation must emit and how metrics are computed.

## Implementations

- [model-compose/](./model-compose/) — YAML workflow. LLM (`text-generation` with `streaming: true`) feeds the `sentence-splitter` component, which feeds a Kokoro `text-to-speech` component. Every arrow is a stream.
- [langgraph/](./langgraph/) — LangGraph `StateGraph`, one node per stage. Nodes run sequentially by construction.
- [langchain/](./langchain/) — LangChain LCEL chain: `RunnableLambda` per stage composed with `|`, consumed via `chain.stream(...)`.

LlamaIndex is not included here. `IngestionPipeline` is the framework's canonical shape and it takes documents (not a live token stream) and returns nodes; wrapping an LLM→TTS pipeline in it would be a strawman, not a fair comparison. LlamaIndex remains included in [../stt-embed-streaming/](../stt-embed-streaming/) where the comparison at least reflects an ingestion-shaped workload.

## Running

Install deps into the shared benchmark venv (only once):

```bash
python -m venv benchmarks/.venv
benchmarks/.venv/bin/pip install -r benchmarks/requirements.txt
benchmarks/.venv/bin/pip install -e .   # model-compose in dev mode
```

Kokoro needs `espeak-ng` at the system level:

```bash
brew install espeak-ng     # macOS
# apt-get install espeak-ng   # Debian/Ubuntu
```

Run one implementation through the harness:

```bash
benchmarks/.venv/bin/python benchmarks/llm-tts-streaming/common/benchmark.py \
  --impl benchmarks/llm-tts-streaming/langgraph \
  --input benchmarks/llm-tts-streaming/data/prompt.txt
```

Metrics land in `<impl>/results/summary-*.json` and per-100 ms samples in `<impl>/results/system-*.csv`.

## Results

Not yet populated. Populate this table after running the three implementations with the checked-in prompt and Qwen2.5-0.5B-Instruct.

| Implementation | TTFO (s) | E2E (s) | E2E ms/char | RTF | Ready RSS (MB) | Peak RSS (MB) | Mean CPU% |
|---|---:|---:|---:|---:|---:|---:|---:|
| model-compose | | | | | | | |
| LangGraph | | | | | | | |
| LangChain | | | | | | | |

### Expected shape

Because the LLM alone takes seconds to produce 512 tokens greedily, and Kokoro takes ~200–400 ms per short sentence, the gap between "stream stages" and "serialize stages" is large:

- **model-compose**: TTFO ≈ *(time-to-first-sentence from LLM) + (Kokoro on that sentence)* — a small fraction of E2E.
- **LangGraph / LangChain**: TTFO ≈ E2E, because the LLM node fully drains before the TTS node starts. Both events fire near each other at the end of the run.
