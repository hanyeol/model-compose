from typing import Type, Optional, Dict, List, Any, Tuple
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelMemoryBufferDriver

class SessionBuffer:
    """Per-session in-memory data: turns, summary, snapshot."""
    def __init__(self):
        self.settled_turns: List[List[Any]] = []
        self.pending_turns: List[List[Any]] = []
        self.summary: str = ""
        self.snapshot: Optional[Tuple[List[List[Any]], str]] = None

    @property
    def turns(self) -> List[List[Any]]:
        return self.settled_turns + self.pending_turns

    def append_turn(self, messages: List[Any]) -> None:
        self.pending_turns.append(messages)

    def merge(self) -> None:
        self.settled_turns = self.settled_turns + self.pending_turns
        self.pending_turns.clear()

    def clear_pending(self) -> None:
        self.pending_turns.clear()

    def take_snapshot(self) -> None:
        self.snapshot = (list(self.settled_turns), self.summary)

    def restore_snapshot(self) -> bool:
        if self.snapshot is None:
            return False
        self.settled_turns = list(self.snapshot[0])
        self.summary = self.snapshot[1]
        self.pending_turns.clear()
        return True

class ModelMemoryBuffer(ABC):
    """Buffer ABC with raw-data abstract methods and shared business logic.

    Each session's in-memory state is held in a SessionBuffer object.
    Drivers only handle persistence of settled turns.
    """
    def __init__(self):
        self._sessions: Dict[str, SessionBuffer] = {}

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    @abstractmethod
    async def setup(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    async def get_turns(self, session_id: str) -> Optional[List[List[Any]]]:
        """Returns all turns (settled + pending), or None if session not in buffer."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return session.turns

    async def set_turns(self, session_id: str, turns: List[List[Any]]) -> None:
        """Auto-creates session if needed."""
        session = await self._acquire_session(session_id)
        session.settled_turns = list(turns)
        await self._write_turns(session_id, turns)
        await self._on_update_turns(session_id)

    async def append_turn(self, session_id: str, messages: List[Any]) -> None:
        """Auto-creates session if needed."""
        session = await self._acquire_session(session_id)
        session.append_turn(messages)

    async def get_summary(self, session_id: str) -> Optional[str]:
        """Returns None if session not in buffer."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return session.summary

    async def set_summary(self, session_id: str, summary: str) -> None:
        """Auto-creates session if needed."""
        session = await self._acquire_session(session_id)
        session.summary = summary

    async def merge_buffer(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.merge()
        await self._write_turns(session_id, session.settled_turns)
        await self._on_update_turns(session_id)

    async def take_snapshot(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.take_snapshot()

    async def restore_snapshot(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        if not session.restore_snapshot():
            return
        await self._write_turns(session_id, session.settled_turns)
        await self._on_update_turns(session_id)

    async def remove(self, session_id: str) -> None:
        await self._remove_all(session_id)
        self._sessions.pop(session_id, None)

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    @abstractmethod
    async def _read_turns(self, session_id: str) -> List[List[Any]]:
        pass

    @abstractmethod
    async def _write_turns(self, session_id: str, turns: List[List[Any]]) -> None:
        pass

    @abstractmethod
    async def _remove_all(self, session_id: str) -> None:
        pass

    async def _on_update_turns(self, session_id: str) -> None:
        """Called when settled turns are written (locally or remotely).
        Clears local pending. Drivers can override to broadcast changes
        (e.g. Pub/Sub), calling super() to keep the pending cleanup."""
        session = self._sessions.get(session_id)
        if session is not None:
            session.clear_pending()

    async def _acquire_session(self, session_id: str) -> SessionBuffer:
        session = self._sessions.get(session_id)
        if session is None:
            session = SessionBuffer()
            self._sessions[session_id] = session
            await self._write_turns(session_id, [])
        return session

    def _get_session(self, session_id: str) -> Optional[SessionBuffer]:
        return self._sessions.get(session_id)

def register_model_memory_buffer(driver: ModelMemoryBufferDriver):
    def decorator(cls: Type[ModelMemoryBuffer]) -> Type[ModelMemoryBuffer]:
        ModelMemoryBufferRegistry[driver] = cls
        return cls
    return decorator

ModelMemoryBufferRegistry: Dict[ModelMemoryBufferDriver, Type[ModelMemoryBuffer]] = {}
