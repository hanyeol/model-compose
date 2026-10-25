from typing import Dict, List, Any
from mindor.dsl.schema.component import MemoryAgentMemoryBufferConfig, AgentMemoryBufferDriverType
from ..base import AgentMemoryBuffer, register_agent_memory_buffer

@register_agent_memory_buffer(AgentMemoryBufferDriverType.MEMORY)
class MemoryAgentMemoryBuffer(AgentMemoryBuffer):
    def __init__(self, config: MemoryAgentMemoryBufferConfig):
        super().__init__()

        self.config = config

        self._turns: Dict[str, List[List[Any]]] = {}

    async def configure(self) -> None:
        pass

    async def close(self) -> None:
        self._turns.clear()
        self._sessions.clear()

    async def _read_turns(self, session_id: str) -> List[List[Any]]:
        return list(self._turns.get(session_id, []))

    async def _write_turns(self, session_id: str, turns: List[List[Any]]) -> None:
        self._turns[session_id] = list(turns)

    async def _remove_all(self, session_id: str) -> None:
        self._turns.pop(session_id, None)
