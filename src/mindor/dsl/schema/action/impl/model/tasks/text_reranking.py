from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextRerankingParamsConfig(BaseModel):
    normalize: Union[bool, str] = Field(default=True, description="Whether sigmoid is applied to model logits so scores fall in the [0, 1] range.")

class TextRerankingModelActionConfig(CommonModelActionConfig):
    query: str = Field(..., description="Query text that candidate documents are ranked against.")
    documents: Union[List[str], List[Dict[str, Any]], str] = Field(..., description="Candidate documents to rerank; a list of strings or objects.")
    document_field: Optional[str] = Field(default=None, description="Field name that holds the scored text when documents are objects.")
    top_k: Optional[Union[int, str]] = Field(default=None, description="Number of top-ranked documents returned; unset returns all.")
    score_threshold: Optional[Union[float, str]] = Field(default=None, description="Minimum score a document must achieve to be returned.")
    return_documents: Union[bool, str] = Field(default=True, description="Whether the original document is included with each result.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per query-document pair; unset uses the tokenizer's default.")
    batch_size: Union[int, str] = Field(default=32, description="Number of query-document pairs scored per batch.")
    params: TextRerankingParamsConfig = Field(default_factory=TextRerankingParamsConfig, description="Score normalization parameters used during reranking.")
