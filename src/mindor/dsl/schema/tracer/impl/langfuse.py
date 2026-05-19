from typing import Literal, Optional, Dict, Any
from pydantic import Field, model_validator
from .common import TracerDriver, CommonTracerConfig

class LangfuseTracerConfig(CommonTracerConfig):
    driver: Literal[TracerDriver.LANGFUSE]
    url: Optional[str] = Field(default=None, description="Langfuse server URL (e.g., https://cloud.langfuse.com, http://localhost:3000).")
    host: str = Field(default="cloud.langfuse.com", description="Langfuse server hostname or IP address.")
    port: int = Field(default=443, ge=1, le=65535, description="Langfuse server port number.")
    secure: bool = Field(default=True, description="Use HTTPS for connections.")
    public_key: str = Field(..., description="Langfuse public key.")
    secret_key: str = Field(..., description="Langfuse secret key.")

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
