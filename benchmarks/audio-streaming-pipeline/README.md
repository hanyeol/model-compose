# audio-streaming-pipeline

Three-stage pipeline where each stage can, in principle, produce partial output before the previous stage finishes. This is the shape where stream-native orchestration should win.

```
audio file ─► Whisper STT ─► RecursiveCharacterTextSplitter ─► embedding
             (segments)      (chunks)                          (vectors)
```

## Why this scenario

- Every stage naturally streams: STT emits transcript segments as it decodes, the splitter produces one chunk at a time, and the embedder can encode each chunk as it arrives.
- No LLM in the middle. Earlier drafts had one; removing it takes prompt-collation policy out of the discussion so the numbers reflect orchestration behavior only.
- Long-form audio (see `data/`) makes stage pipelining matter — a 40-minute file exaggerates the gap between "stream as you go" and "wait for the previous stage to finish."
- Fully local, fully reproducible: no network, no API cost.

## Stack

| Stage | Component | Model |
|---|---|---|
| STT | `faster-whisper` | `base`, int8 |
| Split | `langchain_text_splitters.RecursiveCharacterTextSplitter` | `chunk_size=200`, `chunk_overlap=20` |
| Embed | `sentence-transformers` | `all-MiniLM-L6-v2` |

Small, local, CPU/MPS-friendly. The point is to measure orchestration, not GPU throughput.

## Scenario

See [scenario.md](./scenario.md) for the events every implementation must emit and how metrics are computed.

## Implementations

- [model-compose/](./model-compose/) — YAML workflow with per-stage components and streaming outputs.
- [langgraph/](./langgraph/) — LangGraph, idiomatic `StateGraph`, one node per stage. Nodes run sequentially by construction.
- [langchain/](./langchain/) — LangChain LCEL chain: `RunnableLambda` per stage composed with `|`, consumed via `chain.stream(...)`.
- [llamaindex/](./llamaindex/) — LlamaIndex `IngestionPipeline` with `TransformComponent` per stage. See "About the LlamaIndex implementation" below.

### About the LlamaIndex implementation

LlamaIndex has been explicit that real-time streaming ingestion is out of scope: `IngestionPipeline` takes a list of documents, runs to completion, and returns a list of nodes. There are no per-stage hooks and no natural `first_output` observation point — the pipeline is a blocking batch.

The implementation here is the idiomatic `IngestionPipeline` shape (what LlamaIndex users would actually write). It emits `pipeline.first_output` and `pipeline.done` at the same instant, because that's what the framework returns. This is not a bug — it accurately reflects the framework's shape on a scenario that is outside its stated scope. LlamaIndex is included in the benchmark for reference, not as an unfair target.

If we care about a fair LlamaIndex comparison, a separate RAG-indexing benchmark (bulk documents → vector store, retrieval quality) is the right place. That's what LlamaIndex is designed for.

## Running

Install deps into the shared benchmark venv (only once):

```bash
python -m venv benchmarks/.venv
benchmarks/.venv/bin/pip install -r benchmarks/requirements.txt
benchmarks/.venv/bin/pip install -e .   # model-compose in dev mode
```

Prepare the audio (drop `test.mp3` into `data/`, then):

```bash
benchmarks/.venv/bin/python benchmarks/audio-streaming-pipeline/data/fetch.py
```

Run one implementation through the harness:

```bash
benchmarks/.venv/bin/python -m benchmarks.common.runner \
  --impl benchmarks/audio-streaming-pipeline/langgraph \
  --input benchmarks/audio-streaming-pipeline/data/sample.wav
```

Metrics land in `<impl>/results/summary-*.json` and per-100 ms samples in `<impl>/results/system-*.csv`.

## Results

Latest run on a 40:57 audio file (Apple Silicon, benchmarks/.venv). Raw runs are under `<impl>/results/` (gitignored).

| Implementation | TTFO (s) | E2E (s) | Ready RSS (MB) | Peak RSS (MB) | Mean RSS (MB) | Mean CPU% |
|---|---:|---:|---:|---:|---:|---:|
| **model-compose** | **67.3** | **174.3** | 553 | 2378 | 876 | 361 |
| LangGraph | 427.9 | 429.9 | 714 | 2893 | 1041 | 492 |
| LangChain | 503.6 | 505.5 | 1026 | 2786 | 1021 | 459 |
| LlamaIndex | 613.6 | 613.6 | 558 | 2686 | 854 | 444 |

`model-compose` uses `architecture: sbert` for the text-embedding component (opts into the `sentence-transformers` loader instead of raw `AutoModel`); the other three drivers use `SentenceTransformer` directly in their pipeline files. Keeps the loader consistent across all four implementations.

Observations:

- **model-compose is 2.5×–3.5× faster on E2E**. TTFO is 6×–9× faster because the pipeline actually pipelines across stages instead of running them one after the other.
- **LangGraph, LangChain, LlamaIndex all show TTFO ≈ E2E**: each stage waits for the previous to finish before starting. The first vector emerges only after the whole pipeline settles.
- **LlamaIndex's TTFO = E2E exactly** because `IngestionPipeline.run` is a single blocking call — no per-stage hooks, no partial output. This is by design (see above).
- **Ready RSS is comparable across all four** (550–1030 MB). Same model set, so the spread reflects framework baseline plus per-component setup. All four preload their models before `runtime.ready` and pause briefly so the sample lands before inference-time memory starts growing.
- **Peak RSS is comparable across all four** (2.4–2.9 GB) — inference-time working memory dominates and framework overhead disappears into the noise.
- **Mean CPU% is comparable (361–492%)**. Wall-clock savings come from stages overlapping, not from any single stage being cheaper. model-compose sits at the low end because its wall time is shortest — the CPU is idle waiting on the next chunk more often.
