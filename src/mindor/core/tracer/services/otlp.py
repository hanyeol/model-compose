from typing import Optional, Dict, Any
from mindor.dsl.schema.tracer import OtlpTracerConfig
from mindor.dsl.schema.tracer.impl.types import TracerDriver
from ..base import TracerService, register_tracer
import json, copy

@register_tracer(TracerDriver.OTLP)
class OtlpTracerService(TracerService):
    def __init__(self, id: str, config: OtlpTracerConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._tracer = None
        self._provider = None
        self._trace_spans: Dict[str, Any] = {}
        self._job_spans: Dict[str, Any] = {}
        self._trace_attachments: Dict[str, Any] = {}

    def _get_setup_requirements(self):
        requirements = [ "opentelemetry-api>=1.27", "opentelemetry-sdk>=1.27" ]

        if self.config.protocol == "grpc":
            requirements.append("opentelemetry-exporter-otlp-proto-grpc>=1.27")
        else:
            requirements.append("opentelemetry-exporter-otlp-proto-http>=1.27")

        return requirements

    async def _start(self) -> None:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if self.config.protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(
                endpoint=self.config.endpoint,
                headers=self.config.headers,
                insecure=self.config.insecure,
                timeout=self.config.timeout,
            )
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(
                endpoint=self.config.endpoint,
                headers=self.config.headers,
                timeout=self.config.timeout,
            )

        resource = Resource.create({"service.name": self.config.service_name})
        self._provider = TracerProvider(resource=resource)
        self._provider.add_span_processor(BatchSpanProcessor(exporter))
        self._tracer = self._provider.get_tracer("model-compose")

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self._provider:
            self._provider.shutdown()
            self._provider = None
            self._tracer = None

    def on_workflow_start(self, task_id: str, workflow_id: str, input: Any, session_id: Optional[str], metadata: Any) -> None:
        from opentelemetry import context as context_api, trace as trace_api

        span = self._tracer.start_span(
            name=f"workflow.{workflow_id}",
            attributes=self._workflow_start_attributes(task_id, workflow_id, session_id, input, metadata),
        )
        context = trace_api.set_span_in_context(span)
        token = context_api.attach(context)

        self._trace_spans[task_id] = span
        self._trace_attachments[task_id] = (context, token)

    def on_workflow_end(self, task_id: str, workflow_id: str, output: Any, elapsed: float, is_streaming: bool) -> None:
        from opentelemetry import context as context_api

        span = self._trace_spans.pop(task_id, None)
        attachment = self._trace_attachments.pop(task_id, None)

        if span:
            span.set_attribute("model_compose.elapsed_seconds", elapsed)
            if is_streaming:
                span.set_attribute("model_compose.streaming", True)

            captured = self._capture_output(output)
            if captured is not None:
                span.set_attribute("model_compose.output", self._serialize_attribute(captured))

            span.end()

        if attachment:
            _, token = attachment
            context_api.detach(token)

    def on_workflow_error(self, task_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
        from opentelemetry import context as context_api
        from opentelemetry.trace import Status, StatusCode

        span = self._trace_spans.pop(task_id, None)
        attachment = self._trace_attachments.pop(task_id, None)

        if span:
            span.set_attribute("model_compose.elapsed_seconds", elapsed)
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.end()

        if attachment:
            _, token = attachment
            context_api.detach(token)

    def on_job_start(self, task_id: str, job_id: str, workflow_id: str, input: Any) -> None:
        attachment = self._trace_attachments.get(task_id)
        if not attachment:
            return

        context, _ = attachment
        span = self._tracer.start_span(
            name=f"job.{job_id}",
            context=context,
            attributes={
                "model_compose.task_id": task_id,
                "model_compose.workflow_id": workflow_id,
                "model_compose.job_id": job_id,
                **self._payload_attributes("input", self._capture_input(input)),
            },
        )
        self._job_spans[f"{task_id}:{job_id}"] = span

    def on_job_end(self, task_id: str, job_id: str, workflow_id: str, output: Any, elapsed: float) -> None:
        span_key = f"{task_id}:{job_id}"
        span = self._job_spans.pop(span_key, None)

        if span:
            span.set_attribute("model_compose.elapsed_seconds", elapsed)
            captured = self._capture_output(output)
            if captured is not None:
                span.set_attribute("model_compose.output", self._serialize_attribute(captured))
            span.end()

    def on_job_error(self, task_id: str, job_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
        from opentelemetry.trace import Status, StatusCode

        span_key = f"{task_id}:{job_id}"
        span = self._job_spans.pop(span_key, None)

        if span:
            span.set_attribute("model_compose.elapsed_seconds", elapsed)
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.end()

    def _workflow_start_attributes(self, task_id: str, workflow_id: str, session_id: Optional[str], input: Any, metadata: Any) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {
            "model_compose.task_id": task_id,
            "model_compose.workflow_id": workflow_id,
            "gen_ai.system": "model-compose",
            "gen_ai.operation.name": "workflow",
        }
        if session_id:
            attributes["session.id"] = session_id
        if metadata:
            attributes["model_compose.metadata"] = self._serialize_attribute(metadata)

        attributes.update(self._payload_attributes("input", self._capture_input(input)))

        return attributes

    def _payload_attributes(self, kind: str, payload: Any) -> Dict[str, Any]:
        if payload is None:
            return {}
        return { f"model_compose.{kind}": self._serialize_attribute(payload) }

    def _capture_input(self, data: Any) -> Any:
        if self.config.capture.input:
            return self._process_payload(data)

        return None

    def _capture_output(self, data: Any) -> Any:
        if self.config.capture.output:
            return self._process_payload(data)

        return None

    def _process_payload(self, data: Any) -> Any:
        if data is None:
            return None

        if self.config.capture.redact_keys:
            data = self._redact_payload(copy.deepcopy(data))

        if self.config.capture.max_payload_bytes:
            serialized = json.dumps(data, default=str, ensure_ascii=False)
            if len(serialized.encode("utf-8")) > self.config.capture.max_payload_bytes:
                return "[truncated]"

        return data

    def _redact_payload(self, data: Any) -> Any:
        if isinstance(data, dict):
            redact_lower = { k.lower() for k in self.config.capture.redact_keys }
            return { k: "[redacted]" if k.lower() in redact_lower else self._redact_payload(v) for k, v in data.items() }

        if isinstance(data, list):
            return [ self._redact_payload(item) for item in data ]

        return data

    def _serialize_attribute(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(data)
