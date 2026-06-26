from __future__ import annotations

from typing import Optional
from mindor.core.utils.transport.subprocess_pipe import SubprocessPipeChannel
from .ipc_worker import IpcRuntimeWorker
import asyncio

class VirtualEnvRuntimeWorker(IpcRuntimeWorker):
    """
    Base class for workers launched in a separate Python interpreter (virtualenv).

    Communicates with the parent process through a line-framed bytes channel
    (`SubprocessPipeChannel`). Serialized IPC messages travel as bytes.
    """

    def __init__(self, worker_id: str, channel: SubprocessPipeChannel):
        super().__init__(worker_id)
        self.channel = channel

    async def _send_message(self, message: bytes) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.channel.recv)

    def _close_transport(self) -> None:
        self.channel.close()
