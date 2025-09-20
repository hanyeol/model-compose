from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class CommonModelTrainerActionConfig(CommonActionConfig):
    # Essential training parameters
    learning_rate: float = Field(default=5e-5, description="Learning rate for training.")
    batch_size: int = Field(default=8, description="Training batch size.")
    num_epochs: int = Field(default=3, description="Number of training epochs.")

    # Output configuration
    output_dir: str = Field(default="./output", description="Directory to save the trained model.")

    # Common optimization settings
    weight_decay: float = Field(default=0.01, description="Weight decay for regularization.")
    warmup_steps: int = Field(default=100, description="Number of warmup steps.")
    save_steps: int = Field(default=500, description="Steps between model saves.")

    # Memory optimization
    gradient_checkpointing: bool = Field(default=False, description="Enable gradient checkpointing to save memory.")
    fp16: bool = Field(default=False, description="Enable FP16 mixed precision training.")
