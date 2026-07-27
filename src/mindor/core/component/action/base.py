from typing import Any, Callable
import asyncio, functools

class ComponentAction:
    async def _run_in_executor(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(None, functools.partial(fn, *args, **kwargs))
