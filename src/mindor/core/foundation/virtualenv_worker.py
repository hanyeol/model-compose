from __future__ import annotations

from typing import Any, Dict
from abc import ABC, abstractmethod
from mindor.core.utils.subprocess import SubprocessPipeChannel
from .ipc_messages import IpcMessage, IpcMessageType
import asyncio

class VirtualEnvWorker(ABC):
    """
    Base class for workers launched in a separate Python interpreter (virtualenv).

    Communicates with the parent process exclusively through `SubprocessPipeChannel`.
    """
    def __init__(self, worker_id: str, channel: SubprocessPipeChannel):
        self.worker_id = worker_id
        self.channel = channel
        self.running = True

    async def run(self) -> None:
        try:
            await self._start()
            self._notify_status("ready")

            loop = asyncio.get_event_loop()
            while self.running:
                request = await loop.run_in_executor(None, self.channel.recv)
                if request is None:
                    break
                message = IpcMessage(**request)
                try:
                    result = await self._dispatch_message(message)
                    if message.type == IpcMessageType.RUN:
                        self._send_result(message.request_id, result)
                except Exception as e:
                    self._send_error(message.request_id, str(e))
        except Exception as e:
            self._notify_error(str(e))
        finally:
            try:
                await self._stop()
            finally:
                self.channel.close()

    async def _dispatch_message(self, message: IpcMessage) -> Dict[str, Any]:
        if message.type == IpcMessageType.RUN:
            output = await self._execute_task(message.payload or {})
            return { "output": output }

        if message.type == IpcMessageType.HEARTBEAT:
            return { "status": "alive" }

        if message.type == IpcMessageType.STOP:
            self.running = False
            return { "status": "stopped" }

        return { "status": "ignored" }

    def _send_result(self, request_id: str, payload: Dict[str, Any]) -> None:
        message = IpcMessage(
            type=IpcMessageType.RESULT,
            request_id=request_id,
            payload=payload
        )
        self.channel.send(message.to_params())

    def _send_error(self, request_id: str, error: str) -> None:
        message = IpcMessage(
            type=IpcMessageType.ERROR,
            request_id=request_id,
            payload={ "error": error }
        )
        self.channel.send(message.to_params())

    def _notify_status(self, status: str) -> None:
        message = IpcMessage(
            type=IpcMessageType.STATUS,
            payload={ "status": status }
        )
        self.channel.send(message.to_params())

    def _notify_error(self, error: str) -> None:
        message = IpcMessage(
            type=IpcMessageType.ERROR,
            payload={ "error": error }
        )
        try:
            self.channel.send(message.to_params())
        except Exception:
            pass

    @abstractmethod
    async def _start(self) -> None:
        pass

    @abstractmethod
    async def _stop(self) -> None:
        pass

    @abstractmethod
    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        pass
