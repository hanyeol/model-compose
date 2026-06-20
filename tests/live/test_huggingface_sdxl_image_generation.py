"""Manual / live test for HuggingfaceImageGenerationTaskService (SDXL).

Loads `stabilityai/stable-diffusion-xl-base-1.0` from the local HF cache and
generates a single image with minimal inference steps to keep the run short.

Run directly: `python tests/_manual/test_image_generation_sdxl_live.py`
Not collected by pytest (lives under tests/_manual/).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from PIL import Image as PILImage
from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.image_generation.huggingface import (
    HuggingfaceImageGenerationTaskService,
)
from mindor.dsl.schema.component import ImageGenerationModelComponentConfig


COMPONENT_ID = "test-sdxl"
MODEL_REPO = "stabilityai/stable-diffusion-xl-base-1.0"


def _build_component_config() -> Any:
    adapter = TypeAdapter(ImageGenerationModelComponentConfig)
    return adapter.validate_python({
        "type": "model",
        "task": "image-generation",
        "driver": "huggingface",
        "architecture": "sdxl",
        "model": MODEL_REPO,
        "device": "mps",
        "preload": False,
        "actions": [
            {
                "text": "a serene mountain lake at sunrise, photorealistic",
                "batch_size": 1,
                "params": {
                    "num_inference_steps": 2,
                    "guidance_scale": 5.0,
                    "width": 512,
                    "height": 512,
                    "num_images_per_prompt": 1,
                    "seed": 42,
                },
            }
        ],
    })


async def _run() -> None:
    print(f"[setup] building configs for {MODEL_REPO}")
    component_config = _build_component_config()
    action_config = component_config.actions[0]

    print(f"[setup] instantiating service")
    service = HuggingfaceImageGenerationTaskService(COMPONENT_ID, component_config, daemon=False)

    print(f"[load] loading pipeline (this may take a while on first run)")
    t0 = time.perf_counter()
    await service._load_model()
    print(f"[load] done in {time.perf_counter() - t0:.1f}s")

    assert service.pipeline is not None, "pipeline must be loaded"
    assert service.device is not None, "device must be resolved"
    print(f"[load] pipeline class: {type(service.pipeline).__name__}, device: {service.device}")

    print(f"[run]  generating 1 image (num_inference_steps=2)")
    t0 = time.perf_counter()
    ctx = ComponentActionContext("r-sdxl-1", {})
    loop = asyncio.get_running_loop()
    result = await service._run(action_config, ctx, loop)
    print(f"[run]  done in {time.perf_counter() - t0:.1f}s")

    assert isinstance(result, PILImage.Image), f"expected PIL.Image, got {type(result).__name__}"
    print(f"[run]  result: {type(result).__name__} size={result.size} mode={result.mode}")

    out_path = "/tmp/test_sdxl_output.png"
    result.save(out_path)
    print(f"[run]  saved to {out_path}")

    print(f"[unload] releasing pipeline")
    await service._unload_model()
    assert service.pipeline is None
    assert service.device is None
    print(f"[unload] done")

    print(f"\n[OK] HuggingfaceImageGenerationTaskService (SDXL) end-to-end run succeeded")


if __name__ == "__main__":
    asyncio.run(_run())
