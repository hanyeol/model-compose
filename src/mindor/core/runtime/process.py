from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field
from mindor.core.runtime.base.ipc_manager import IpcRuntimeManager
from mindor.core.runtime.base.ipc_worker import IpcRuntimeWorker
from multiprocessing import Process, Queue
import asyncio, os


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


@dataclass
class ProcessRuntimeManagerParams:
    """
    Parameters for the process runtime manager.
    Used to configure how the worker subprocess is spawned and managed.
    """
    env: Dict[str, str] = field(default_factory=dict)
    start_timeout: float = 60.0  # seconds
    stop_timeout: float = 30.0   # seconds


class ProcessRuntimeManager(IpcRuntimeManager):
    """
    Generic process runtime manager for running workers in separate processes.

    Can be used for use cases requiring process isolation.
    """

    def __init__(
        self,
        worker_id: str,
        worker_factory: Callable[[str, Queue, Queue], Any],
        worker_params: ProcessRuntimeManagerParams = None
    ):
        super().__init__(worker_id)

        self.worker_factory = worker_factory
        self.worker_params = worker_params or ProcessRuntimeManagerParams()

        self._subprocess: Optional[Process] = None
        self._request_queue: Optional[Queue] = None
        self._response_queue: Optional[Queue] = None

        self._start_timeout = self.worker_params.start_timeout
        self._stop_timeout = self.worker_params.stop_timeout

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()

        self._request_queue  = Queue()
        self._response_queue = Queue()

        self._subprocess = Process(
            target=self._run_worker,
            args=(
                self.worker_factory,
                self.worker_id,
                self._request_queue,
                self._response_queue
            ),
            daemon=False
        )

        if self.worker_params.env:
            for key, value in self.worker_params.env.items():
                os.environ[key] = value

        self._subprocess.start()

        await self._wait_for_ready()

        self._response_task = asyncio.create_task(self._handle_responses())

    async def stop(self) -> None:
        await self._send_stop_message()

        try:
            await self._loop.run_in_executor(
                None,
                lambda: self._subprocess.join(timeout=self._stop_timeout),
            )
        except Exception:
            pass

        if self._subprocess.is_alive():
            self._subprocess.terminate()
            self._subprocess.join(timeout=5)
            if self._subprocess.is_alive():
                self._subprocess.kill()

        # Unblock the executor thread parked in _recv_message (Queue.get is blocking).
        # Without this, loop.shutdown_default_executor() hangs forever on interpreter exit.
        if self._response_queue is not None:
            self._response_queue.put(None)

        if self._response_task is not None:
            try:
                await self._response_task
            except asyncio.CancelledError:
                pass

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._request_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._response_queue.get)

    @staticmethod
    def _run_worker(
        worker_factory: Callable[[str, Queue, Queue], Any],
        worker_id: str,
        request_queue: Queue,
        response_queue: Queue,
    ) -> None:
        worker = worker_factory(worker_id, request_queue, response_queue)
        loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(worker.run())
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
