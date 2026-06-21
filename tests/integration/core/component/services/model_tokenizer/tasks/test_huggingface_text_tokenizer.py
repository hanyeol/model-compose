"""Manual / live test for HuggingfaceTextModelTokenizerTaskService.

Loads the tokenizer for `sentence-transformers/all-MiniLM-L6-v2` from the local
HF cache and exercises encode / decode / count round-trips.

Run directly: `python tests/_manual/test_model_tokenizer_text_live.py`
Not collected by pytest (lives under tests/_manual/).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model_tokenizer.tasks.text.huggingface import (
    HuggingfaceTextModelTokenizerTaskService,
)
from mindor.dsl.schema.component import TextModelTokenizerComponentConfig


COMPONENT_ID = "test-text-tokenizer"
MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"

SAMPLE_TEXT  = "The quick brown fox jumps over the lazy dog."
SAMPLE_BATCH = [ "Hello, world!", "Tokenizers are fun." ]


def _build_component_config(actions: list[dict]) -> Any:
    adapter = TypeAdapter(TextModelTokenizerComponentConfig)
    return adapter.validate_python({
        "type": "model-tokenizer",
        "task": "text",
        "driver": "huggingface",
        "model": MODEL_REPO,
        "use_fast": True,
        "actions": actions,
    })


def _action_encode(text_expr: str, max_length: int = 32) -> dict:
    return {
        "method": "encode",
        "text": text_expr,
        "max_length": max_length,
        "padding": False,
        "truncation": True,
        "additional_returns": [ "length" ],
        "batch_size": 4,
    }


def _action_decode(token_ids_expr: str) -> dict:
    return {
        "method": "decode",
        "token_ids": token_ids_expr,
        "skip_special_tokens": True,
        "batch_size": 4,
    }


def _action_count(text_expr: str) -> dict:
    return {
        "method": "count",
        "text": text_expr,
        "batch_size": 4,
    }


async def _run() -> None:
    print(f"[setup] building configs for {MODEL_REPO}")
    component_config = _build_component_config([
        _action_encode("${input.text}"),
        _action_decode("${input.token_ids}"),
        _action_count("${input.text}"),
    ])
    encode_action, decode_action, count_action = component_config.actions

    print(f"[setup] instantiating service")
    service = HuggingfaceTextModelTokenizerTaskService(COMPONENT_ID, component_config)

    print(f"[load] loading tokenizer")
    t0 = time.perf_counter()
    service.load()
    print(f"[load] done in {time.perf_counter() - t0:.2f}s")

    assert service._tokenizer is not None, "tokenizer must be loaded"
    print(f"[load] tokenizer class: {type(service._tokenizer).__name__}")

    # --- encode (single) -----------------------------------------------------
    print(f"\n[encode] single input")
    ctx = ComponentActionContext("r-tok-enc-1", { "text": SAMPLE_TEXT })
    t0 = time.perf_counter()
    enc_result = await service.run(encode_action, ctx)
    print(f"[encode] done in {time.perf_counter() - t0:.3f}s")

    assert isinstance(enc_result, dict), f"encode single should return dict, got {type(enc_result).__name__}"
    assert "input_ids" in enc_result, "encode result must include input_ids"
    assert "attention_mask" in enc_result, "encode result must include attention_mask"
    assert "length" in enc_result, "encode result must include length (requested via additional_returns)"
    input_ids = list(enc_result["input_ids"])
    print(f"[encode] input_ids[:8] = {input_ids[:8]}")
    print(f"[encode] length        = {enc_result['length']}")
    assert len(input_ids) == enc_result["length"], "input_ids length must match reported length"

    # --- decode (single) -----------------------------------------------------
    print(f"\n[decode] round-trip on encoded ids")
    ctx = ComponentActionContext("r-tok-dec-1", { "token_ids": input_ids })
    t0 = time.perf_counter()
    dec_result = await service.run(decode_action, ctx)
    print(f"[decode] done in {time.perf_counter() - t0:.3f}s")

    assert isinstance(dec_result, dict), f"decode single should return dict, got {type(dec_result).__name__}"
    assert "text" in dec_result, "decode result must include text"
    decoded = dec_result["text"].strip().lower()
    print(f"[decode] text = {dec_result['text']!r}")
    assert SAMPLE_TEXT.strip().lower().rstrip(".") in decoded, (
        f"decoded text {decoded!r} should preserve the original sample"
    )

    # --- count (single) ------------------------------------------------------
    print(f"\n[count] single input")
    ctx = ComponentActionContext("r-tok-cnt-1", { "text": SAMPLE_TEXT })
    t0 = time.perf_counter()
    cnt_result = await service.run(count_action, ctx)
    print(f"[count] done in {time.perf_counter() - t0:.3f}s")

    assert isinstance(cnt_result, dict), f"count single should return dict, got {type(cnt_result).__name__}"
    assert "count" in cnt_result, "count result must include count"
    assert cnt_result["count"] == enc_result["length"], (
        f"count ({cnt_result['count']}) must match encode length ({enc_result['length']})"
    )
    print(f"[count] count = {cnt_result['count']} (matches encode length)")

    # --- encode (batch) ------------------------------------------------------
    print(f"\n[encode] batch input")
    ctx = ComponentActionContext("r-tok-enc-batch", { "text": SAMPLE_BATCH })
    t0 = time.perf_counter()
    enc_batch = await service.run(encode_action, ctx)
    print(f"[encode] batch done in {time.perf_counter() - t0:.3f}s")

    assert isinstance(enc_batch, list), f"encode batch should return list, got {type(enc_batch).__name__}"
    assert len(enc_batch) == len(SAMPLE_BATCH), f"expected {len(SAMPLE_BATCH)} results, got {len(enc_batch)}"
    for index, item in enumerate(enc_batch):
        assert "input_ids" in item, f"batch result [{index}] missing input_ids"
        print(f"[encode] batch[{index}] length={item['length']}")

    # --- count (batch) -------------------------------------------------------
    print(f"\n[count] batch input")
    ctx = ComponentActionContext("r-tok-cnt-batch", { "text": SAMPLE_BATCH })
    t0 = time.perf_counter()
    cnt_batch = await service.run(count_action, ctx)
    print(f"[count] batch done in {time.perf_counter() - t0:.3f}s")

    assert isinstance(cnt_batch, list), f"count batch should return list, got {type(cnt_batch).__name__}"
    assert len(cnt_batch) == len(SAMPLE_BATCH)
    for index, item in enumerate(cnt_batch):
        assert item["count"] == enc_batch[index]["length"], (
            f"batch count[{index}]={item['count']} must match encode length={enc_batch[index]['length']}"
        )
        print(f"[count] batch[{index}] count={item['count']}")

    print(f"\n[OK] HuggingfaceTextModelTokenizerTaskService end-to-end run succeeded")


if __name__ == "__main__":
    asyncio.run(_run())
