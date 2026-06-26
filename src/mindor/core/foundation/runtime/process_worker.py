from typing import Any, Dict, Optional
from .ipc_worker import IpcRuntimeWorker
from multiprocessing import Queue
import asyncio

class ProcessRuntimeWorker(IpcRuntimeWorker):
    """
    Base class for workers running in separate processes via `multiprocessing.Process`.

    Communicates with the parent process through a pair of `multiprocessing.Queue`s.
    """

    def __init__(self, worker_id: str, request_queue: Queue, response_queue: Queue):
        super().__init__(worker_id)

        self.request_queue = request_queue
        self.response_queue = response_queue

    async def _send_message(self, message: bytes) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.response_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.request_queue.get)

    def _close_transport(self) -> None:
        # Queue objects do not need explicit close from the worker side; the
        # parent owns the queue lifecycle.
        pass
