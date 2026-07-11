from typing import Optional
from pydantic import BaseModel, Field

class LlamaCppEngineOptionsConfig(BaseModel):
    n_gpu_layers: Optional[int] = Field(default=None, description="Number of layers to offload to GPU. -1 offloads all layers.")
    n_ctx: Optional[int] = Field(default=None, description="Context window size in tokens.")
    n_batch: Optional[int] = Field(default=None, description="Prompt processing batch size.")
    n_threads: Optional[int] = Field(default=None, description="Number of CPU threads to use.")
    verbose: bool = Field(default=False, description="Enable verbose logging from llama.cpp.")
