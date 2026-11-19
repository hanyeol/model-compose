from __future__ import annotations
from typing import Any
from mindor.dsl.schema.action import ModelActionConfig
from ......base import ComponentActionContext
from ..base import MinimaxH3VideoToVideoTaskAction, MinimaxH3VideoToVideoBaseDriver

class MinimaxH3TorchVideoToVideoTaskDriver(MinimaxH3VideoToVideoBaseDriver):
    """MiniMax-H3 ref2va driver using diffusers' default attention dispatch (SDPA / FlashAttention / xformers)."""

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await MinimaxH3VideoToVideoTaskAction(action, self.pipeline).run(context)
