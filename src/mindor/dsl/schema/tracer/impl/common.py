from typing import Optional, List
from pydantic import BaseModel, Field
from .types import TracerDriver

class TracerCaptureConfig(BaseModel):
    input: bool = Field(default=True, description="Whether to include input payloads in exported traces.")
    output: bool = Field(default=True, description="Whether to include output payloads in exported traces.")
    redact_keys: List[str] = Field(default_factory=list, description="Payload keys whose values are redacted before export (case-insensitive, applied recursively).")
    max_payload_bytes: Optional[int] = Field(default=None, description="Maximum payload size in bytes before truncation.")

class CommonTracerConfig(BaseModel):
    driver: TracerDriver = Field(..., description="Backend implementation used to export traces.")
    capture: TracerCaptureConfig = Field(default_factory=TracerCaptureConfig, description="Controls which payload fields are captured in exported traces.")
    timeout: int = Field(default=30, description="Maximum seconds to wait for a trace export request before failing.")
