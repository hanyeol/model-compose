from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextRerankingParamsConfig(BaseModel):
    normalize: Union[bool, str] = Field(default=True, description="Whether to apply sigmoid to logits so scores are in [0, 1].")

class TextRerankingModelActionConfig(CommonModelActionConfig):
    query: str = Field(..., description="Query text to rank documents against.")
    documents: Union[List[str], List[Dict[str, Any]], str] = Field(..., description="Candidate documents to rerank. Either a list of strings or a list of objects.")
    document_field: Optional[str] = Field(default=None, description="If documents are objects, the field name containing the text to score.")
    top_k: Optional[Union[int, str]] = Field(default=None, description="Return only the top K results after ranking. If unset, all results are returned.")
    score_threshold: Optional[Union[float, str]] = Field(default=None, description="Discard results with a score below this threshold.")
    return_documents: Union[bool, str] = Field(default=True, description="Whether to include the original document in each result.")
    batch_size: Union[int, str] = Field(default=32, description="Number of (query, document) pairs to score in a single batch.")
    max_input_length: Union[int, str] = Field(default=512, description="Maximum number of tokens per (query, document) pair.")
    params: TextRerankingParamsConfig = Field(default_factory=TextRerankingParamsConfig, description="Configuration parameters for reranking.")
