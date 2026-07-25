"""LangChain (LCEL) implementation of LLM -> sentence splitter -> TTS.

Uses LangChain's idiomatic LCEL: `RunnableLambda`s composed with `|`.
LCEL is the framework's data-pipeline shape (before LangGraph existed).

Each stage is a Runnable; the whole chain is `llm | split | tts`. We
call `.stream()` on the chain so audio segments flow out lazily, giving
the framework the best chance to pipeline. In practice the sentence
splitter is a batch operation (LangChain's text splitters don't stream),
so the chain still waits for the full LLM output before splitting.

Reads the prompt file path from argv (`--input <path>`). Emits only
`runtime.ready` (models loaded) and `pipeline.first_output` +
`pipeline.done` (from the tail of the pipeline).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator, List

import torch
from langchain_text_splitters import NLTKTextSplitter
from transformers import AutoModelForCausalLM, AutoTokenizer

from langchain_core.runnables import RunnableLambda


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
    warm_ids = TOKENIZER("warmup", return_tensors="pt").input_ids.to(LLM_DEVICE)
    with torch.no_grad():
        LLM.generate(warm_ids, max_new_tokens=1, do_sample=False)

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
    messages = [{"role": "user", "content": user_text}]
    return TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def audio_seconds_of(samples: Any) -> float:
    if hasattr(samples, "shape"):
        n = int(samples.shape[-1])
    else:
        n = len(samples)
    return n / KOKORO_SAMPLE_RATE


# ---------------- framework-specific code below ---------------------------

def llm_stage(prompt: str) -> str:
    templated = build_prompt(prompt)
    input_ids = TOKENIZER(templated, return_tensors="pt").input_ids.to(LLM_DEVICE)
    with torch.no_grad():
        output_ids = LLM.generate(
            input_ids,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )
    new_tokens = output_ids[0, input_ids.shape[-1]:]
    return TOKENIZER.decode(new_tokens, skip_special_tokens=True).strip()


def split_stage(text: str) -> List[str]:
    return [s for s in SPLITTER.split_text(text) if s.strip()]


def tts_stage(sentences: List[str]) -> Iterator[dict]:
    for sentence in sentences:
        for _, _, audio in TTS(sentence, voice=KOKORO_VOICE):
            yield {"seconds": audio_seconds_of(audio)}


def build_chain():
    llm = RunnableLambda(llm_stage)
    split = RunnableLambda(split_stage)
    tts = RunnableLambda(tts_stage)
    return llm | split | tts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path,
                    help="path to a text file containing the LLM prompt")
    args = ap.parse_args()

    prompt = args.input.read_text(encoding="utf-8").strip()

    preload_models()
    chain = build_chain()
    emit("runtime", "ready")
    time.sleep(1)  # let the runner snapshot Ready RSS

    first = True
    count = 0
    audio_seconds = 0.0
    for item in chain.stream(prompt):
        count += 1
        audio_seconds += float(item["seconds"])
        if first:
            emit("pipeline", "first_output", sample_rate=KOKORO_SAMPLE_RATE)
            first = False
    emit("pipeline", "done", count=count, audio_seconds=round(audio_seconds, 3))


if __name__ == "__main__":
    main()
