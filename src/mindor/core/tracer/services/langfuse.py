from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, Any
from mindor.dsl.schema.tracer import LangfuseTracerConfig
from mindor.dsl.schema.tracer.impl.types import TracerDriver
from ..base import TracerService, register_tracer
import json, copy

if TYPE_CHECKING:
    from langfuse import Langfuse

@register_tracer(TracerDriver.LANGFUSE)
class LangfuseTracerService(TracerService):
    def __init__(self, id: str, config: LangfuseTracerConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[Langfuse] = None

        self._trace_spans: Dict[str, Any] = {}
        self._job_spans: Dict[str, Any] = {}

    def _get_setup_requirements(self):
        return [ "langfuse>=4.0" ]

    async def _start(self) -> None:
        from langfuse import Langfuse

        self.client = Langfuse(
            public_key=self.config.public_key,
            secret_key=self.config.secret_key,
            base_url=self._resolve_base_url(),
            timeout=self.config.timeout
        )

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client:
            self.client.shutdown()
            self.client = None

    def on_workflow_start(self, task_id: str, workflow_id: str, input: Any, session_id: Optional[str], metadata: Any) -> None:
        trace_id = self.client.create_trace_id(seed=task_id)

        self._upsert_trace(
            trace_id=trace_id,
            name=workflow_id,
            session_id=session_id,
            input=self._capture_input(input),
            metadata={
                "workflow_id": workflow_id,
                **({"metadata": metadata} if metadata else {})
            }
        )

        trace_span = self.client.start_observation(
            name=workflow_id,
            trace_context={"trace_id": trace_id},
        )
        self._trace_spans[task_id] = trace_span

    def on_workflow_end(self, task_id: str, workflow_id: str, output: Any, elapsed: float, is_streaming: bool) -> None:
        trace_span = self._trace_spans.pop(task_id, None)

        if trace_span:
            metadata = {
                "workflow_id": workflow_id,
                "elapsed": elapsed,
            }
            if is_streaming:
                metadata["is_streaming"] = True
            trace_span.update(
                output=self._capture_output(output),
                metadata=metadata,
            )
            trace_span.end()

    def on_workflow_error(self, task_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
        trace_span = self._trace_spans.pop(task_id, None)
        
        if trace_span:
            trace_span.update(
                output=str(error),
                level="ERROR",
                status_message=str(error),
                metadata={
                    "workflow_id": workflow_id,
                    "elapsed": elapsed
                }
            )
            trace_span.end()

    def on_job_start(self, task_id: str, job_id: str, workflow_id: str, input: Any) -> None:
        trace_span = self._trace_spans.get(task_id)

        if trace_span:
            span_key = f"{task_id}:{job_id}"
            job_span = trace_span.start_observation(
                name=job_id,
                input=self._capture_input(input)
            )
            self._job_spans[span_key] = job_span

    def on_job_end(self, task_id: str, job_id: str, workflow_id: str, output: Any, elapsed: float) -> None:
        span_key = f"{task_id}:{job_id}"
        job_span = self._job_spans.pop(span_key, None)

        if job_span:
            job_span.update(output=self._capture_output(output))
            job_span.end()

    def on_job_error(self, task_id: str, job_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
        span_key = f"{task_id}:{job_id}"
        job_span = self._job_spans.pop(span_key, None)
        
        if job_span:
            job_span.update(
                output=str(error),
                level="ERROR",
                status_message=str(error)
            )
            job_span.end()

    def _upsert_trace(self, trace_id: str, name: str, session_id: Optional[str], input: Any, metadata: Any) -> None:
        from langfuse.api.ingestion.types.trace_body import TraceBody
        from langfuse._utils import _get_timestamp

        event = {
            "id": self.client.create_trace_id(),
            "type": "trace-create",
            "timestamp": _get_timestamp(),
            "body": TraceBody(
                id=trace_id,
                name=name,
                session_id=session_id,
                input=input,
                metadata=metadata,
            ),
        }
        self.client._resources.add_trace_task(event)

    def _resolve_base_url(self) -> str:
        if self.config.url:
            return self.config.url
        scheme = "https" if self.config.secure else "http"
        default_port = 443 if self.config.secure else 80
        if self.config.port == default_port:
            return f"{scheme}://{self.config.host}"
        return f"{scheme}://{self.config.host}:{self.config.port}"

    def _capture_input(self, data: Any) -> Any:
        if self.config.capture.input:
            return self._process_payload(data)
        
        return None

    def _capture_output(self, data: Any) -> Any:
        if self.config.capture.output:
            return self._process_payload(data)

        return None
        
    def _process_payload(self, data: Any) -> Any:
        if data is not None:
            if self.config.capture.redact_keys:
                data = self._redact_payload(copy.deepcopy(data))

            if self.config.capture.max_payload_bytes:
                serialized = json.dumps(data, default=str, ensure_ascii=False)
                if len(serialized.encode("utf-8")) > self.config.capture.max_payload_bytes:
                    return "[truncated]"

            return data
    
        return None

    def _redact_payload(self, data: Any) -> Any:
        if isinstance(data, dict):
            redact_lower = { k.lower() for k in self.config.capture.redact_keys }
            return { k: "[redacted]" if k.lower() in redact_lower else self._redact_payload(v) for k, v in data.items() }

        if isinstance(data, list):
            return [ self._redact_payload(item) for item in data ]

        return data
