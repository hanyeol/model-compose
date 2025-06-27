from typing import TypeVar, Generic, Dict, Tuple, Optional, Any
import time

T = TypeVar("T")

class ExpiringDict(Generic[T]):
    def __init__(self):
        self._store: Dict[str, Tuple[T, float]] = {}

    def set(self, key: str, value: T, expires_in: float = 0) -> None:
        self._store[key] = (value, time.time() + expires_in if expires_in > 0 else float('inf'))

    def get(self, key: str) -> Optional[T]:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                return value
            else:
                del self._store[key]
        return None

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def remove(self, key: str) -> None:
        self._store.pop(key, None)

    def keys(self):
        now = time.time()
        return [ key for key, (_, expires_at) in self._store.items() if now < expires_at ]

    def cleanup(self):
        now = time.time()
        for key in [ key for key, (_, expires_at) in self._store.items() if now >= expires_at ]:
            del self._store[key]
