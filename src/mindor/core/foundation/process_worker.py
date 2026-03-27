from typing import Any, Dict
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from .ipc_messages import IpcMessage, IpcMessageType
from multiprocessing import Queue
import asyncio

@dataclass
class ProcessWorkerParams:
    """
    Parameters for process worker runtime configuration.
    Used by foundation layer to configure worker execution environment.
    """
    env: Dict[str, str] = field(default_factory=dict)
    start_timeout: float = 60.0  # seconds
    stop_timeout: float = 30.0   # seconds

class ProcessWorker(ABC):
    """
    Base class for workers running in separate processes.

    This is a generic process worker that can be extended for various use cases
    beyond just components (e.g., workflow execution, data processing, etc.)
    """
    def __init__(self, worker_id: str, request_queue: Queue, response_queue: Queue):
        self.worker_id = worker_id
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.running = True

    async def run(self) -> None:
        try:
            await self._start()
            self._notify_status("ready")

            loop = asyncio.get_event_loop()
            while self.running:
                request = await loop.run_in_executor(None, self.request_queue.get)
                message = IpcMessage(**request)
                try:
                    result = await self._dispatch_message(message)
                    self._send_result(message.request_id, result)
                except Exception as e:
                    self._send_error(message.request_id, str(e))
        except Exception as e:
            self._notify_error(str(e))
        finally:
            await self._stop()

    async def _dispatch_message(self, message: IpcMessage) -> Dict[str, Any]:
        if message.type == IpcMessageType.RUN:
            output = await self._execute_task(message.payload)
            return { "output": output }

        if message.type == IpcMessageType.HEARTBEAT:
            return { "status": "alive" }

        if message.type == IpcMessageType.STOP:
            self.running = False
            return { "status": "stopped" }

    def _send_result(self, request_id: str, payload: Dict[str, Any]) -> None:
        message = IpcMessage(
            type=IpcMessageType.RESULT,
            request_id=request_id,
            payload=payload
        )
        self.response_queue.put(message.to_params())

    def _send_error(self, request_id: str, error: str) -> None:
        message = IpcMessage(
            type=IpcMessageType.ERROR,
            request_id=request_id,
            payload={ "error": error }
        )
        self.response_queue.put(message.to_params())

    def _notify_status(self, status: str) -> None:
        message = IpcMessage(
            type=IpcMessageType.STATUS,
            payload={ "status": status }
        )
        self.response_queue.put(message.to_params())

    def _notify_error(self, error: str) -> None:
        message = IpcMessage(
            type=IpcMessageType.ERROR,
            payload={ "error": error }
        )
        self.response_queue.put(message.to_params())

    @abstractmethod
    async def _start(self) -> None:
        pass

    @abstractmethod
    async def _stop(self) -> None:
        pass

    @abstractmethod
    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        pass
