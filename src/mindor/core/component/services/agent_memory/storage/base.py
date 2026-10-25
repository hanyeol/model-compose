from typing import Type, Tuple, Optional, Dict, List, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import AgentMemoryStorageDriverType

class AgentMemoryStorage(ABC):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    @abstractmethod
    async def configure(self) -> None:
        """Initialize storage (create tables, etc.)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close storage connections."""
        pass

    @abstractmethod
    async def load(self, session_id: str) -> Tuple[List[List[Any]], str]:
        """Load session data. Returns (turns, summary)."""
        pass

    @abstractmethod
    async def save(self, session_id: str, turns: List[List[Any]], summary: str) -> None:
        """Save session data."""
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete session data."""
        pass

def register_agent_memory_storage(driver: AgentMemoryStorageDriverType):
    def decorator(cls: Type[AgentMemoryStorage]) -> Type[AgentMemoryStorage]:
        AgentMemoryStorageRegistry[driver] = cls
        return cls
    return decorator

AgentMemoryStorageRegistry: Dict[AgentMemoryStorageDriverType, Type[AgentMemoryStorage]] = {}
