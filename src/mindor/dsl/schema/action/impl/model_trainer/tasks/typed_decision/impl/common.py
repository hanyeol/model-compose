from typing import Optional, Union
from pydantic import Field
from ...common import CommonModelTrainerActionConfig

class TypedDecisionModelTrainerActionConfig(CommonModelTrainerActionConfig):
    # Column layout — rows carry the same shape as typed-decision inference input,
    # plus an `answers` column keyed by question id.
    state_column: str = Field(default="state", description="Dataset column that holds the input state (text).")
    schema_column: str = Field(default="schema", description="Dataset column that holds the per-question schema dict.")
    answers_column: str = Field(default="answers", description="Dataset column that holds ground-truth answers keyed by question id.")

    # Training strategy
    max_seq_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokenized sequence length used during training.")
