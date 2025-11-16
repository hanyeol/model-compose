from typing import Any, Dict, Optional, Callable
from mindor.core.logger import logging
from .ipc_messages import IpcMessage, IpcMessageType
from .process_worker import ProcessWorkerParams
from multiprocessing import Process, Queue
import asyncio, os, uuid, time

class ProcessRuntimeManager:
    """
    Generic process runtime manager for running workers in separate processes.

    Can be used for use cases requiring process isolation.
    """

    def __init__(
        self,
        worker_id: str,
        worker_factory: Callable[[str, Queue, Queue], Any],
        worker_params: ProcessWorkerParams = None
    ):
        """
        Args:
            worker_id: Worker identifier
            worker_factory: Factory function to create worker instance
                           (worker_id, request_queue, response_queue) -> Worker
            worker_params: Worker runtime parameters (optional, uses defaults if not provided)
        """
        self.worker_id = worker_id
        self.worker_factory = worker_factory
        self.worker_params = worker_params or ProcessWorkerParams()

        self.subprocess: Optional[Process] = None
        self.request_queue: Optional[Queue] = None
        self.response_queue: Optional[Queue] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.response_handler_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the subprocess"""
        self.request_queue  = Queue()
        self.response_queue = Queue()

        self.subprocess = Process(
            target=self._run_worker,
            args=(
                self.worker_id,
                self.request_queue,
                self.response_queue
            ),
            daemon=False
        )

        if self.worker_params.env:
            for key, value in self.worker_params.env.items():
                os.environ[key] = value

        self.subprocess.start()
        logging.info(f"Started subprocess for worker {self.worker_id} (PID: {self.subprocess.pid})")

        await self._wait_for_ready()

        self.response_handler_task = asyncio.create_task(
            self._handle_responses()
        )

    async def stop(self) -> None:
        """Stop the subprocess"""
        logging.info(f"Stopping subprocess for worker {self.worker_id}")

        stop_message = IpcMessage(
            type=IpcMessageType.STOP,
            request_id=str(uuid.uuid4())
        )
        self.request_queue.put(stop_message.to_params())

        try:
            self.subprocess.join(timeout=self.worker_params.stop_timeout)
        except TimeoutError:
            logging.warning(f"Process {self.worker_id} did not stop gracefully, terminating")
            self.subprocess.terminate()
            self.subprocess.join(timeout=5)
            if self.subprocess.is_alive():
                logging.error(f"Process {self.worker_id} did not terminate, killing")
                self.subprocess.kill()

        if self.response_handler_task:
            self.response_handler_task.cancel()

    async def execute(self, payload: Dict[str, Any]) -> Any:
        """Execute a task in the subprocess"""
        request_id = str(uuid.uuid4())

        message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id=request_id,
            payload=payload
        )

        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future

        self.request_queue.put(message.to_params())

        try:
            return await future
        finally:
            self.pending_requests.pop(request_id, None)

    async def _handle_responses(self) -> None:
        """Handle responses from the subprocess"""
        while True:
            try:
                if not self.response_queue.empty():
                    message = IpcMessage(**self.response_queue.get_nowait())

                    if message.request_id in self.pending_requests:
                        future = self.pending_requests[message.request_id]

                        if message.type == IpcMessageType.RESULT:
                            future.set_result(message.payload.get("output"))
                        elif message.type == IpcMessageType.ERROR:
                            error = message.payload.get("error", "Unknown error")
                            future.set_exception(Exception(error))

                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error handling response: {e}")

    async def _wait_for_ready(self) -> None:
        """Wait for subprocess to be ready"""
        start_time = time.time()
        timeout = self.worker_params.start_timeout

        while time.time() - start_time < timeout:
            if not self.response_queue.empty():
                message = IpcMessage(**self.response_queue.get())

                if message.type == IpcMessageType.RESULT and message.payload.get("status") == "ready":
                    logging.info(f"Subprocess {self.worker_id} is ready")
                    return

            await asyncio.sleep(0.5)

        raise TimeoutError(f"Process {self.worker_id} did not start within {timeout}s")

    def _run_worker(
        self,
        worker_id: str,
        request_queue: Queue,
        response_queue: Queue
    ) -> None:
        """Subprocess entry point"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        worker = self.worker_factory(worker_id, request_queue, response_queue)

        try:
            loop.run_until_complete(worker.run())
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
