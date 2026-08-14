from typing import Optional
from pydantic import BaseModel, Field

class LlamaCppEngineOptionsConfig(BaseModel):
    n_gpu_layers: Optional[int] = Field(default=None, description="Number of model layers offloaded to GPU; -1 offloads all layers.")
    n_ctx: Optional[int] = Field(default=None, description="Context window size in tokens.")
    n_batch: Optional[int] = Field(default=None, description="Batch size used for prompt processing.")
    n_threads: Optional[int] = Field(default=None, description="Number of CPU threads used for inference.")
    verbose: bool = Field(default=False, description="Whether to emit verbose logging from llama.cpp.")
