from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional
from mindor.core.controller.base import TaskEventCallback

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService, TaskState

class ControllerRunner:
    def __init__(self) -> None:
        from mindor.core.controller.base import ControllerService

        service = ControllerService.get_shared_instance()
        if service is None:
            raise RuntimeError("ControllerService is not running")

        self.service: ControllerService = service

    async def run_workflow(
        self,
        workflow_id: Optional[str],
        input: Any,
        on_event: Optional[TaskEventCallback] = None,
        wait_for_completion: bool = True,
    ) -> TaskState:
        return await self.service.run_workflow(
            workflow_id,
            input,
            wait_for_completion=wait_for_completion,
            on_event=on_event
        )

    async def resume_workflow(
        self,
        task_id: str,
        job_id: str,
        run_id: Optional[str],
        answer: Any = None
    ) -> None:
        await self.service.resume_workflow(task_id, job_id, run_id, answer)

    async def cancel_workflow(self, task_id: str) -> TaskState:
        return await self.service.cancel_workflow(task_id, wait_for_completion=True)

    async def wait_for_completion(self, task_id: str) -> TaskState:
        return await self.service.wait_for_terminal_state(task_id)

    async def get_task_state(self, task_id: str) -> TaskState:
        state = self.service.get_task_state(task_id)
        if state is None:
            raise LookupError(f"Task not found: {task_id}")
        return state

    async def close(self) -> None:
        pass
