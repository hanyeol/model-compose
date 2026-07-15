"""LangGraph, idiomatic version.

3-stage pipeline: STT -> text splitter -> embedding. Uses LangGraph's
idiomatic `StateGraph`: each stage is a node, edges express order, and
nodes run sequentially.

Reads the audio file path from argv (`--input <path>`). Emits only
`runtime.ready` (models loaded) and `pipeline.first_output` +
`pipeline.done` (from the tail of the pipeline).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
import wave
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
from faster_whisper import WhisperModel
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from langgraph.graph import StateGraph, START, END


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

    SPLITTER = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    SPLITTER.split_text("warmup")

    EMBEDDER = SentenceTransformer(EMBED_MODEL, device=TORCH_DEVICE)
    EMBEDDER.encode("hello", normalize_embeddings=True)


def read_wav_pcm(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


# ---------------- framework-specific code below ---------------------------

@dataclass
class PipelineState:
    audio_path: str = ""
    transcript: str = ""
    chunks: list[str] = field(default_factory=list)
    vectors: list[np.ndarray] = field(default_factory=list)


async def stt_stage(state: PipelineState) -> PipelineState:
    pcm = read_wav_pcm(state.audio_path)
    segments, _ = WHISPER.transcribe(pcm, language="en", beam_size=1)
    parts = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            parts.append(text)
    state.transcript = " ".join(parts)
    return state


async def split_stage(state: PipelineState) -> PipelineState:
    state.chunks = SPLITTER.split_text(state.transcript)
    return state


async def embed_stage(state: PipelineState) -> PipelineState:
    first = False
    for chunk in state.chunks:
        vec = EMBEDDER.encode(chunk, normalize_embeddings=True)
        state.vectors.append(vec)
        if not first:
            emit("pipeline", "first_output", dim=int(vec.shape[0]))
            first = True
        await asyncio.sleep(0)
    emit("pipeline", "done", count=len(state.vectors))
    return state


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("stt", stt_stage)
    g.add_node("split", split_stage)
    g.add_node("embed", embed_stage)
    g.add_edge(START, "stt")
    g.add_edge("stt", "split")
    g.add_edge("split", "embed")
    g.add_edge("embed", END)
    return g.compile()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True,
                    help="path to 16 kHz mono WAV to feed the pipeline")
    args = ap.parse_args()

    preload_models()
    graph = build_graph()
    emit("runtime", "ready")
    await asyncio.sleep(1)  # let the runner snapshot Ready RSS

    await graph.ainvoke(PipelineState(audio_path=args.input))


if __name__ == "__main__":
    asyncio.run(main())
