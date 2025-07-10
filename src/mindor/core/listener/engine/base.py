from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.listener import ListenerConfig, ListenerType
from mindor.core.services import AsyncService
from mindor.core.utils.workqueue import WorkQueue

class ListenerEngine(AsyncService):
    def __init__(self, id: str, config: ListenerConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ListenerConfig = config
        self.queue: Optional[WorkQueue] = None

        # if self.config.max_concurrent_count > 0:
        #     self.queue = WorkQueue(self.config.max_concurrent_count, self._run_workflow)

    async def _start(self) -> None:
        if self.queue:
            await self.queue.start()

        await super()._start()

    async def _stop(self) -> None:
        if self.queue:
            await self.queue.stop()

        await super()._stop()

ListenerEngineMap: Dict[ListenerType, Type[ListenerEngine]] = {}
