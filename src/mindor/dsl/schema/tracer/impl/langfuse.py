from typing import Literal, Optional
from pydantic import Field
from .common import TracerDriver, CommonTracerConfig

class LangfuseTracerConfig(CommonTracerConfig):
    driver: Literal[TracerDriver.LANGFUSE]
    base_url: str = Field(default="https://cloud.langfuse.com", description="Langfuse server URL.")
    public_key: str = Field(..., description="Langfuse public key.")
    secret_key: str = Field(..., description="Langfuse secret key.")
