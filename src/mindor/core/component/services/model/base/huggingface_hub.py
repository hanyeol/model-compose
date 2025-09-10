from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import HuggingfaceModelConfig

def get_model_path(model: HuggingfaceModelConfig) -> Optional[str]:
    if model.filename:
        from huggingface_hub import hf_hub_download
        return hf_hub_download(
            repo_id=model.repository,
            filename=model.filename,
            revision=model.revision,
            cache_dir=model.cache_dir,
            token=model.token,
            local_files_only=model.local_files_only
        )
    else:
        from huggingface_hub import snapshot_download
        return snapshot_download(
            repo_id=model.repository,
            revision=model.revision,
            cache_dir=model.cache_dir,
            token=model.token,
            local_files_only=model.local_files_only
        )
