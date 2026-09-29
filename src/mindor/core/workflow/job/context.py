from typing import Optional, Dict, List, Any
from contextlib import contextmanager
from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.workflow.context import WorkflowContext

class JobContext:
    def __init__(self, workflow: WorkflowContext, job_id: str, is_terminal: bool = False):
        self.workflow: WorkflowContext = workflow
        self.job_id: str = job_id

        self._sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self._is_terminal: bool = is_terminal

        self._run_id_stack: List[str] = []
        self._default_input_stack: List[Any] = []
        self._is_terminal_stack: List[bool] = []

        self._renderer: VariableRenderer = VariableRenderer(self._resolve_source)

    @property
    def default_input(self) -> Any:
        if self._default_input_stack and self._default_input_stack[-1] is not None:
            return self._default_input_stack[-1]

        return self.workflow.input

    @property
    def is_terminal(self) -> bool:
        if self._is_terminal_stack:
            return self._is_terminal_stack[-1]

        return self._is_terminal

    @property
    def cancellation_token(self) -> Optional[CancellationToken]:
        return self.workflow.cancellation_token if self.workflow else None

    @contextmanager
    def use_inline_scope(self, run_id: str, default_input: Optional[Any] = None, is_terminal: bool = False):
        self._run_id_stack.append(run_id)
        self._default_input_stack.append(default_input)
        self._is_terminal_stack.append(is_terminal)

        try:
            yield
        finally:
            self._run_id_stack.pop()
            self._default_input_stack.pop()
            self._is_terminal_stack.pop()

    def register_source(self, run_id: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(run_id or "__global__", {})[key] = source

    async def render_variable(
        self,
        run_id: Optional[str],
        value: Any,
        skip_decode: bool = False
    ) -> Any:
        if value is not None:
            return await self._renderer.render(value, run_id or self._current_run_id(), skip_decode=skip_decode)

        return None

    async def _resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})

        if key in sources:
            return sources[key][index] if index is not None else sources[key]

        return await self.workflow.resolve_source(key, index, None)

    def _current_run_id(self) -> Optional[str]:
        if self._run_id_stack:
            return self._run_id_stack[-1]

        return None
