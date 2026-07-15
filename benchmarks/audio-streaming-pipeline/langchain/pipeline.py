"""LangChain (LCEL) implementation of STT -> splitter -> embedding.

Uses LangChain's idiomatic LCEL: `RunnableLambda`s composed with `|`.
LCEL is the framework's data-pipeline shape (before LangGraph existed).

Each stage is a Runnable; the whole chain is `stt | split | embed`. We
call `.stream()` on the chain so the final embed vectors flow out
lazily, giving the framework the best chance to pipeline.

Reads the audio file path from argv (`--input <path>`). Emits only
`runtime.ready` (models loaded) and `pipeline.first_output` +
`pipeline.done` (from the tail of the pipeline).
"""
from __future__ import annotations

import argparse
import json
import time
import wave
from typing import Any, Iterator, List

import numpy as np
import torch
from faster_whisper import WhisperModel
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from langchain_core.runnables import RunnableLambda


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

def stt_stage(audio_path: str) -> str:
    pcm = read_wav_pcm(audio_path)
    segments, _ = WHISPER.transcribe(pcm, language="en", beam_size=1)
    parts: List[str] = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def split_stage(transcript: str) -> List[str]:
    return SPLITTER.split_text(transcript)


def embed_stage(chunks: List[str]) -> Iterator[np.ndarray]:
    for chunk in chunks:
        vec = EMBEDDER.encode(chunk, normalize_embeddings=True)
        yield vec


def build_chain():
    stt = RunnableLambda(stt_stage)
    split = RunnableLambda(split_stage)
    embed = RunnableLambda(embed_stage)
    return stt | split | embed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True,
                    help="path to 16 kHz mono WAV to feed the pipeline")
    args = ap.parse_args()

    preload_models()
    chain = build_chain()
    emit("runtime", "ready")
    time.sleep(1)  # let the runner snapshot Ready RSS

    first = True
    count = 0
    for _ in chain.stream(args.input):
        count += 1
        if first:
            emit("pipeline", "first_output")
            first = False
    emit("pipeline", "done", count=count)


if __name__ == "__main__":
    main()
