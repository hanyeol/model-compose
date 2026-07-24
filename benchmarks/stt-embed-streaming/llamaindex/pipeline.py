"""LlamaIndex (IngestionPipeline) implementation of STT -> splitter -> embed.

LlamaIndex's ingestion primitive is `IngestionPipeline`, which chains
`TransformComponent`s. It's the framework's canonical way to turn raw
sources into indexable nodes with embeddings attached.

Note on scope:
  LlamaIndex has been explicit that real-time streaming ingestion is
  out of scope: pipelines take a list of documents, run to completion,
  and return a list of nodes. There are no per-stage hooks and no
  natural `first_output` observation point — the pipeline is a blocking
  batch. Emitting `pipeline.first_output` and `pipeline.done` at the
  same moment accurately reflects the framework's shape.

Reads the audio file path from argv (`--input <path>`).
"""
from __future__ import annotations

import argparse
import json
import time
import wave
from typing import Any, List

import numpy as np
import torch
from faster_whisper import WhisperModel

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode, Document, TextNode, TransformComponent
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


WHISPER_MODEL = "base"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 200
CHUNK_OVERLAP = 20


def torch_device() -> str:
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


TORCH_DEVICE = torch_device()


def emit(stage: str, event: str, **detail) -> None:
    payload = {"t": time.time(), "stage": stage, "event": event}
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload), flush=True)


WHISPER: Any = None
SPLITTER: Any = None
EMBEDDER: Any = None


def preload_models() -> None:
    global WHISPER, SPLITTER, EMBEDDER

    WHISPER = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    silence = np.zeros(16000, dtype=np.float32)
    list(WHISPER.transcribe(silence, language="en", beam_size=1)[0])

    SPLITTER = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    EMBEDDER = HuggingFaceEmbedding(model_name=EMBED_MODEL, device=TORCH_DEVICE)
    EMBEDDER.get_text_embedding("hello")


def read_wav_pcm(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


# ---------------- framework-specific code below ---------------------------

class SttStage(TransformComponent):
    """Turn a seed Document with `audio_path` metadata into a transcript TextNode."""

    def __call__(self, nodes: List[BaseNode], **kwargs) -> List[BaseNode]:
        results: List[BaseNode] = []
        for node in nodes:
            audio_path = node.metadata.get("audio_path") or node.get_content()
            pcm = read_wav_pcm(audio_path)
            segments, _ = WHISPER.transcribe(pcm, language="en", beam_size=1)
            transcript = " ".join(
                seg.text.strip() for seg in segments if seg.text.strip()
            )
            results.append(TextNode(text=transcript))
        return results


def build_pipeline() -> IngestionPipeline:
    return IngestionPipeline(
        transformations=[SttStage(), SPLITTER, EMBEDDER],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True,
                    help="path to 16 kHz mono WAV to feed the pipeline")
    args = ap.parse_args()

    preload_models()
    pipeline = build_pipeline()
    emit("runtime", "ready")
    time.sleep(1)  # let the runner snapshot Ready RSS

    seed = Document(text="", metadata={"audio_path": args.input})
    nodes = pipeline.run(documents=[seed])
    vectors = [n for n in nodes if getattr(n, "embedding", None) is not None]
    emit("pipeline", "first_output")
    emit("pipeline", "done", count=len(vectors))


if __name__ == "__main__":
    main()
