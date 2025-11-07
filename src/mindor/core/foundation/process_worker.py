from typing import Any, Dict
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from mindor.core.logger import logging
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

    def __init__(
        self,
        worker_id: str,
        request_queue: Queue,
        response_queue: Queue
    ):
        self.worker_id = worker_id
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.running = True

    async def run(self) -> None:
        """Main worker loop - handles initialization, message processing, and cleanup"""
        try:
            await self._initialize()

            logging.info(f"ProcessWorker {self.worker_id} initialized in subprocess")

            ready_message = IpcMessage(
                type=IpcMessageType.RESULT,
                request_id="init",
                payload={"status": "ready"}
            )
            self.response_queue.put(ready_message.to_params())

            while self.running:
                if not self.request_queue.empty():
                    message_dict = self.request_queue.get()
                    message = IpcMessage(**message_dict)
                    await self._handle_message(message)

                await asyncio.sleep(0.01)

        except Exception as e:
            logging.error(f"Worker error: {e}")
            error_message = IpcMessage(
                type=IpcMessageType.ERROR,
                request_id="worker",
                payload={"error": str(e)}
            )
            self.response_queue.put(error_message.to_params())

        finally:
            await self._cleanup()

    async def _handle_message(self, message: IpcMessage) -> None:
        """Handle incoming messages from the main process"""
        try:
            if message.type == IpcMessageType.RUN:
                output = await self._execute_task(message.payload)

                response = IpcMessage(
                    type=IpcMessageType.RESULT,
                    request_id=message.request_id,
                    payload={"output": output}
                )
                self.response_queue.put(response.to_params())

            elif message.type == IpcMessageType.HEARTBEAT:
                response = IpcMessage(
                    type=IpcMessageType.RESULT,
                    request_id=message.request_id,
                    payload={"status": "alive"}
                )
                self.response_queue.put(response.to_params())

            elif message.type == IpcMessageType.STOP:
                self.running = False
                response = IpcMessage(
                    type=IpcMessageType.RESULT,
                    request_id=message.request_id,
                    payload={"status": "stopped"}
                )
                self.response_queue.put(response.to_params())

        except Exception as e:
            logging.error(f"Error handling message: {e}")
            error_response = IpcMessage(
                type=IpcMessageType.ERROR,
                request_id=message.request_id,
                payload={"error": str(e)}
            )
            self.response_queue.put(error_response.to_params())

    @abstractmethod
    async def _initialize(self) -> None:
        """
        Initialize the worker (e.g., load models, connect to services, etc.)

        This method is called once when the worker process starts.
        """
        pass

    @abstractmethod
    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        """
        Execute a task with the given payload.

        This is the main work method that subclasses should implement
        to perform their specific work.

        Args:
            payload: Task-specific data from the main process

        Returns:
            Task result to be sent back to the main process
        """
        pass

    @abstractmethod
    async def _cleanup(self) -> None:
        """
        Clean up resources before the worker exits.

        This method is called when the worker is stopping.
        """
        pass
