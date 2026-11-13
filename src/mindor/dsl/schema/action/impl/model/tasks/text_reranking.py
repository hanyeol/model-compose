from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextRerankingParamsConfig(BaseModel):
    normalize: Union[bool, str] = Field(default=True, description="Whether sigmoid is applied to model logits so scores fall in the [0, 1] range.")

class TextRerankingModelActionConfig(CommonModelActionConfig):
    query: str = Field(..., description="Query text that candidate texts are ranked against.")
    texts: Union[List[str], str] = Field(..., description="Candidate texts to rerank.")
    top_k: Optional[Union[int, str]] = Field(default=None, description="Number of top-ranked results returned; unset returns all.")
    score_threshold: Optional[Union[float, str]] = Field(default=None, description="Minimum score a result must achieve to be returned.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per query-text pair; unset uses the tokenizer's default.")
    batch_size: Union[int, str] = Field(default=32, description="Number of query-text pairs scored per forward pass.")
    params: TextRerankingParamsConfig = Field(default_factory=TextRerankingParamsConfig, description="Score normalization parameters used during reranking.")
