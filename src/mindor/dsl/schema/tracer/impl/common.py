from typing import Optional, List
from pydantic import BaseModel, Field
from .types import TracerDriver

class TracerCaptureConfig(BaseModel):
    input: bool = Field(default=True, description="Include input data in trace.")
    output: bool = Field(default=True, description="Include output data in trace.")
    redact_keys: List[str] = Field(default_factory=list, description="Keys to redact from trace payloads (case-insensitive, recursive).")
    max_payload_bytes: Optional[int] = Field(default=None, description="Max payload size in bytes. Truncated if exceeded.")

class CommonTracerConfig(BaseModel):
    driver: TracerDriver = Field(..., description="Tracer backend driver.")
    capture: TracerCaptureConfig = Field(default_factory=TracerCaptureConfig, description="Capture settings.")
    timeout: int = Field(default=30, description="Timeout in seconds for API requests.")
