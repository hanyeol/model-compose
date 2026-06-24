from typing import Literal, Optional, Dict
from pydantic import Field
from .common import TracerDriver, CommonTracerConfig

class OtlpTracerConfig(CommonTracerConfig):
    driver: Literal[TracerDriver.OTLP]
    endpoint: str = Field(..., description="OTLP collector endpoint. Use http(s)://host:port/v1/traces for HTTP, or host:port for gRPC.")
    protocol: Literal["grpc", "http"] = Field(default="http", description="OTLP transport protocol.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Additional headers sent with OTLP requests (e.g., authentication tokens).")
    insecure: bool = Field(default=False, description="Disable TLS verification (gRPC only).")
    service_name: str = Field(default="model-compose", description="Value for the OpenTelemetry `service.name` resource attribute.")
