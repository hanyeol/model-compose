from typing import Union, Optional, Dict, List, Any
from pydantic import Field
from .common import CommonModelActionConfig

class TypedDecisionModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts the scorer judges against the schema.")
    schema_: Union[Dict[str, Any], str] = Field(..., alias="schema", description="Flat field schema declaring enum/boolean fields to score.")
    return_probabilities: Union[bool, str] = Field(default=False, description="Whether per-candidate probabilities are included per field.")
    return_logits: Union[bool, str] = Field(default=False, description="Whether raw logits are included per field.")
    batch_size: Union[int, str] = Field(default=1, description="Number of texts scored per batch.")

    model_config = { "populate_by_name": True }  # `schema` shadows BaseModel.schema(), so accept it via alias.
