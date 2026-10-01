from __future__ import annotations
from typing import Any
from mindor.dsl.schema.action import ModelActionConfig
from ......base import ComponentActionContext
from ..base import MinimaxH3TextToVideoTaskAction, MinimaxH3TextToVideoTaskDriverBase

class MinimaxH3TorchTextToVideoTaskDriver(MinimaxH3TextToVideoTaskDriverBase):
    """MiniMax-H3 driver using diffusers' default attention dispatch (SDPA / FlashAttention / xformers)."""

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await MinimaxH3TextToVideoTaskAction(action, self.pipeline).run(context)
