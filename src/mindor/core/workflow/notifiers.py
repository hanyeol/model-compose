from typing import Literal, Optional, Dict, Callable, Awaitable, Any
from mindor.core.logger import logging
from .context import WorkflowContext

JobEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]
ComponentEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]

class JobEventNotifier:
    def __init__(self, workflow_id: str, callback: Optional[JobEventCallback]):
        self.workflow_id: str = workflow_id
        self.callback: Optional[JobEventCallback] = callback

    async def notify(
        self,
        event: Literal[ "started", "completed", "failed", "routed" ],
        job_id: str,
        job_type: str,
        context: WorkflowContext,
        elapsed: Optional[float] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        error: Optional[str] = None,
        next_job_id: Optional[str] = None
    ) -> None:
        if self.callback:
            payload = self._build_payload(event, job_id, job_type, context, elapsed, input, output, error, next_job_id)
            try:
                await self.callback(payload)
            except Exception:
                logging.warning("on_job_event callback failed for job '%s'", job_id, exc_info=True)

    def _build_payload(
        self,
        event: Literal[ "started", "completed", "failed", "routed" ],
        job_id: str,
        job_type: str,
        context: WorkflowContext,
        elapsed: Optional[float],
        input: Optional[Any],
        output: Optional[Any],
        error: Optional[str],
        next_job_id: Optional[str]
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = { "event": event, "job_id": job_id, "job_type": job_type, "workflow_id": self.workflow_id }
        run_ids = context.job_run_ids.get(job_id)
        if run_ids:
            payload["run_id"] = run_ids[0] if len(run_ids) == 1 else list(run_ids)
        if elapsed is not None:
            payload["elapsed"] = elapsed
        if input is not None:
            payload["input"] = input
        if output is not None:
            payload["output"] = output
        if error is not None:
            payload["error"] = error
        if next_job_id is not None:
            payload["next_job_id"] = next_job_id
        return payload

class ComponentEventNotifier:
    def __init__(self, workflow_id: str, callback: Optional[ComponentEventCallback]):
        self.workflow_id: str = workflow_id
        self.callback: Optional[ComponentEventCallback] = callback

    async def notify(
        self,
        event: Literal[ "started", "completed", "failed", "internal" ],
        job_id: str,
        component_id: str,
        component_type: str,
        run_id: str,
        kind: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        if self.callback:
            payload = self._build_payload(event, job_id, component_id, component_type, run_id, kind, input, output, error)
            try:
                await self.callback(payload)
            except Exception:
                logging.warning("on_component_event callback failed for component '%s' in job '%s'", component_id, job_id, exc_info=True)

    def _build_payload(
        self,
        event: Literal[ "started", "completed", "failed", "internal" ],
        job_id: str,
        component_id: str,
        component_type: str,
        run_id: str,
        kind: Optional[str],
        input: Optional[Any],
        output: Optional[Any],
        error: Optional[str],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "event": event,
            "workflow_id": self.workflow_id,
            "job_id": job_id,
            "component_id": component_id,
            "component_type": component_type,
            "run_id": run_id,
        }
        if kind is not None:
            payload["kind"] = kind
        if input is not None:
            payload["input"] = input
        if output is not None:
            payload["output"] = output
        if error is not None:
            payload["error"] = error
        return payload
