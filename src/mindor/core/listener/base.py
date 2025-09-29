from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.listener import ListenerConfig, ListenerType
from mindor.core.foundation import AsyncService
from mindor.core.utils.workqueue import WorkQueue
from mindor.core.logger import logging

class ListenerService(AsyncService):
    def __init__(self, id: str, config: ListenerConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ListenerConfig = config
        self.work_queue: Optional[WorkQueue] = None

        # if self.config.max_concurrent_count > 0:
        #     self.work_queue = WorkQueue(self.config.max_concurrent_count, self._run_workflow)

    async def _start(self) -> None:
        if self.work_queue:
            await self.work_queue.start()

        await super()._start()

    async def _stop(self) -> None:
        if self.work_queue:
            await self.work_queue.stop()

        await super()._stop()

    async def _install_package(self, package_spec: str, repository: Optional[str]) -> None:
        logging.info(f"Installing required module: {package_spec}")
        await super()._install_package(package_spec, repository)

def register_listener(type: ListenerType):
    def decorator(cls: Type[ListenerService]) -> Type[ListenerService]:
        ListenerRegistry[type] = cls
        return cls
    return decorator

ListenerRegistry: Dict[ListenerType, Type[ListenerService]] = {}
