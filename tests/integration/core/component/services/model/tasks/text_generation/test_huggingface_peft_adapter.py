"""Live test for PEFT adapter loading on a real HuggingFace text-generation model.

Downloads a small base model (~250 MB) and a published LoRA adapter, attaches
the adapter via ``HuggingfaceTextGenerationTaskService._load_pretrained_model``,
and runs a short generation to confirm the merged model is callable end-to-end.

Pair:
  base    : facebook/opt-125m
  adapter : peft-internal-testing/opt-125m-dummy-lora

Run directly:
    python tests/live/test_huggingface_peft_adapter.py

Not collected by the default pytest run (``-m 'not live'`` in pyproject.toml).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.text_generation.huggingface import (
    HuggingfaceTextGenerationTaskService,
)
from mindor.dsl.schema.component import TextGenerationModelComponentConfig


COMPONENT_ID = "test-peft-text-generation"
BASE_MODEL_REPO = "facebook/opt-125m"
ADAPTER_REPO = "peft-internal-testing/opt-125m-dummy-lora"


def _build_component_config(*, with_adapter: bool, weight: float = 1.0) -> Any:
    adapter = TypeAdapter(TextGenerationModelComponentConfig)
    raw: dict = {
        "type": "model",
        "task": "text-generation",
        "driver": "huggingface",
        "model": BASE_MODEL_REPO,
        "device": "cpu",
        "preload": False,
        "actions": [
            {
                "prompt": "${input.text}",
                "batch_size": 1,
                "params": {
                    "max_output_length": 16,
                    "do_sample": False,
                },
            }
        ],
    }
    if with_adapter:
        raw["peft_adapters"] = [
            {
                "type": "lora",
                "name": "dummy",
                "model": ADAPTER_REPO,
                "weight": weight,
            }
        ]
    return adapter.validate_python(raw)


async def _load_and_generate(*, with_adapter: bool, weight: float = 1.0) -> str:
    label = f"adapter@{weight}" if with_adapter else "base-only"
    print(f"\n[{label}] building config")
    component_config = _build_component_config(with_adapter=with_adapter, weight=weight)
    action_config = component_config.actions[0]

    service = HuggingfaceTextGenerationTaskService(COMPONENT_ID, component_config, daemon=False)

    print(f"[{label}] loading model")
    t0 = time.perf_counter()
    await service._load_model()
    print(f"[{label}] load done in {time.perf_counter() - t0:.1f}s")

    assert service.model is not None, "model must be loaded"
    assert service.tokenizer is not None, "tokenizer must be loaded"
    print(f"[{label}] model class: {type(service.model).__name__}")

    if with_adapter:
        # PeftModel exposes the active adapter name; confirm the merge/set ran.
        active = getattr(service.model, "active_adapter", None)
        print(f"[{label}] active adapter: {active}")
        assert active is not None, "expected an active PEFT adapter on the loaded model"

    prompt = "The quick brown fox"
    print(f"[{label}] generating for prompt: {prompt!r}")
    t0 = time.perf_counter()
    ctx = ComponentActionContext("r-peft-1", {"text": prompt})
    loop = asyncio.get_running_loop()
    result = await service._run(action_config, ctx, loop)
    print(f"[{label}] generate done in {time.perf_counter() - t0:.2f}s")

    assert isinstance(result, str), f"expected str result, got {type(result).__name__}"
    assert len(result) > 0, "generation produced empty output"
    print(f"[{label}] output: {result!r}")

    await service._unload_model()
    assert service.model is None
    return result


async def _run() -> None:
    print(f"[setup] base={BASE_MODEL_REPO}  adapter={ADAPTER_REPO}")

    base_output = await _load_and_generate(with_adapter=False)
    adapter_output = await _load_and_generate(with_adapter=True, weight=1.0)
    # Non-unit weight exercises the add_weighted_adapter / blended_adapter branch.
    blended_output = await _load_and_generate(with_adapter=True, weight=0.5)

    print("\n[summary]")
    print(f"  base-only      : {base_output!r}")
    print(f"  adapter@1.0    : {adapter_output!r}")
    print(f"  adapter@0.5    : {blended_output!r}")

    # All three runs must produce text. We do NOT assert that adapter output
    # differs from base — the testing LoRA is randomly initialized, so the
    # delta may be small at greedy decoding. The contract under test is the
    # load path, not the quality of the adapter.
    assert all(isinstance(out, str) and out for out in (base_output, adapter_output, blended_output))

    print("\n[OK] PEFT adapter load + generation end-to-end run succeeded")


if __name__ == "__main__":
    asyncio.run(_run())
