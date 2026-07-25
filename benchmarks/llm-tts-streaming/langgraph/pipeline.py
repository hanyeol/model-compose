"""LangGraph, idiomatic version.

3-stage pipeline: LLM -> sentence splitter -> TTS. Uses LangGraph's
idiomatic `StateGraph`: each stage is a node, edges express order, and
nodes run sequentially. The LLM node produces the full assistant text
before the splitter node begins; the splitter emits sentences before
the TTS node begins — this is exactly the shape the benchmark measures.

Reads the prompt file path from argv (`--input <path>`). Emits only
`runtime.ready` (models loaded) and `pipeline.first_output` +
`pipeline.done` (from the tail of the pipeline).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import numpy as np
import torch
from langchain_text_splitters import NLTKTextSplitter
from transformers import AutoModelForCausalLM, AutoTokenizer

from langgraph.graph import StateGraph, START, END


LLM_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
MAX_NEW_TOKENS = 512
KOKORO_VOICE = "af_heart"
KOKORO_SAMPLE_RATE = 24000


def llm_device() -> str:
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


LLM_DEVICE = llm_device()
TTS_DEVICE = "cpu"  # Kokoro MPS support is partial; CPU is the common baseline.

# Kokoro internally uses espeak-ng; on macOS+MPS, force any tensor ops that
# hit unsupported kernels to fall back to CPU to avoid hard crashes.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def emit(stage: str, event: str, **detail) -> None:
    payload = {"t": time.time(), "stage": stage, "event": event}
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload), flush=True)


LLM: Any = None
TOKENIZER: Any = None
SPLITTER: Any = None
TTS: Any = None


def preload_models() -> None:
    global LLM, TOKENIZER, SPLITTER, TTS

    TOKENIZER = AutoTokenizer.from_pretrained(LLM_MODEL)
    LLM = AutoModelForCausalLM.from_pretrained(LLM_MODEL, torch_dtype=torch.float32).to(LLM_DEVICE)
    LLM.eval()
    # Warmup: one greedy step so the first real generate() doesn't include compile cost.
    warm_ids = TOKENIZER("warmup", return_tensors="pt").input_ids.to(LLM_DEVICE)
    with torch.no_grad():
        LLM.generate(warm_ids, max_new_tokens=1, do_sample=False)

    # NLTK Punkt is required by NLTKTextSplitter. Download on demand;
    # subsequent runs use the cached data under ~/nltk_data.
    import nltk
    for pkg in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{pkg}")
        except LookupError:
            nltk.download(pkg, quiet=True)
    SPLITTER = NLTKTextSplitter(chunk_size=1, chunk_overlap=0)
    SPLITTER.split_text("warmup sentence.")

    from kokoro import KPipeline
    TTS = KPipeline(lang_code="a", device=TTS_DEVICE)
    for _ in TTS("warmup.", voice=KOKORO_VOICE):
        pass


def build_prompt(user_text: str) -> str:
    """Wrap the user prompt in the model's chat template."""
    messages = [{"role": "user", "content": user_text}]
    return TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def audio_seconds_of(samples: Any) -> float:
    """Given a Kokoro yield (torch tensor or ndarray), return playback seconds."""
    if hasattr(samples, "shape"):
        n = int(samples.shape[-1])
    else:
        n = len(samples)
    return n / KOKORO_SAMPLE_RATE


# ---------------- framework-specific code below ---------------------------

@dataclass
class PipelineState:
    prompt: str = ""
    generated_text: str = ""
    sentences: List[str] = field(default_factory=list)
    audio_seconds: float = 0.0
    segment_count: int = 0


async def llm_stage(state: PipelineState) -> PipelineState:
    prompt = build_prompt(state.prompt)
    input_ids = TOKENIZER(prompt, return_tensors="pt").input_ids.to(LLM_DEVICE)
    with torch.no_grad():
        output_ids = LLM.generate(
            input_ids,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )
    new_tokens = output_ids[0, input_ids.shape[-1]:]
    state.generated_text = TOKENIZER.decode(new_tokens, skip_special_tokens=True).strip()
    return state


async def split_stage(state: PipelineState) -> PipelineState:
    # chunk_size=1 with NLTKTextSplitter yields one sentence per chunk;
    # nltk boundaries drive it, `chunk_size` just prevents re-merging.
    state.sentences = [s for s in SPLITTER.split_text(state.generated_text) if s.strip()]
    return state


async def tts_stage(state: PipelineState) -> PipelineState:
    first = True
    for sentence in state.sentences:
        for _, _, audio in TTS(sentence, voice=KOKORO_VOICE):
            state.audio_seconds += audio_seconds_of(audio)
            state.segment_count += 1
            if first:
                emit("pipeline", "first_output", sample_rate=KOKORO_SAMPLE_RATE)
                first = False
        await asyncio.sleep(0)
    emit("pipeline", "done",
         count=state.segment_count,
         audio_seconds=round(state.audio_seconds, 3))
    return state


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("llm", llm_stage)
    g.add_node("split", split_stage)
    g.add_node("tts", tts_stage)
    g.add_edge(START, "llm")
    g.add_edge("llm", "split")
    g.add_edge("split", "tts")
    g.add_edge("tts", END)
    return g.compile()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path,
                    help="path to a text file containing the LLM prompt")
    args = ap.parse_args()

    prompt = args.input.read_text(encoding="utf-8").strip()

    preload_models()
    graph = build_graph()
    emit("runtime", "ready")
    await asyncio.sleep(1)  # let the runner snapshot Ready RSS

    await graph.ainvoke(PipelineState(prompt=prompt))


if __name__ == "__main__":
    asyncio.run(main())
