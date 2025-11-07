from typing import Any, Dict, Optional, Callable
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.logger import logging
from .ipc_protocol import IpcMessage, IpcMessageType
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
        runtime_config: ProcessRuntimeConfig,
        worker_factory: Callable[[str, Queue, Queue], Any]
    ):
        """
        Args:
            worker_id: Worker identifier
            runtime_config: Process runtime configuration
            worker_factory: Factory function to create worker instance
                           (worker_id, request_queue, response_queue) -> Worker
        """
        self.worker_id = worker_id
        self.runtime_config = runtime_config
        self.worker_factory = worker_factory

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

        if self.runtime_config.env:
            for key, value in self.runtime_config.env.items():
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
        self.request_queue.put(stop_message.model_dump())

        timeout_seconds = self._parse_timeout(self.runtime_config.stop_timeout)

        try:
            self.subprocess.join(timeout=timeout_seconds)
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

        self.request_queue.put(message.model_dump())

        try:
            result = await future
            return result
        finally:
            self.pending_requests.pop(request_id, None)

    async def _handle_responses(self) -> None:
        """Handle responses from the subprocess"""
        while True:
            try:
                if not self.response_queue.empty():
                    message_dict = self.response_queue.get_nowait()
                    message = IpcMessage(**message_dict)

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
        timeout = self._parse_timeout(self.runtime_config.start_timeout)
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self.response_queue.empty():
                message_dict = self.response_queue.get()
                message = IpcMessage(**message_dict)

                if message.type == IpcMessageType.RESULT and \
                   message.payload.get("status") == "ready":
                    logging.info(f"Subprocess {self.worker_id} is ready")
                    return

            await asyncio.sleep(0.5)

        raise TimeoutError(
            f"Process {self.worker_id} did not start within {timeout}s"
        )

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

    @staticmethod
    def _parse_timeout(timeout_str: str) -> float:
        """Parse timeout string (e.g., '60s', '2m') to seconds"""
        timeout_str = timeout_str.strip().lower()

        if timeout_str.endswith('s'):
            return float(timeout_str[:-1])
        elif timeout_str.endswith('m'):
            return float(timeout_str[:-1]) * 60
        elif timeout_str.endswith('h'):
            return float(timeout_str[:-1]) * 3600
        else:
            return float(timeout_str)