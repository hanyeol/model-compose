from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from transformers import PreTrainedModel
import torch
    
async def load_model(
    provider: str,
    model_id: str,
    revision: Optional[str],
    filename: Optional[str],
    model_class: Type[PreTrainedModel],
    *,
    cache_dir: Optional[str] = None,
    local_files_only: bool = False
) -> Union[PreTrainedModel, torch.nn.Module]:
    if provider in [ "huggingface.co", "huggingface.com", "huggingface" ]:
        pass

async def load_model_from_uri(
    uri: str,
    model_class: Type[PreTrainedModel],
    *,
    cache_dir: Optional[str] = None,
    local_files_only: bool = False
) -> Union[PreTrainedModel, torch.nn.Module]:
    pass
