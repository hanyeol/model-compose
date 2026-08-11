from typing import Deque, List, Literal, Optional, Union, Any
from collections import deque
import asyncio, json, os, shutil, tempfile

class EventAdaptiveLinger:
    _MIN_SECONDS    = 0.05
    _MAX_SECONDS    = 0.5
    _DOWN_THRESHOLD = 3
    _UP_THRESHOLD   = 20
    _DOWN_FACTOR    = 0.7
    _UP_FACTOR      = 1.5

    def __init__(self):
        self._seconds: float = self._MIN_SECONDS

    @property
    def seconds(self) -> float:
        return self._seconds

    def update(self, drained: int) -> None:
        if drained > self._UP_THRESHOLD:
            self._seconds = min(self._MAX_SECONDS, self._seconds * self._UP_FACTOR)
        elif drained < self._DOWN_THRESHOLD:
            self._seconds = max(self._MIN_SECONDS, self._seconds * self._DOWN_FACTOR)

    def reset(self) -> None:
        self._seconds = self._MIN_SECONDS

class EventHistory:
    _DEFAULT_MAX_MEMORY_EVENT_COUNT = 100

    def __init__(self, max_memory_event_count: int = _DEFAULT_MAX_MEMORY_EVENT_COUNT):
        self._max_memory_event_count: int = max_memory_event_count
        self._events: Deque[Any] = deque()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._adaptive_linger: Optional[EventAdaptiveLinger] = None
        self._spool_path: Optional[str] = None
        self._spool_file = None
        self._total_count: int = 0

    def put(self, event: Any) -> None:
        self._queue.put_nowait(event)

    def get(self) -> List[Any]:
        return list(self._events)

    def total_count(self) -> int:
        return self._total_count

    def drain(self) -> int:
        count = 0
        while not self._queue.empty():
            self._append(self._queue.get_nowait())
            count += 1
        return count

    def reset(self) -> None:
        self._events.clear()
        self._total_count = 0

        while not self._queue.empty():
            self._queue.get_nowait()

        self._reset_spool()

        if self._adaptive_linger is not None:
            self._adaptive_linger.reset()

    def export(self, path: str, keep: bool = False) -> None:
        if self._spool_file is None:
            for event in self._events:
                self._spool(event)

        self._spool_file.flush()

        if keep:
            shutil.copy(self._spool_path, path)
            return

        self._spool_file.close()
        os.replace(self._spool_path, path)

        self._spool_file = None
        self._spool_path = None

    async def poll(self, timeout: float, linger: Union[float, Literal["adaptive"]] = 0.0) -> bool:
        try:
            event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return False

        self._append(event)
        drained = 1

        if linger == "adaptive":
            if self._adaptive_linger is None:
                self._adaptive_linger = EventAdaptiveLinger()
            wait = self._adaptive_linger.seconds
        else:
            wait = linger

        if wait > 0:
            await asyncio.sleep(wait)

        while not self._queue.empty():
            self._append(self._queue.get_nowait())
            drained += 1

        if linger == "adaptive":
            self._adaptive_linger.update(drained)

        return True

    def _append(self, event: Any) -> None:
        self._events.append(event)
        self._total_count += 1

        while len(self._events) > self._max_memory_event_count:
            self._spool(self._events.popleft())

    def _spool(self, event: Any) -> None:
        if self._spool_file is None:
            fd, self._spool_path = tempfile.mkstemp(prefix="model-compose-log-", suffix=".jsonl")
            self._spool_file = os.fdopen(fd, "w", encoding="utf-8")

        try:
            line = json.dumps(event, ensure_ascii=False)
        except (TypeError, ValueError):
            line = json.dumps(repr(event), ensure_ascii=False)

        self._spool_file.write(line + "\n")
        self._spool_file.flush()

    def _reset_spool(self) -> None:
        if self._spool_file is not None:
            try:
                self._spool_file.close()
            except Exception:
                pass
            self._spool_file = None

        if self._spool_path is not None:
            try:
                os.unlink(self._spool_path)
            except OSError:
                pass
            self._spool_path = None
