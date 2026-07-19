from typing import Optional
import threading

class CancellationToken:
    def __init__(self):
        self._event: threading.Event = threading.Event()
        self._reason: Optional[str] = None

    def cancel(self, reason: Optional[str] = None) -> None:
        self._reason = reason
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._event.wait(timeout)

    @property
    def reason(self) -> Optional[str]:
        return self._reason
