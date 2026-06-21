"""Manual / live test for HuggingfaceTextEmbeddingTaskService.

Loads `sentence-transformers/all-MiniLM-L6-v2` from the local HF cache and
embeds a small batch of texts.

Run directly: `python tests/_manual/test_text_embedding_live.py`
Not collected by pytest (lives under tests/_manual/).
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.text_embedding.huggingface import (
    HuggingfaceTextEmbeddingTaskService,
)
from mindor.dsl.schema.component import TextEmbeddingModelComponentConfig


COMPONENT_ID = "test-text-embedding"
MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
EXPECTED_DIM = 384


def _build_component_config() -> Any:
    adapter = TypeAdapter(TextEmbeddingModelComponentConfig)
    return adapter.validate_python({
        "type": "model",
        "task": "text-embedding",
        "driver": "huggingface",
        "model": MODEL_REPO,
        "device": "mps",
        "preload": False,
        "actions": [
            {
                "text": "${input.text}",
                "batch_size": 8,
                "max_input_length": 128,
                "params": {
                    "pooling": "mean",
                    "normalize": True,
                },
            }
        ],
    })


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


async def _run() -> None:
    print(f"[setup] building configs for {MODEL_REPO}")
    component_config = _build_component_config()
    action_config = component_config.actions[0]

    print(f"[setup] instantiating service")
    service = HuggingfaceTextEmbeddingTaskService(COMPONENT_ID, component_config, daemon=False)

    print(f"[load] loading model")
    t0 = time.perf_counter()
    await service._load_model()
    print(f"[load] done in {time.perf_counter() - t0:.1f}s")

    assert service.model is not None, "model must be loaded"
    assert service.tokenizer is not None, "tokenizer must be loaded"
    assert service.device is not None, "device must be resolved"
    print(f"[load] model class: {type(service.model).__name__}, device: {service.device}")

    texts = [
        "The cat sits on the mat.",
        "A feline rests on a rug.",
        "The Eiffel Tower is in Paris.",
    ]

    print(f"[run]  embedding {len(texts)} texts")
    t0 = time.perf_counter()
    ctx = ComponentActionContext("r-emb-1", {"text": texts})
    loop = asyncio.get_running_loop()
    result = await service._run(action_config, ctx, loop)
    print(f"[run]  done in {time.perf_counter() - t0:.2f}s")

    assert isinstance(result, list), f"expected list, got {type(result).__name__}"
    assert len(result) == len(texts), f"expected {len(texts)} embeddings, got {len(result)}"

    for index, embedding in enumerate(result):
        assert isinstance(embedding, list), f"embedding[{index}] must be list"
        assert len(embedding) == EXPECTED_DIM, f"embedding[{index}] dim {len(embedding)} != {EXPECTED_DIM}"
        norm = math.sqrt(sum(value * value for value in embedding))
        assert abs(norm - 1.0) < 1e-3, f"embedding[{index}] is not L2-normalized (norm={norm:.4f})"

    print(f"[run]  3 embeddings, dim={EXPECTED_DIM}, all L2-normalized")

    sim_paraphrase = _cosine(result[0], result[1])
    sim_unrelated  = _cosine(result[0], result[2])

    print(f"[run]  cosine sim(text0, text1 paraphrase) = {sim_paraphrase:.4f}")
    print(f"[run]  cosine sim(text0, text2 unrelated)  = {sim_unrelated:.4f}")
    assert sim_paraphrase > sim_unrelated, (
        f"paraphrase similarity ({sim_paraphrase:.4f}) should exceed unrelated ({sim_unrelated:.4f})"
    )

    print(f"[unload] releasing model")
    await service._unload_model()
    assert service.model is None
    assert service.tokenizer is None
    assert service.device is None
    print(f"[unload] done")

    print(f"\n[OK] HuggingfaceTextEmbeddingTaskService end-to-end run succeeded")


if __name__ == "__main__":
    asyncio.run(_run())
