from typing import Literal, Optional, Dict, Any
from pydantic import Field, model_validator
from .common import TracerDriver, CommonTracerConfig

class LangfuseTracerConfig(CommonTracerConfig):
    driver: Literal[TracerDriver.LANGFUSE]
    url: Optional[str] = Field(default=None, description="Full URL of the Langfuse server. Mutually exclusive with `host`.")
    host: str = Field(default="cloud.langfuse.com", description="Hostname or IP address of the Langfuse server.")
    port: int = Field(default=443, ge=1, le=65535, description="TCP port the Langfuse server listens on.")
    secure: bool = Field(default=True, description="Whether to connect to the Langfuse server over HTTPS.")
    public_key: str = Field(..., description="Langfuse project public key used to identify the client.")
    secret_key: str = Field(..., description="Langfuse project secret key used to authenticate the client.")

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
