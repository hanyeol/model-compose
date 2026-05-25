from typing import Type, Tuple, Optional, Dict, List, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelMemoryStorageDriver

class ModelMemoryStorage(ABC):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    @abstractmethod
    async def setup(self) -> None:
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

def register_model_memory_storage(driver: ModelMemoryStorageDriver):
    def decorator(cls: Type[ModelMemoryStorage]) -> Type[ModelMemoryStorage]:
        ModelMemoryStorageRegistry[driver] = cls
        return cls
    return decorator

ModelMemoryStorageRegistry: Dict[ModelMemoryStorageDriver, Type[ModelMemoryStorage]] = {}
