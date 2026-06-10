from typing import Optional, Any
from .tracer import TracerInstances
import logging

def on_workflow_start(task_id: str, workflow_id: str, input: Any, session_id: Optional[str] = None, metadata: Any = None) -> None:
    for tracer in TracerInstances.values():
        try:
            tracer.on_workflow_start(task_id, workflow_id, input, session_id, metadata)
        except Exception:
            logging.warning("Tracer '%s' failed on_workflow_start", tracer.id, exc_info=True)

def on_workflow_end(task_id: str, workflow_id: str, output: Any, elapsed: float, is_streaming: bool = False) -> None:
    for tracer in TracerInstances.values():
        try:
            tracer.on_workflow_end(task_id, workflow_id, output, elapsed, is_streaming)
        except Exception:
            logging.warning("Tracer '%s' failed on_workflow_end", tracer.id, exc_info=True)

def on_workflow_error(task_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
    for tracer in TracerInstances.values():
        try:
            tracer.on_workflow_error(task_id, workflow_id, error, elapsed)
        except Exception:
            logging.warning("Tracer '%s' failed on_workflow_error", tracer.id, exc_info=True)

def on_job_start(task_id: str, job_id: str, workflow_id: str, input: Any) -> None:
    for tracer in TracerInstances.values():
        try:
            tracer.on_job_start(task_id, job_id, workflow_id, input)
        except Exception:
            logging.warning("Tracer '%s' failed on_job_start", tracer.id, exc_info=True)

def on_job_end(task_id: str, job_id: str, workflow_id: str, output: Any, elapsed: float) -> None:
    for tracer in TracerInstances.values():
        try:
            tracer.on_job_end(task_id, job_id, workflow_id, output, elapsed)
        except Exception:
            logging.warning("Tracer '%s' failed on_job_end", tracer.id, exc_info=True)

def on_job_error(task_id: str, job_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
    for tracer in TracerInstances.values():
        try:
            tracer.on_job_error(task_id, job_id, workflow_id, error, elapsed)
        except Exception:
            logging.warning("Tracer '%s' failed on_job_error", tracer.id, exc_info=True)

