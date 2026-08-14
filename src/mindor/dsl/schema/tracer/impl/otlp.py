from typing import Literal, Optional, Dict
from pydantic import Field
from .common import TracerDriver, CommonTracerConfig

class OtlpTracerConfig(CommonTracerConfig):
    driver: Literal[TracerDriver.OTLP]
    endpoint: str = Field(..., description="Full URL of the OTLP collector endpoint.")
    protocol: Literal[ "grpc", "http" ] = Field(default="http", description="Transport protocol used to send OTLP spans.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers sent with OTLP export requests (e.g., authentication tokens).")
    insecure: bool = Field(default=False, description="Whether to skip TLS verification when connecting to the collector (gRPC only).")
    service_name: str = Field(default="model-compose", description="Value of the OpenTelemetry `service.name` resource attribute.")
