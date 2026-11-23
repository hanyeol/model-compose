from __future__ import annotations
from typing import Any
from mindor.dsl.schema.action import ModelActionConfig, ImageGenerationActionMethod
from ......base import ComponentActionContext
from ..base import (
    MinimaxH3ImageGenerationBaseDriver,
    MinimaxH3ImageGenerationGenerateAction,
    MinimaxH3ImageGenerationEditAction,
)

class MinimaxH3TorchImageGenerationTaskDriver(MinimaxH3ImageGenerationBaseDriver):
    """MiniMax-H3-Image driver using diffusers' default attention dispatch (SDPA / FlashAttention / xformers)."""

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == ImageGenerationActionMethod.GENERATE:
            return await MinimaxH3ImageGenerationGenerateAction(action, self.pipeline, self.device).run(context)

        if action.method == ImageGenerationActionMethod.EDIT:
            return await MinimaxH3ImageGenerationEditAction(action, self.pipeline, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
