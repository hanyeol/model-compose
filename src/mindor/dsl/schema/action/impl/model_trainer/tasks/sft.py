from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelTrainerActionConfig

class SftModelTrainerActionConfig(CommonModelTrainerActionConfig):
    # Dataset configuration
    dataset: str = Field(..., description="Training dataset to use.")
    eval_dataset: Optional[str] = Field(default=None, description="Evaluation dataset.")

    # Data formatting
    text_column: Optional[str] = Field(default=None, description="Column name containing the text for training.")
    prompt_column: Optional[str] = Field(default=None, description="Column name for prompts in chat-style data.")
    response_column: Optional[str] = Field(default=None, description="Column name for responses in chat-style data.")
    system_column: Optional[str] = Field(default=None, description="Column name for system prompts in chat-style data.")

    # Training strategy
    max_seq_length: int = Field(default=512, description="Maximum sequence length for training.")
    packing: bool = Field(default=False, description="Pack multiple short examples into one sequence for efficiency.")

    @model_validator(mode="after")
    def validate_data_columns(self):
        if not self.text_column and not (self.prompt_column and self.response_column):
            raise ValueError("Either 'text_column' or both 'prompt_column' and 'response_column' must be specified.")
        return self
