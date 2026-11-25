from typing import Any, Callable
from mindor.dsl.schema.action.impl.common import CommonActionConfig
import asyncio, functools

class ComponentAction:
    config: CommonActionConfig

    def __init__(self, config: CommonActionConfig):
        self.config = config

    async def _run_in_executor(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(None, functools.partial(fn, *args, **kwargs))
